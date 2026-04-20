from typing import List
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.source import Source
from app.models.theme import Theme
from app.schemas.theme import ThemeCreate, ThemeOut, ThemeUpdate

router = APIRouter(prefix="/themes", tags=["themes"])

# Sources added automatically to every new theme
DEFAULT_SOURCES = [
    {
        "name": "Future Resources Repository",
        "url": "https://lydiacaldana.notion.site/Future-Resources-Repository-3deb0e6d2b0d4290aa9e00c500ab45f7",
        "domain": "lydiacaldana.notion.site",
        "source_type": "web",
        "status": "approved",
        "relevance_score": 0.85,
        "trust_score": 0.80,
    },
]


@router.post("", response_model=ThemeOut, status_code=status.HTTP_201_CREATED)
def create_theme(body: ThemeCreate, db: Session = Depends(get_db)):
    theme = Theme(**body.model_dump())
    db.add(theme)
    db.flush()

    for s in DEFAULT_SOURCES:
        db.add(Source(theme_id=theme.id, **s))

    db.commit()
    db.refresh(theme)
    return theme


@router.get("", response_model=List[ThemeOut])
def list_themes(db: Session = Depends(get_db)):
    return db.query(Theme).order_by(Theme.created_at.desc()).all()


@router.get("/{theme_id}", response_model=ThemeOut)
def get_theme(theme_id: UUID, db: Session = Depends(get_db)):
    theme = db.get(Theme, theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    return theme


@router.patch("/{theme_id}", response_model=ThemeOut)
def update_theme(theme_id: UUID, body: ThemeUpdate, db: Session = Depends(get_db)):
    theme = db.get(Theme, theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(theme, field, value)
    db.commit()
    db.refresh(theme)
    return theme


@router.delete("/{theme_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_theme(theme_id: UUID, db: Session = Depends(get_db)):
    theme = db.get(Theme, theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    db.delete(theme)
    db.commit()


@router.post("/{theme_id}/reset", status_code=status.HTTP_204_NO_CONTENT)
def reset_theme(theme_id: UUID, db: Session = Depends(get_db)):
    """Delete all generated data for a theme (signals, trends, drivers, scenarios,
    scenario axes/drafts, briefs, runs) while keeping the theme and its sources."""
    theme = db.get(Theme, theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    for rel in (
        "signals", "trends", "drivers", "scenarios",
        "scenario_axes", "scenario_drafts", "briefs", "crawl_runs",
    ):
        for obj in list(getattr(theme, rel)):
            db.delete(obj)
    db.commit()


@router.post("/{theme_id}/reset-scenarios", status_code=status.HTTP_204_NO_CONTENT)
def reset_scenarios(theme_id: UUID, db: Session = Depends(get_db)):
    """Delete only scenario-layer data (axes, drafts, approved scenarios, briefs)
    while keeping signals, trends, and drivers intact."""
    theme = db.get(Theme, theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    for rel in ("scenarios", "scenario_axes", "scenario_drafts", "briefs"):
        for obj in list(getattr(theme, rel)):
            db.delete(obj)
    db.commit()


@router.post("/{theme_id}/activate", response_model=ThemeOut)
def activate_theme(theme_id: UUID, db: Session = Depends(get_db)):
    theme = db.get(Theme, theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    theme.status = "active"
    db.commit()
    db.refresh(theme)
    try:
        from app.services.scheduler import setup_daily_schedules
        setup_daily_schedules()
    except Exception:
        pass
    return theme
