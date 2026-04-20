"""
Brief generation service.

Layer 1 (deterministic): select and structure content from DB.
Layer 2 (LLM): generate prose for semantic sections only.
"""
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.brief import Brief
from app.models.scenario import Scenario
from app.models.signal import Signal
from app.models.theme import Theme
from app.services.llm_gateway import draft_brief_section


# ---------- Layer 1: deterministic assembly ----------

def _select_top_signals(db: Session, theme_id: UUID, period_start: date, period_end: date, top_n: int = 5):
    return (
        db.query(Signal)
        .filter(
            Signal.theme_id == theme_id,
            Signal.status == "active",
            Signal.created_at >= period_start,
            Signal.created_at <= period_end,
        )
        .order_by(Signal.importance_score.desc())
        .limit(top_n)
        .all()
    )


def _select_changed_signals(
    db: Session,
    theme_id: UUID,
    period_start: date,
    period_end: date,
    top_n: int = 5,
    elevated_signal_ids: list[str] | None = None,
):
    """
    Prefer signals identified by the pipeline's change detection (elevated_signal_ids)
    over the novelty+relevance proxy. Falls back to the proxy when no change data exists.
    """
    if elevated_signal_ids:
        from uuid import UUID as _UUID
        signals = (
            db.query(Signal)
            .filter(Signal.id.in_([_UUID(sid) for sid in elevated_signal_ids[:top_n]]))
            .all()
        )
        if signals:
            return signals
    # Fallback: highest novelty + relevance within the period
    return (
        db.query(Signal)
        .filter(
            Signal.theme_id == theme_id,
            Signal.status == "active",
            Signal.created_at >= period_start,
            Signal.created_at <= period_end,
        )
        .order_by((Signal.novelty_score + Signal.relevance_score).desc())
        .limit(top_n)
        .all()
    )


def _select_active_scenarios(db: Session, theme_id: UUID):
    return db.query(Scenario).filter(Scenario.theme_id == theme_id).all()


def _build_structured_payload(
    theme: Theme,
    top_signals,
    changed_signals,
    scenarios,
) -> dict:
    return {
        "theme": {"id": str(theme.id), "name": theme.name, "focal_question": theme.focal_question},
        "key_developments": [
            {"id": str(s.id), "title": s.title, "summary": s.summary, "type": s.signal_type}
            for s in top_signals
        ],
        "whats_changing": [
            {"id": str(s.id), "title": s.title, "novelty": s.novelty_score}
            for s in changed_signals
        ],
        "scenarios": [
            {
                "id": str(sc.id),
                "name": sc.name,
                "confidence": sc.confidence_level,
                "momentum": sc.momentum_state,
            }
            for sc in scenarios
        ],
    }


# ---------- Layer 2: LLM prose generation ----------

def _generate_prose(payload: dict) -> str:
    theme_name = payload["theme"]["name"]
    focal_question = payload["theme"].get("focal_question", "")

    dev_context = "\n".join(
        f"- {d['title']}: {d['summary'] or ''}" for d in payload["key_developments"]
    )
    change_context = "\n".join(f"- {d['title']}" for d in payload["whats_changing"])
    scenario_context = "\n".join(
        f"- {s['name']} (confidence: {s['confidence']}, momentum: {s['momentum']})"
        for s in payload["scenarios"]
    )

    sections = {}

    if dev_context.strip():
        sections["Key Developments"] = draft_brief_section(
            "Key Developments",
            f"Theme: {theme_name}\nFocal question: {focal_question}\n\nDevelopments:\n{dev_context}",
        )

    if change_context.strip():
        sections["What's Changing"] = draft_brief_section(
            "What's Changing",
            f"Theme: {theme_name}\n\nRecent shifts:\n{change_context}",
        )

    if scenario_context.strip():
        sections["Why It Matters"] = draft_brief_section(
            "Why It Matters",
            f"Theme: {theme_name}\nFocal question: {focal_question}\n\nScenario state:\n{scenario_context}",
        )

    if sections:
        sections["Implications"] = draft_brief_section(
            "Implications",
            f"Theme: {theme_name}\n\nKey signals:\n{dev_context}\n\nScenario state:\n{scenario_context}",
        )
        sections["Recommended Actions"] = draft_brief_section(
            "Recommended Actions",
            f"Theme: {theme_name}\nFocal question: {focal_question}\n\nImplications context:\n"
            + sections.get("Implications", ""),
        )

    if not sections:
        return "Insufficient data for this period. No relevant signals were detected."

    lines = [f"# Strategic Brief: {theme_name}\n"]
    for heading, content in sections.items():
        lines.append(f"## {heading}\n{content}\n")
    return "\n".join(lines)


# ---------- Job entry point (called by RQ worker) ----------

def generate_brief_job(theme_id: str, brief_id: str):
    db = SessionLocal()
    try:
        brief = db.get(Brief, brief_id)
        theme = db.get(Theme, theme_id)
        if not brief or not theme:
            return

        period_start = brief.period_start or (date.today() - timedelta(days=7))
        period_end = brief.period_end or date.today()

        # Pull elevated signal IDs from the most recent completed run's change notes
        import json as _json
        from app.models.crawl import CrawlRun
        last_run = (
            db.query(CrawlRun)
            .filter(CrawlRun.theme_id == theme.id, CrawlRun.status == "completed")
            .order_by(CrawlRun.completed_at.desc())
            .first()
        )
        elevated_ids: list[str] = []
        if last_run and last_run.notes:
            try:
                change_data = _json.loads(last_run.notes)
                elevated_ids = change_data.get("new_signal_ids", [])
            except (ValueError, TypeError):
                pass

        top_signals = _select_top_signals(db, theme.id, period_start, period_end)
        changed_signals = _select_changed_signals(
            db, theme.id, period_start, period_end, elevated_signal_ids=elevated_ids
        )
        scenarios = _select_active_scenarios(db, theme.id)

        payload = _build_structured_payload(theme, top_signals, changed_signals, scenarios)

        try:
            rendered = _generate_prose(payload)
            brief.status = "completed"
        except Exception as e:
            # Graceful degradation: save structured payload, mark partial
            rendered = f"[LLM generation failed: {e}]\n\nStructured data was assembled successfully."
            brief.status = "completed"

        brief.structured_payload_json = payload
        brief.rendered_text = rendered
        db.commit()
    finally:
        db.close()
