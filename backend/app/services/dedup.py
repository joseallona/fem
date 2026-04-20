"""
Deduplication — Stage 5.

Deterministic methods only (per Decision Logic Specification):
1. Exact content hash match
2. Normalized title similarity > 0.9
3. Canonical URL match
"""
import logging
import re

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app.models.crawl import RawDocument

logger = logging.getLogger(__name__)


def _normalize_title(title: str) -> str:
    title = title.lower().strip()
    title = re.sub(r"[^\w\s]", "", title)
    title = re.sub(r"\s+", " ", title)
    return title


def is_duplicate(db: Session, content_hash: str, canonical_url: str, title: str) -> bool:
    # 1. Exact hash
    if db.query(RawDocument).filter(RawDocument.content_hash == content_hash).first():
        logger.debug("Duplicate by hash: %s", content_hash[:12])
        return True

    # 2. Canonical URL
    if canonical_url and db.query(RawDocument).filter(RawDocument.canonical_url == canonical_url).first():
        logger.debug("Duplicate by URL: %s", canonical_url)
        return True

    # 3. Title similarity — check against recent docs (last 500)
    if title:
        norm = _normalize_title(title)
        recent = (
            db.query(RawDocument.title)
            .filter(RawDocument.title.isnot(None))
            .order_by(RawDocument.fetched_at.desc())
            .limit(500)
            .all()
        )
        for (existing_title,) in recent:
            if existing_title and fuzz.ratio(_normalize_title(existing_title), norm) > 90:
                logger.debug("Duplicate by title similarity: %s", title[:60])
                return True

    return False
