"""
Backfill signal extraction for initial crawl docs (crawl_run_id=None).
These docs were stored before signal extraction was wired up in the pipeline.
"""
import sys
import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

from app.core.database import SessionLocal
from app.models.crawl import RawDocument
from app.models.signal import Signal
from app.models.source import Source
from app.models.theme import Theme
from app.services.relevance import score_relevance, is_relevant
from app.services.signal_extractor import extract_and_classify
from app.services.scoring import apply_signal_scores, auto_map_signals_to_scenarios, update_all_scenarios

db = SessionLocal()
theme = db.query(Theme).first()
print(f"Theme: {theme.name!r}", flush=True)

docs = db.query(RawDocument).filter(RawDocument.crawl_run_id==None).all()
print(f"Initial crawl docs: {len(docs)}", flush=True)

new_signal_ids = []
processed = 0
filtered = 0
extracted = 0

for d in docs:
    raw_text = d.raw_text or ""
    title = d.title or ""

    rel = score_relevance(
        raw_text=raw_text, title=title,
        theme_name=theme.name,
        primary_subject=theme.primary_subject,
        related_subjects=theme.related_subjects_json or [],
        focal_question=theme.focal_question,
    )
    if not is_relevant(rel):
        filtered += 1
        continue

    processed += 1
    print(f"  [{processed}] rel={rel:.3f} {title[:60]!r}", flush=True)

    signal_data = extract_and_classify(
        raw_text=raw_text, title=title,
        theme_name=theme.name,
        focal_question=theme.focal_question,
        relevance_score=rel,
    )
    if not signal_data:
        print(f"    → extraction returned None", flush=True)
        continue

    # Check if signal already exists for this raw_doc
    existing = db.query(Signal).filter(Signal.raw_document_id==d.id).first()
    if existing:
        continue

    sig = Signal(
        theme_id=str(theme.id),
        source_id=d.source_id,
        raw_document_id=d.id,
        title=signal_data.get("title", title)[:500],
        summary=signal_data.get("summary", ""),
        signal_type=signal_data.get("signal_type"),
        steep_category=signal_data.get("steep_category"),
        horizon=signal_data.get("horizon"),
        importance_score=signal_data.get("importance_score", 0.5),
        novelty_score=signal_data.get("novelty_score", 0.5),
        relevance_score=rel,
        status="active",
    )
    db.add(sig)
    db.flush()
    new_signal_ids.append(sig.id)
    extracted += 1
    print(f"    → signal created: {sig.title[:60]!r}", flush=True)

print(f"\nFiltered: {filtered}, Passed relevance: {processed}, Signals created: {extracted}", flush=True)

if new_signal_ids:
    print("Scoring signals...", flush=True)
    sigs = [db.get(Signal, sid) for sid in new_signal_ids]
    apply_signal_scores(db, sigs)
    print("Mapping to scenarios...", flush=True)
    auto_map_signals_to_scenarios(db, str(theme.id), new_signal_ids)
    update_all_scenarios(db, str(theme.id))
    db.commit()
    print(f"Done — {extracted} signals saved.", flush=True)
else:
    db.commit()
    print("No signals created.", flush=True)

db.close()
