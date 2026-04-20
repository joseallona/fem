"""
Signal Archive — persistent, cross-reset historical signal store.

Uses a separate SQLite database so it survives theme resets, deletions,
and any changes to the main PostgreSQL schema.

Schema (single table):
  archived_signals(
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    url           TEXT,          -- source URL the document came from
    title         TEXT NOT NULL,
    summary       TEXT,
    theme_name    TEXT NOT NULL, -- theme name at time of extraction (denormalised)
    relevance_reason TEXT,       -- why the LLM considered this related to the theme
    archived_at   DATETIME DEFAULT CURRENT_TIMESTAMP
  )

Deduplication: (url, theme_name) pair — same URL can appear under different themes.
"""
import logging
import os
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, Text, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)

# Path to the SQLite file — from env var, then settings, then local fallback.
_DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "../../../../signal_archive.db")
try:
    from app.core.config import settings as _settings
    ARCHIVE_PATH = os.environ.get("SIGNAL_ARCHIVE_PATH", _settings.SIGNAL_ARCHIVE_PATH)
except Exception:
    ARCHIVE_PATH = os.environ.get("SIGNAL_ARCHIVE_PATH", os.path.abspath(_DEFAULT_PATH))

_engine = None
_SessionLocal = None


def _get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine(
            f"sqlite:///{ARCHIVE_PATH}",
            connect_args={"check_same_thread": False},
        )
        _SessionLocal = sessionmaker(bind=_engine)
        _ensure_table(_engine)
    return _engine


def _ensure_table(engine):
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS archived_signals (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                url              TEXT,
                title            TEXT NOT NULL,
                summary          TEXT,
                theme_name       TEXT NOT NULL,
                relevance_reason TEXT,
                archived_at      TEXT NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS ix_archived_signals_url_theme
            ON archived_signals (url, theme_name)
            WHERE url IS NOT NULL
        """))
        conn.commit()


def archive_signal(
    *,
    url: str | None,
    title: str,
    summary: str | None,
    theme_name: str,
    relevance_reason: str | None,
) -> bool:
    """
    Save a signal to the archive. Silently skips duplicates (same url + theme).
    Returns True if inserted, False if skipped or on error.
    """
    try:
        engine = _get_engine()
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT OR IGNORE INTO archived_signals
                        (url, title, summary, theme_name, relevance_reason, archived_at)
                    VALUES
                        (:url, :title, :summary, :theme_name, :relevance_reason, :archived_at)
                """),
                {
                    "url": url,
                    "title": title[:500],
                    "summary": (summary or "")[:1000],
                    "theme_name": theme_name,
                    "relevance_reason": (relevance_reason or "")[:500],
                    "archived_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            conn.commit()
            return True
    except Exception as e:
        logger.warning("Signal archive write failed: %s", e)
        return False


def query_archive(
    theme_name: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """Return archived signals, optionally filtered by theme_name."""
    try:
        engine = _get_engine()
        with engine.connect() as conn:
            if theme_name:
                rows = conn.execute(
                    text("""
                        SELECT id, url, title, summary, theme_name, relevance_reason, archived_at
                        FROM archived_signals
                        WHERE theme_name = :theme
                        ORDER BY archived_at DESC
                        LIMIT :limit OFFSET :offset
                    """),
                    {"theme": theme_name, "limit": limit, "offset": offset},
                ).fetchall()
            else:
                rows = conn.execute(
                    text("""
                        SELECT id, url, title, summary, theme_name, relevance_reason, archived_at
                        FROM archived_signals
                        ORDER BY archived_at DESC
                        LIMIT :limit OFFSET :offset
                    """),
                    {"limit": limit, "offset": offset},
                ).fetchall()
            return [dict(r._mapping) for r in rows]
    except Exception as e:
        logger.warning("Signal archive query failed: %s", e)
        return []


def count_archive(theme_name: str | None = None) -> int:
    """Return total archived signal count, optionally filtered by theme."""
    try:
        engine = _get_engine()
        with engine.connect() as conn:
            if theme_name:
                row = conn.execute(
                    text("SELECT COUNT(*) FROM archived_signals WHERE theme_name = :theme"),
                    {"theme": theme_name},
                ).fetchone()
            else:
                row = conn.execute(
                    text("SELECT COUNT(*) FROM archived_signals"),
                ).fetchone()
            return row[0] if row else 0
    except Exception as e:
        logger.warning("Signal archive count failed: %s", e)
        return 0
