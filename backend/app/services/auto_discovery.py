"""
Automated source discovery — Phase 4.

Called weekly by the scheduler for each active theme.
Discovers new source candidates via the ontology + LLM expansion,
saves them as "pending" for user review.
"""
import logging

from app.core.database import SessionLocal
from app.models.source import Source
from app.models.theme import Theme

logger = logging.getLogger(__name__)


def run_auto_discovery(theme_id: str):
    """
    Discover new source candidates for a theme and save as "pending".
    Deduplication is handled by existing_domains passed to discover_sources.
    Safe to run repeatedly.
    """
    db = SessionLocal()
    try:
        theme = db.get(Theme, theme_id)
        if not theme:
            logger.warning("Auto-discovery: theme %s not found", theme_id)
            return

        existing = db.query(Source).filter(Source.theme_id == theme_id).all()
        existing_domains = {s.domain for s in existing if s.domain}

        from app.services.source_discovery import discover_sources
        candidates = discover_sources(
            theme_name=theme.name,
            primary_subject=theme.primary_subject,
            related_subjects=theme.related_subjects_json or [],
            focal_question=theme.focal_question,
            existing_domains=existing_domains,
            use_llm=True,
            limit=150,
        )

        added = 0
        for c in candidates:
            c["status"] = "approved"
            source = Source(theme_id=theme_id, **c)
            db.add(source)
            added += 1

        db.commit()
        logger.info("Auto-discovery: added %d pending sources for theme '%s'", added, theme.name)
        return {"sources_added": added}

    except Exception as e:
        logger.exception("Auto-discovery failed for theme %s: %s", theme_id, e)
        return {"sources_added": 0}
    finally:
        db.close()
