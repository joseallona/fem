"""
Full monitoring pipeline — Phase 2+.

Stages (per Pipeline Specification):
  1  Source Discovery     — skipped in Phase 2 (manual sources only)
  2  Source Selection     — filter to approved sources
  3  Crawling             — RSS + HTML
  4  Raw Document Storage — store with hash
  5  Deduplication        — hash + title similarity
  6  Relevance Filtering  — deterministic keyword scoring
  7  Signal Extraction    — LLM
  8  Classification       — deterministic rules + LLM
  9  Scoring & Ranking    — deterministic
  10 Scenario Mapping     — deterministic keyword overlap
  11 Scenario Update      — deterministic scoring engine
  11b Signal Clustering   — deterministic Jaccard + Union-Find
  12 Change Detection     — diff vs previous run
  13 Trend Synthesis      — LLM over signal clusters
  14 Driver Extraction    — LLM from trends
  15 Axis Proposal        — LLM pole labels for top-2 drivers
  16 Scenario Monitoring  — deterministic indicator matching + alerts
"""
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.crawl import CrawlRun, RawDocument
from app.models.signal import Signal
from app.models.source import Source
from app.models.theme import Theme
from app.services.crawler import fetch_source
from app.services.dedup import is_duplicate
from app.services.relevance import is_relevant, score_relevance
from app.services.scoring import (
    apply_signal_scores,
    auto_map_signals_to_scenarios,
    detect_changes,
    update_all_scenarios,
)
from app.services.signal_extractor import extract_and_classify
from app.services.signal_archive import archive_signal

logger = logging.getLogger(__name__)


def _get_previous_run_id(db: Session, theme_id: UUID, current_run_id: UUID):
    prev = (
        db.query(CrawlRun)
        .filter(
            CrawlRun.theme_id == theme_id,
            CrawlRun.id != current_run_id,
            CrawlRun.status == "completed",
        )
        .order_by(CrawlRun.started_at.desc())
        .first()
    )
    return prev.id if prev else None


def _is_cancelled(db: Session, run_id: str) -> bool:
    """Re-fetch run status from DB to detect cancellation requests."""
    db.expire_all()
    run = db.get(CrawlRun, run_id)
    return run is not None and run.status == "cancelled"


def _set_stage(db: Session, run: CrawlRun, stage: str):
    """Update current_stage on the run and flush immediately."""
    run.current_stage = stage
    db.commit()


