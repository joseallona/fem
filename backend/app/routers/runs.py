import statistics
from datetime import datetime, timezone
from typing import List
from uuid import UUID

import redis as redis_lib
from fastapi import APIRouter, Depends, HTTPException, status
from rq import Queue
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.crawl import CrawlRun
from app.models.theme import Theme
from app.schemas.run import RunOut
from app.services.pipeline import run_monitoring_pipeline

router = APIRouter(tags=["runs"])

FALLBACK_ESTIMATE_SECONDS = 120  # shown when no history exists


def _estimate_duration(db: Session, theme_id: UUID) -> int:
    """Return median duration of past completed runs, or a fallback."""
    completed = (
        db.query(CrawlRun)
        .filter(
            CrawlRun.theme_id == theme_id,
            CrawlRun.status == "completed",
            CrawlRun.completed_at.isnot(None),
        )
        .order_by(CrawlRun.started_at.desc())
        .limit(10)
        .all()
    )
    durations = [
        int((r.completed_at - r.started_at).total_seconds())
        for r in completed
        if r.completed_at and r.started_at and r.completed_at > r.started_at
    ]
    if durations:
        return int(statistics.median(durations))
    return FALLBACK_ESTIMATE_SECONDS


def _enrich(run: CrawlRun, estimated: int) -> RunOut:
    out = RunOut.model_validate(run)
    return out.model_copy(update={"estimated_duration_seconds": estimated})


@router.get("/themes/{theme_id}/runs", response_model=List[RunOut])
def list_runs(theme_id: UUID, db: Session = Depends(get_db)):
    if not db.get(Theme, theme_id):
        raise HTTPException(status_code=404, detail="Theme not found")
    runs = (
        db.query(CrawlRun)
        .filter(CrawlRun.theme_id == theme_id)
        .order_by(CrawlRun.started_at.desc())
        .limit(20)
        .all()
    )
    estimated = _estimate_duration(db, theme_id)
    return [_enrich(r, estimated) for r in runs]


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: UUID, db: Session = Depends(get_db)):
    run = db.get(CrawlRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    estimated = _estimate_duration(db, run.theme_id)
    return _enrich(run, estimated)


@router.post("/themes/{theme_id}/runs/trigger", response_model=RunOut, status_code=status.HTTP_202_ACCEPTED)
def trigger_run(theme_id: UUID, db: Session = Depends(get_db)):
    theme = db.get(Theme, theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    active = db.query(CrawlRun).filter(
        CrawlRun.theme_id == theme_id, CrawlRun.status == "running"
    ).first()
    if active:
        raise HTTPException(status_code=409, detail="A run is already active for this theme")
    run = CrawlRun(theme_id=theme_id, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        r = redis_lib.from_url(settings.REDIS_URL)
        q = Queue("fem-jobs", connection=r)
        q.enqueue(run_monitoring_pipeline, str(theme_id), str(run.id), job_timeout=3600)
    except Exception as exc:
        # Roll back the run record so it doesn't linger as "running"
        run.status = "failed"
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=503, detail=f"Could not enqueue pipeline job: {exc}")
    estimated = _estimate_duration(db, theme_id)
    return _enrich(run, estimated)


@router.post("/runs/{run_id}/cancel", response_model=RunOut)
def cancel_run(run_id: UUID, db: Session = Depends(get_db)):
    run = db.get(CrawlRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != "running":
        raise HTTPException(status_code=409, detail=f"Run is not active (status: {run.status})")
    run.status = "cancelled"
    run.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    estimated = _estimate_duration(db, run.theme_id)
    return _enrich(run, estimated)
