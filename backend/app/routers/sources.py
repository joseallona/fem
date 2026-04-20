from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.source import Source
from app.models.theme import Theme
from app.schemas.source import SourceCreate, SourceOut, SourceUpdate


class SourceStats(BaseModel):
    docs_fetched: int
    signals_yielded: int
    yield_rate: float       # signals / docs_fetched (0–1)
    avg_importance: float   # avg importance_score of yielded signals

router = APIRouter(tags=["sources"])


def _get_theme_or_404(theme_id: UUID, db: Session) -> Theme:
    theme = db.get(Theme, theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    return theme


def _validate_url(url: str) -> str:
    """Normalize and reachability-check a URL. Raises 422 on failure."""
    from app.services.crawler import validate_url
    try:
        return validate_url(url)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/themes/{theme_id}/sources", response_model=List[SourceOut])
def list_sources(
    theme_id: UUID,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    _get_theme_or_404(theme_id, db)
    q = db.query(Source).filter(Source.theme_id == theme_id)
    if status:
        q = q.filter(Source.status == status)
    return q.order_by(Source.relevance_score.desc()).all()


@router.post("/themes/{theme_id}/sources", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
def add_source(theme_id: UUID, body: SourceCreate, db: Session = Depends(get_db)):
    _get_theme_or_404(theme_id, db)

    # Normalize + validate the URL
    normalized_url = _validate_url(body.url)

    # Reject duplicates within this theme
    existing = db.query(Source).filter(
        Source.theme_id == theme_id, Source.url == normalized_url
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="This URL is already tracked for this theme.")

    domain = body.domain or urlparse(normalized_url).netloc
    name = body.name or domain

    source = Source(
        theme_id=theme_id,
        domain=domain,
        name=name,
        url=normalized_url,
        source_type=body.source_type,
        discovery_mode=body.discovery_mode,
        crawl_frequency=body.crawl_frequency,
        relevance_score=body.relevance_score,
        trust_score=body.trust_score,
        status=body.status,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.get("/sources/{source_id}", response_model=SourceOut)
def get_source(source_id: UUID, db: Session = Depends(get_db)):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.patch("/sources/{source_id}", response_model=SourceOut)
def update_source(source_id: UUID, body: SourceUpdate, db: Session = Depends(get_db)):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(source, field, value)
    db.commit()
    db.refresh(source)
    return source


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: UUID, db: Session = Depends(get_db)):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    db.delete(source)
    db.commit()


@router.get("/themes/{theme_id}/source-stats", response_model=Dict[str, SourceStats])
def get_source_stats(theme_id: UUID, db: Session = Depends(get_db)):
    """
    Per-source document and signal yield stats for a theme.
    Returns {source_id: {docs_fetched, signals_yielded, yield_rate, avg_importance}}.
    """
    from app.models.crawl import RawDocument
    from app.models.signal import Signal

    _get_theme_or_404(theme_id, db)

    source_ids = [
        row[0] for row in db.query(Source.id).filter(Source.theme_id == theme_id).all()
    ]

    doc_counts: dict[UUID, int] = dict(
        db.query(RawDocument.source_id, sqlfunc.count(RawDocument.id))
        .filter(RawDocument.source_id.in_(source_ids))
        .group_by(RawDocument.source_id)
        .all()
    )

    signal_counts: dict[UUID, int] = dict(
        db.query(Signal.source_id, sqlfunc.count(Signal.id))
        .filter(Signal.theme_id == theme_id, Signal.source_id.in_(source_ids))
        .group_by(Signal.source_id)
        .all()
    )

    avg_importance: dict[UUID, float] = dict(
        db.query(Signal.source_id, sqlfunc.avg(Signal.importance_score))
        .filter(Signal.theme_id == theme_id, Signal.source_id.in_(source_ids))
        .group_by(Signal.source_id)
        .all()
    )

    result: dict[str, SourceStats] = {}
    for sid in source_ids:
        docs = doc_counts.get(sid, 0)
        signals = signal_counts.get(sid, 0)
        result[str(sid)] = SourceStats(
            docs_fetched=docs,
            signals_yielded=signals,
            yield_rate=round(signals / docs, 3) if docs > 0 else 0.0,
            avg_importance=round(float(avg_importance.get(sid) or 0.0), 3),
        )

    return result


@router.post("/themes/{theme_id}/source-discovery/async", response_model=Dict[str, Any], status_code=status.HTTP_202_ACCEPTED)
def discover_sources_async(theme_id: UUID, db: Session = Depends(get_db)):
    """Enqueue source discovery as a background job. Returns {job_id, status} immediately."""
    _get_theme_or_404(theme_id, db)
    try:
        import redis as redis_lib
        from rq import Queue
        from app.core.config import settings
        from app.services.auto_discovery import run_auto_discovery
        r = redis_lib.from_url(settings.REDIS_URL)
        q = Queue("fem-jobs", connection=r)
        job = q.enqueue(run_auto_discovery, str(theme_id), job_timeout=1800)
        return {"job_id": job.id, "status": "queued"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not enqueue discovery job: {exc}")


@router.post("/themes/{theme_id}/source-discovery", response_model=List[SourceOut])
def discover_sources(
    theme_id: UUID,
    use_llm: bool = True,
    db: Session = Depends(get_db),
):
    theme = _get_theme_or_404(theme_id, db)
    existing = db.query(Source).filter(Source.theme_id == theme_id).all()
    existing_urls = {s.url for s in existing if s.url}

    from app.services.source_discovery import discover_sources as _discover
    candidates = _discover(
        theme_name=theme.name,
        primary_subject=theme.primary_subject,
        related_subjects=theme.related_subjects_json or [],
        focal_question=theme.focal_question,
        existing_domains=set(),  # don't filter by domain — URL-level dedup happens on save
        use_llm=use_llm,
        limit=50,
    )

    created = []
    for c in candidates:
        if c.get("url") in existing_urls:
            continue
        source = Source(theme_id=theme_id, **c)
        db.add(source)
        db.flush()
        created.append(source)
        existing_urls.add(c["url"])

    db.commit()
    for s in created:
        db.refresh(s)
    return created