def run_monitoring_pipeline(theme_id: str, run_id: str):
    db = SessionLocal()
    run = None
    try:
        run = db.get(CrawlRun, run_id)
        theme = db.get(Theme, theme_id)
        if not run or not theme:
            logger.error("Run or theme not found: %s / %s", run_id, theme_id)
            return

        logger.info("Pipeline started — theme: %s, run: %s", theme.name, run_id)

        # Stage 2: Source selection
        _set_stage(db, run, "Selecting sources…")
        sources = (
            db.query(Source)
            .filter(Source.theme_id == theme_id, Source.status == "approved")
            .all()
        )
        if not sources:
            _finish_run(db, run, sources_scanned=0, docs_fetched=0, signals_created=0,
                        notes="No approved sources found.")
            return

        run.sources_scanned = len(sources)
        db.commit()

        total_docs = 0
        total_signals = 0
        new_signal_ids = []
        n_sources = len(sources)

        for i, source in enumerate(sources, 1):
            if _is_cancelled(db, run_id):
                logger.info("Pipeline cancelled — run: %s", run_id)
                return

            source_label = source.name or source.domain or source.url
            crawl_mode = "initial" if not source.initial_crawl_done else "monitor"
            stage_prefix = "Initial crawl" if crawl_mode == "initial" else "Crawling"
            _set_stage(db, run, f"{stage_prefix} source {i}/{n_sources}: {source_label[:60]}")
            logger.info("Crawling source (%s): %s", crawl_mode, source.url)

            # Stage 3: Crawl
            try:
                raw_docs = fetch_source(
                    source.url,
                    mode=crawl_mode,
                    since=source.last_crawled_at if crawl_mode == "monitor" else None,
                )
            except Exception as e:
                logger.warning("Crawl error for %s: %s", source.url, e)
                raw_docs = []

            _set_stage(db, run, f"Processing documents from source {i}/{n_sources}…")

            source_docs_count = 0
            source_filtered = 0
            for doc_data in raw_docs:
                content_hash = doc_data.get("content_hash", "")
                canonical_url = doc_data.get("canonical_url", "")
                title = doc_data.get("title", "")
                raw_text = doc_data.get("raw_text", "")

                # Stage 5: Dedup
                if is_duplicate(db, content_hash, canonical_url, title):
                    continue

                # Stage 4: Store raw document
                raw_doc = RawDocument(
                    source_id=source.id,
                    crawl_run_id=run.id,
                    url=doc_data.get("url", ""),
                    title=title,
                    published_at=doc_data.get("published_at"),
                    raw_text=raw_text,
                    content_hash=content_hash,
                    canonical_url=canonical_url,
                    metadata_json=doc_data.get("metadata_json", {}),
                )
                db.add(raw_doc)
                db.flush()
                total_docs += 1
                source_docs_count += 1

                # Stage 6: Relevance filtering
                rel_score = score_relevance(
                    raw_text=raw_text,
                    title=title,
                    theme_name=theme.name,
                    primary_subject=theme.primary_subject,
                    related_subjects=theme.related_subjects_json or [],
                    focal_question=theme.focal_question,
                )
                if not is_relevant(rel_score):
                    source_filtered += 1
                    logger.warning("  FILTERED (rel=%.3f, text_len=%d): %s", rel_score, len(raw_text), title[:60])
                    continue

                # Stage 7+8: Signal extraction + classification
                _set_stage(db, run, f"Extracting signals from source {i}/{n_sources} ({total_signals} found so far)…")
                signal_data = extract_and_classify(
                    raw_text=raw_text,
                    title=title,
                    theme_name=theme.name,
                    focal_question=theme.focal_question,
                    relevance_score=rel_score,
                )
                if not signal_data:
                    continue

                signal = Signal(
                    theme_id=theme_id,
                    source_id=source.id,
                    raw_document_id=raw_doc.id,
                    title=signal_data.get("title", title)[:500],
                    summary=signal_data.get("summary", ""),
                    signal_type=signal_data.get("signal_type"),
                    steep_category=signal_data.get("steep_category"),
                    horizon=signal_data.get("horizon"),
                    importance_score=signal_data.get("importance_score", 0.5),
                    novelty_score=signal_data.get("novelty_score", 0.5),
                    relevance_score=rel_score,
                    status="active",
                )
                db.add(signal)
                db.flush()
                new_signal_ids.append(signal.id)
                total_signals += 1

                # Archive to the persistent historical store (survives theme resets)
                archive_signal(
                    url=source.url,
                    title=signal_data.get("title", title),
                    summary=signal_data.get("summary"),
                    theme_name=theme.name,
                    relevance_reason=signal_data.get("relevance_reason"),
                )

            if source_docs_count > 0:
                logger.warning(
                    "Source %s: %d new docs, %d filtered by relevance, %d passed",
                    source_label[:40], source_docs_count, source_filtered,
                    source_docs_count - source_filtered,
                )

            # Strategy 5: auto-block sources that yield nothing on initial crawl
            if crawl_mode == "initial" and source_docs_count == 0:
                logger.warning(
                    "Source %s yielded 0 documents on initial crawl — marking as blocked.",
                    source.url,
                )
                source.status = "blocked"
                source.initial_crawl_done = True
                source.last_crawled_at = datetime.now(timezone.utc)
                db.commit()
                continue

            # Update source last crawled + mark initial crawl done
            source.last_crawled_at = datetime.now(timezone.utc)
            source.initial_crawl_done = True
            db.commit()

        if _is_cancelled(db, run_id):
            logger.info("Pipeline cancelled before scoring — run: %s", run_id)
            return

        # Stage 9: Scoring + ranking
        _set_stage(db, run, f"Scoring and ranking {total_signals} signal(s)…")
        new_signals = [db.get(Signal, sid) for sid in new_signal_ids if db.get(Signal, sid)]
        apply_signal_scores(db, new_signals)

        # Stage 10+11: Scenario mapping + update
        _set_stage(db, run, "Mapping signals to scenarios…")
        if new_signal_ids:
            auto_map_signals_to_scenarios(db, theme_id, new_signal_ids)
        update_all_scenarios(db, theme_id)

        # Stage 11b: Signal clustering
        _set_stage(db, run, "Clustering signals…")
        from app.services.clustering import run_clustering_for_theme
        run_clustering_for_theme(theme_id, db)

        # Stage 12: Change detection
        _set_stage(db, run, "Detecting changes…")
        prev_run_id = _get_previous_run_id(db, theme_id, run.id)
        changes = detect_changes(db, theme_id, run.id, prev_run_id)

        if _is_cancelled(db, run_id):
            return

        # Stage 13: Trend synthesis from signal clusters
        _set_stage(db, run, "Synthesising trends from signal clusters…")
        try:
            from app.services.trend_synthesizer import run_trend_synthesis
            run_trend_synthesis(theme_id, db)
        except Exception as e:
            logger.warning("Trend synthesis failed (non-fatal): %s", e)

        if _is_cancelled(db, run_id):
            return

        # Stage 14: Driver extraction from trends
        _set_stage(db, run, "Extracting drivers of change…")
        try:
            from app.services.driver_extractor import run_driver_extraction
            run_driver_extraction(theme_id, db)
        except Exception as e:
            logger.warning("Driver extraction failed (non-fatal): %s", e)

        if _is_cancelled(db, run_id):
            return

        # Stage 15: Axis proposal (only if axes not yet proposed/confirmed)
        _set_stage(db, run, "Proposing scenario axes…")
        try:
            from app.services.axis_selector import run_axis_selection
            run_axis_selection(theme_id, db)
        except Exception as e:
            logger.warning("Axis selection failed (non-fatal): %s", e)

        if _is_cancelled(db, run_id):
            return

        # Stage 16: Scenario monitoring (only if live scenarios with indicators exist)
        _set_stage(db, run, "Updating scenario monitoring…")
        try:
            from app.models.scenario_pipeline import ScenarioIndicator
            has_indicators = db.query(ScenarioIndicator).filter(
                ScenarioIndicator.theme_id == theme_id
            ).first()
            if has_indicators:
                from app.services.scenario_monitor import run_scenario_monitoring
                monitor_report = run_scenario_monitoring(theme_id, db, new_signal_ids)
                if monitor_report.get("alerts"):
                    changes["monitoring_alerts"] = monitor_report["alerts"]
        except Exception as e:
            logger.warning("Scenario monitoring failed (non-fatal): %s", e)

        _finish_run(
            db, run,
            sources_scanned=len(sources),
            docs_fetched=total_docs,
            signals_created=total_signals,
            notes=json.dumps(changes),
        )
        logger.info("Pipeline complete — docs: %d, signals: %d", total_docs, total_signals)

    except Exception as e:
        logger.exception("Pipeline failed: %s", e)
        if run:
            run.status = "failed"
            run.completed_at = datetime.now(timezone.utc)
            run.notes = str(e)
            db.commit()
    finally:
        db.close()


def _finish_run(db: Session, run: CrawlRun, sources_scanned: int, docs_fetched: int,
                signals_created: int, notes: str = ""):
    run.status = "completed"
    run.completed_at = datetime.now(timezone.utc)
    run.sources_scanned = sources_scanned
    run.documents_fetched = docs_fetched
    run.signals_created = signals_created
    run.notes = notes
    db.commit()
