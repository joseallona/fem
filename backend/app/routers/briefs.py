from datetime import date
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.brief import Brief
from app.models.theme import Theme
from app.schemas.brief import BriefGenerateRequest, BriefOut

router = APIRouter(tags=["briefs"])


@router.post(
    "/themes/{theme_id}/briefs/generate",
    response_model=BriefOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_brief(theme_id: UUID, body: BriefGenerateRequest, db: Session = Depends(get_db)):
    theme = db.get(Theme, theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    today = date.today()
    brief = Brief(
        theme_id=theme_id,
        generation_mode=body.generation_mode,
        period_start=body.period_start or today,
        period_end=body.period_end or today,
        status="generating",
        structured_payload_json={},
    )
    db.add(brief)
    db.commit()
    db.refresh(brief)
    # Enqueue background job
    import redis
    from rq import Queue
    from app.core.config import settings
    from app.services.brief_service import generate_brief_job
    r = redis.from_url(settings.REDIS_URL)
    q = Queue("fem-jobs", connection=r)
    q.enqueue(generate_brief_job, str(theme_id), str(brief.id))
    return brief


@router.get("/themes/{theme_id}/briefs", response_model=List[BriefOut])
def list_briefs(theme_id: UUID, db: Session = Depends(get_db)):
    if not db.get(Theme, theme_id):
        raise HTTPException(status_code=404, detail="Theme not found")
    return (
        db.query(Brief)
        .filter(Brief.theme_id == theme_id)
        .order_by(Brief.created_at.desc())
        .all()
    )


@router.get("/themes/{theme_id}/briefs/latest", response_model=BriefOut)
def get_latest_brief(theme_id: UUID, db: Session = Depends(get_db)):
    if not db.get(Theme, theme_id):
        raise HTTPException(status_code=404, detail="Theme not found")
    brief = (
        db.query(Brief)
        .filter(Brief.theme_id == theme_id, Brief.status == "completed")
        .order_by(Brief.created_at.desc())
        .first()
    )
    if not brief:
        raise HTTPException(status_code=404, detail="No completed brief found")
    return brief


@router.get("/briefs/{brief_id}", response_model=BriefOut)
def get_brief(brief_id: UUID, db: Session = Depends(get_db)):
    brief = db.get(Brief, brief_id)
    if not brief:
        raise HTTPException(status_code=404, detail="Brief not found")
    return brief


@router.patch("/briefs/{brief_id}", response_model=BriefOut)
def update_brief(brief_id: UUID, rendered_text: str, db: Session = Depends(get_db)):
    brief = db.get(Brief, brief_id)
    if not brief:
        raise HTTPException(status_code=404, detail="Brief not found")
    brief.rendered_text = rendered_text
    db.commit()
    db.refresh(brief)
    return brief
