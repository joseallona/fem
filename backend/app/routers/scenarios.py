from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.scenario import Scenario
from app.models.signal import Signal, SignalScenario
from app.models.theme import Theme
from app.schemas.scenario import ScenarioCreate, ScenarioOut, ScenarioUpdate, SignalLinkCreate, SignalLinkOut

router = APIRouter(tags=["scenarios"])


def _get_theme_or_404(theme_id: UUID, db: Session) -> Theme:
    theme = db.get(Theme, theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    return theme


@router.get("/themes/{theme_id}/scenarios", response_model=List[ScenarioOut])
def list_scenarios(theme_id: UUID, db: Session = Depends(get_db)):
    _get_theme_or_404(theme_id, db)
    return db.query(Scenario).filter(Scenario.theme_id == theme_id).all()


@router.post("/themes/{theme_id}/scenarios", response_model=ScenarioOut, status_code=status.HTTP_201_CREATED)
def create_scenario(theme_id: UUID, body: ScenarioCreate, db: Session = Depends(get_db)):
    _get_theme_or_404(theme_id, db)
    scenario = Scenario(theme_id=theme_id, **body.model_dump())
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return scenario


@router.get("/scenarios/{scenario_id}", response_model=ScenarioOut)
def get_scenario(scenario_id: UUID, db: Session = Depends(get_db)):
    scenario = db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario


@router.patch("/scenarios/{scenario_id}", response_model=ScenarioOut)
def update_scenario(scenario_id: UUID, body: ScenarioUpdate, db: Session = Depends(get_db)):
    scenario = db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(scenario, field, value)
    db.commit()
    db.refresh(scenario)
    return scenario


@router.delete("/scenarios/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(scenario_id: UUID, db: Session = Depends(get_db)):
    scenario = db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    db.delete(scenario)
    db.commit()


@router.post("/scenarios/{scenario_id}/signals", status_code=status.HTTP_204_NO_CONTENT)
def link_signal(scenario_id: UUID, body: SignalLinkCreate, db: Session = Depends(get_db)):
    if not db.get(Scenario, scenario_id):
        raise HTTPException(status_code=404, detail="Scenario not found")
    if not db.get(Signal, body.signal_id):
        raise HTTPException(status_code=404, detail="Signal not found")
    existing = db.query(SignalScenario).filter_by(
        signal_id=body.signal_id, scenario_id=scenario_id
    ).first()
    if existing:
        existing.relationship_type = body.relationship_type
        existing.relationship_score = body.relationship_score
        existing.explanation_text = body.explanation_text
        existing.user_confirmed = body.user_confirmed
    else:
        db.add(SignalScenario(scenario_id=scenario_id, **body.model_dump()))
    db.commit()


@router.get("/scenarios/{scenario_id}/signals", response_model=List[SignalLinkOut])
def list_scenario_signals(scenario_id: UUID, db: Session = Depends(get_db)):
    if not db.get(Scenario, scenario_id):
        raise HTTPException(status_code=404, detail="Scenario not found")
    links = db.query(SignalScenario).filter(SignalScenario.scenario_id == scenario_id).all()
    result = []
    for link in links:
        signal = db.get(Signal, link.signal_id)
        result.append(SignalLinkOut(
            signal_id=link.signal_id,
            scenario_id=link.scenario_id,
            relationship_type=link.relationship_type,
            relationship_score=link.relationship_score,
            user_confirmed=link.user_confirmed,
            explanation_text=link.explanation_text,
            signal_title=signal.title if signal else None,
            signal_type=signal.signal_type if signal else None,
            steep_category=signal.steep_category if signal else None,
            horizon=signal.horizon if signal else None,
            importance_score=signal.importance_score if signal else None,
            source_url=signal.source_url if signal else None,  # prefers raw_document.url over source.url
        ))
    return result


@router.delete("/scenarios/{scenario_id}/signals/{signal_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_signal(scenario_id: UUID, signal_id: UUID, db: Session = Depends(get_db)):
    link = db.query(SignalScenario).filter_by(signal_id=signal_id, scenario_id=scenario_id).first()
    if link:
        db.delete(link)
        db.commit()
