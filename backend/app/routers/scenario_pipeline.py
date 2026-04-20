"""
Scenario Pipeline Router.

Endpoints for the automated scenario generation pipeline including
the two human-in-the-loop review gates.

Gate 1 — Axis Review:
  GET  /themes/{id}/scenario-pipeline/status       → current pipeline state
  GET  /themes/{id}/trends                          → synthesized trends
  GET  /themes/{id}/drivers                         → extracted drivers
  GET  /themes/{id}/scenario-axes                   → proposed axes
  PATCH /scenario-axes/{axis_id}                    → edit axis poles
  POST /themes/{id}/scenario-axes/confirm           → Gate 1: confirm axes → triggers scenario generation

Gate 2 — Draft Review:
  GET  /themes/{id}/scenario-drafts                 → draft scenarios
  PATCH /scenario-drafts/{draft_id}                 → edit draft
  POST /scenario-drafts/{draft_id}/approve          → Gate 2: approve → promote to live scenario
  POST /scenario-drafts/{draft_id}/reject           → reject draft
  POST /themes/{id}/scenario-drafts/approve-all     → approve all pending drafts

Monitoring:
  GET  /themes/{id}/scenario-monitoring             → monitoring status + alerts
  GET  /scenarios/{id}/indicators                   → indicators for a scenario
"""
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.scenario import Scenario
from app.models.scenario_pipeline import ScenarioAxis, ScenarioDraft, ScenarioIndicator
from app.models.theme import Theme
from app.models.trend import Driver, Trend
from app.schemas.scenario_pipeline import (
    DriverOut,
    PipelineStatusOut,
    ScenarioAxisOut,
    ScenarioAxisUpdate,
    ScenarioDraftOut,
    ScenarioDraftUpdate,
    ScenarioIndicatorOut,
    TrendOut,
)

router = APIRouter(tags=["scenario-pipeline"])
logger = logging.getLogger(__name__)


def _get_theme_or_404(theme_id: UUID, db: Session) -> Theme:
    theme = db.get(Theme, theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    return theme


# ── Pipeline Status ────────────────────────────────────────────────────────

@router.get("/themes/{theme_id}/scenario-pipeline/status", response_model=PipelineStatusOut)
def get_pipeline_status(theme_id: UUID, db: Session = Depends(get_db)):
    _get_theme_or_404(theme_id, db)

    trend_count = db.query(Trend).filter(Trend.theme_id == theme_id).count()
    driver_count = db.query(Driver).filter(Driver.theme_id == theme_id).count()
    axes = db.query(ScenarioAxis).filter(ScenarioAxis.theme_id == theme_id).order_by(ScenarioAxis.axis_number).all()
    draft_count = db.query(ScenarioDraft).filter(ScenarioDraft.theme_id == theme_id).count()
    drafts_approved = db.query(ScenarioDraft).filter(
        ScenarioDraft.theme_id == theme_id, ScenarioDraft.status == "approved"
    ).count()
    live_scenario_count = db.query(Scenario).filter(Scenario.theme_id == theme_id).count()
    has_indicators = db.query(ScenarioIndicator).filter(ScenarioIndicator.theme_id == theme_id).first() is not None

    # Derive pipeline state
    confirmed_axes = [a for a in axes if a.user_confirmed]
    if trend_count == 0:
        state = "no_data"
    elif len(axes) == 0:
        state = "trends_ready"
    elif len(confirmed_axes) < 2:
        state = "axes_pending"
    elif draft_count == 0:
        state = "axes_confirmed"
    elif drafts_approved < draft_count:
        state = "scenarios_pending"
    else:
        state = "monitoring"

    # Collect recent monitoring alerts from scenario notes (stored in scenario recent_delta field)
    alerts: list[dict] = []

    return PipelineStatusOut(
        state=state,
        trend_count=trend_count,
        driver_count=driver_count,
        axes=[ScenarioAxisOut.model_validate(a) for a in axes],
        draft_count=draft_count,
        drafts_approved=drafts_approved,
        live_scenario_count=live_scenario_count,
        monitoring_active=has_indicators,
        alerts=alerts,
    )


# ── Trends ─────────────────────────────────────────────────────────────────

@router.get("/themes/{theme_id}/trends", response_model=list[TrendOut])
def list_trends(theme_id: UUID, db: Session = Depends(get_db)):
    _get_theme_or_404(theme_id, db)
    return db.query(Trend).filter(Trend.theme_id == theme_id).order_by(Trend.momentum.desc()).all()


# ── Drivers ────────────────────────────────────────────────────────────────

@router.get("/themes/{theme_id}/drivers", response_model=list[DriverOut])
def list_drivers(theme_id: UUID, db: Session = Depends(get_db)):
    _get_theme_or_404(theme_id, db)
    return (
        db.query(Driver)
        .filter(Driver.theme_id == theme_id)
        .order_by((Driver.impact_score * Driver.uncertainty_score).desc())
        .all()
    )


# ── Scenario Axes (Gate 1) ─────────────────────────────────────────────────

@router.get("/themes/{theme_id}/scenario-axes", response_model=list[ScenarioAxisOut])
def list_axes(theme_id: UUID, db: Session = Depends(get_db)):
    _get_theme_or_404(theme_id, db)
    return db.query(ScenarioAxis).filter(ScenarioAxis.theme_id == theme_id).order_by(ScenarioAxis.axis_number).all()


@router.patch("/scenario-axes/{axis_id}", response_model=ScenarioAxisOut)
def update_axis(axis_id: UUID, body: ScenarioAxisUpdate, db: Session = Depends(get_db)):
    axis = db.get(ScenarioAxis, axis_id)
    if not axis:
        raise HTTPException(status_code=404, detail="Axis not found")

    patch = body.model_dump(exclude_none=True)
    content_fields = {"driver_name", "pole_low", "pole_high", "rationale"}
    if axis.user_confirmed and (patch.keys() & content_fields):
        raise HTTPException(status_code=409, detail="Cannot edit pole labels on a confirmed axis")

    for field, value in patch.items():
        setattr(axis, field, value)
    db.commit()
    db.refresh(axis)
    return axis


@router.post("/themes/{theme_id}/scenario-axes/confirm", status_code=status.HTTP_202_ACCEPTED)
def confirm_axes(theme_id: UUID, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Gate 1: User confirms the proposed axes.
    Marks both axes as confirmed and enqueues scenario draft generation.
    """
    _get_theme_or_404(theme_id, db)

    axes = db.query(ScenarioAxis).filter(ScenarioAxis.theme_id == theme_id).all()
    if len(axes) < 2:
        raise HTTPException(status_code=409, detail="No axes proposed yet — run the pipeline first")

    already_confirmed = all(a.user_confirmed for a in axes)
    if already_confirmed:
        raise HTTPException(status_code=409, detail="Axes already confirmed")

    now = datetime.now(timezone.utc)
    for axis in axes:
        axis.user_confirmed = True
        axis.confirmed_at = now
    db.commit()

    # Enqueue scenario generation as a background task
    background_tasks.add_task(_generate_scenarios_bg, str(theme_id))

    return {"message": "Axes confirmed. Scenario drafts are being generated.", "theme_id": str(theme_id)}


@router.post("/themes/{theme_id}/scenario-axes/rebuild", status_code=status.HTTP_202_ACCEPTED)
def rebuild_axes(theme_id: UUID, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    On-demand matrix rebuild.
    Deletes all non-locked axes and re-proposes axes from signal evidence.
    Locked axes are always preserved and count toward the two slots.
    Previously generated scenarios and drafts are not modified.
    """
    _get_theme_or_404(theme_id, db)

    non_locked = db.query(ScenarioAxis).filter(
        ScenarioAxis.theme_id == theme_id,
        ScenarioAxis.axis_locked == False,  # noqa: E712
    ).all()
    for axis in non_locked:
        db.delete(axis)
    db.commit()

    background_tasks.add_task(_rebuild_axes_bg, str(theme_id))
    return {"message": "Matrix rebuild started.", "theme_id": str(theme_id)}


def _rebuild_axes_bg(theme_id: str):
    """Background task: re-propose axes after non-locked axes are cleared."""
    from app.core.database import SessionLocal
    from app.services.axis_selector import run_axis_selection
    from uuid import UUID as _UUID
    db = SessionLocal()
    try:
        run_axis_selection(_UUID(theme_id), db, force=True)
    except Exception as e:
        logger.error("Background axis rebuild failed for theme %s: %s", theme_id, e)
    finally:
        db.close()


def _generate_scenarios_bg(theme_id: str):
    """Background task: generate 4 scenario drafts."""
    from app.core.database import SessionLocal
    from app.services.scenario_generator import run_scenario_generation
    db = SessionLocal()
    try:
        run_scenario_generation(theme_id, db)
    except Exception as e:
        logger.error("Background scenario generation failed for theme %s: %s", theme_id, e)
    finally:
        db.close()


# ── Scenario Drafts (Gate 2) ───────────────────────────────────────────────

@router.get("/themes/{theme_id}/scenario-drafts", response_model=list[ScenarioDraftOut])
def list_drafts(theme_id: UUID, db: Session = Depends(get_db)):
    _get_theme_or_404(theme_id, db)
    return db.query(ScenarioDraft).filter(ScenarioDraft.theme_id == theme_id).order_by(ScenarioDraft.quadrant).all()


@router.patch("/scenario-drafts/{draft_id}", response_model=ScenarioDraftOut)
def update_draft(draft_id: UUID, body: ScenarioDraftUpdate, db: Session = Depends(get_db)):
    draft = db.get(ScenarioDraft, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft.status == "approved":
        raise HTTPException(status_code=409, detail="Cannot edit an approved draft")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(draft, field, value)
    db.commit()
    db.refresh(draft)
    return draft


@router.post("/scenario-drafts/{draft_id}/approve", response_model=ScenarioDraftOut)
def approve_draft(draft_id: UUID, db: Session = Depends(get_db)):
    """
    Gate 2: Approve a single scenario draft.
    Promotes it to a live Scenario and creates its ScenarioIndicator records.
    """
    draft = db.get(ScenarioDraft, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft.status == "approved":
        raise HTTPException(status_code=409, detail="Draft already approved")
    if draft.status == "rejected":
        raise HTTPException(status_code=409, detail="Cannot approve a rejected draft")

    _promote_draft(draft, db)
    db.commit()
    db.refresh(draft)
    return draft


@router.post("/scenario-drafts/{draft_id}/reject", response_model=ScenarioDraftOut)
def reject_draft(draft_id: UUID, db: Session = Depends(get_db)):
    draft = db.get(ScenarioDraft, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft.status != "draft":
        raise HTTPException(status_code=409, detail=f"Draft is already '{draft.status}'")
    draft.status = "rejected"
    db.commit()
    db.refresh(draft)
    return draft


@router.post("/themes/{theme_id}/scenario-drafts/approve-all", response_model=list[ScenarioDraftOut])
def approve_all_drafts(theme_id: UUID, db: Session = Depends(get_db)):
    """Gate 2: Approve all pending drafts in one action."""
    _get_theme_or_404(theme_id, db)
    pending = db.query(ScenarioDraft).filter(
        ScenarioDraft.theme_id == theme_id,
        ScenarioDraft.status == "draft",
    ).all()
    if not pending:
        raise HTTPException(status_code=409, detail="No pending drafts to approve")

    for draft in pending:
        _promote_draft(draft, db)

    db.commit()
    return pending


def _promote_draft(draft: ScenarioDraft, db: Session) -> Scenario:
    """Create a live Scenario from an approved draft and register its indicators.
    Immediately backfills all active signals for the theme so the scenario
    starts with a populated signal map rather than waiting for the next run.
    """
    scenario = Scenario(
        theme_id=draft.theme_id,
        name=draft.name,
        narrative=draft.narrative,
        assumptions=draft.key_characteristics or [],
        confidence_level="low",
        momentum_state="stable",
        support_score=0.0,
        contradiction_score=0.0,
        internal_score=0.0,
        recent_delta=0.0,
        axis1_pole=draft.axis1_pole,
        axis2_pole=draft.axis2_pole,
    )
    db.add(scenario)
    db.flush()

    # Create ScenarioIndicator records from draft.early_indicators
    for indicator_text in (draft.early_indicators or []):
        if isinstance(indicator_text, str) and indicator_text.strip():
            indicator = ScenarioIndicator(
                scenario_id=scenario.id,
                theme_id=draft.theme_id,
                description=indicator_text,
                monitoring_query=indicator_text,
                match_count=0,
            )
            db.add(indicator)

    draft.status = "approved"
    draft.approved_at = datetime.now(timezone.utc)
    draft.approved_scenario_id = scenario.id
    db.flush()

    # Backfill: map all existing active signals to this new scenario
    _backfill_signals(draft.theme_id, scenario, db)

    logger.info("Draft '%s' approved → live scenario %s", draft.name, scenario.id)
    return scenario


def _backfill_signals(theme_id, scenario: Scenario, db: Session):
    """Map all active signals for the theme to a newly promoted scenario."""
    from app.models.signal import Signal as SignalModel
    from app.services.scoring import auto_map_signals_to_scenarios

    signal_ids = [
        s.id for s in db.query(SignalModel.id)
        .filter(SignalModel.theme_id == theme_id, SignalModel.status == "active")
        .all()
    ]
    if signal_ids:
        auto_map_signals_to_scenarios(db, theme_id, signal_ids)
    logger.info("Backfilled signal links for scenario '%s' (%d signals evaluated)", scenario.name, len(signal_ids))


# ── Monitoring ─────────────────────────────────────────────────────────────

@router.get("/themes/{theme_id}/scenario-monitoring")
def get_monitoring_status(theme_id: UUID, db: Session = Depends(get_db)):
    _get_theme_or_404(theme_id, db)

    scenarios = db.query(Scenario).filter(Scenario.theme_id == theme_id).all()
    total_score = sum(s.support_score for s in scenarios) or 1.0

    scenario_data = []
    for s in scenarios:
        indicators = db.query(ScenarioIndicator).filter(ScenarioIndicator.scenario_id == s.id).all()
        scenario_data.append({
            "scenario_id": str(s.id),
            "name": s.name,
            "support_score": s.support_score,
            "relative_weight": s.support_score / total_score,
            "momentum_state": s.momentum_state,
            "confidence_level": s.confidence_level,
            "indicator_count": len(indicators),
            "indicators_matched": sum(1 for i in indicators if i.match_count > 0),
            "total_matches": sum(i.match_count for i in indicators),
            "last_match_at": max(
                (i.last_match_at for i in indicators if i.last_match_at),
                default=None,
            ),
        })

    scenario_data.sort(key=lambda x: x["relative_weight"], reverse=True)

    return {
        "theme_id": str(theme_id),
        "monitoring_active": len(scenario_data) > 0,
        "scenarios": scenario_data,
    }


@router.get("/scenarios/{scenario_id}/indicators", response_model=list[ScenarioIndicatorOut])
def list_indicators(scenario_id: UUID, db: Session = Depends(get_db)):
    if not db.get(Scenario, scenario_id):
        raise HTTPException(status_code=404, detail="Scenario not found")
    return db.query(ScenarioIndicator).filter(ScenarioIndicator.scenario_id == scenario_id).all()


# ── Trend-Scenario Matrix ───────────────────────────────────────────────────

@router.get("/themes/{theme_id}/trend-scenario-matrix")
def get_trend_scenario_matrix(theme_id: UUID, db: Session = Depends(get_db)):
    """
    Returns a matrix of trend × scenario signal overlap.
    Each cell contains total overlap count, support count, and weaken count.
    Used to visualize which trends are driving which scenarios.
    """
    from app.models.signal import SignalScenario

    _get_theme_or_404(theme_id, db)

    trends = db.query(Trend).filter(Trend.theme_id == theme_id).order_by(Trend.momentum.desc()).all()
    scenarios = db.query(Scenario).filter(Scenario.theme_id == theme_id).all()

    if not trends or not scenarios:
        return {"trends": [], "scenarios": [], "cells": []}

    # Pre-fetch all signal→scenario links for this theme's scenarios
    scenario_ids = [s.id for s in scenarios]
    all_links = (
        db.query(SignalScenario)
        .filter(SignalScenario.scenario_id.in_(scenario_ids))
        .all()
    )
    # Index: scenario_id → {signal_id: relationship_type}
    scenario_signal_map: dict[str, dict[str, str]] = {}
    for link in all_links:
        sid = str(link.scenario_id)
        scenario_signal_map.setdefault(sid, {})[str(link.signal_id)] = link.relationship_type

    cells = []
    for trend in trends:
        trend_signal_ids = set(trend.supporting_signal_ids or [])
        for scenario in scenarios:
            scene_signals = scenario_signal_map.get(str(scenario.id), {})
            overlap_ids = trend_signal_ids & set(scene_signals.keys())
            support = sum(1 for sid in overlap_ids if scene_signals[sid] == "supports")
            weaken = sum(1 for sid in overlap_ids if scene_signals[sid] == "weakens")
            cells.append({
                "trend_id": str(trend.id),
                "scenario_id": str(scenario.id),
                "overlap": len(overlap_ids),
                "supports": support,
                "weakens": weaken,
            })

    return {
        "trends": [
            {
                "id": str(t.id),
                "name": t.name,
                "signal_count": t.signal_count,
                "horizon": t.horizon,
                "steep_domains": t.steep_domains or [],
            }
            for t in trends
        ],
        "scenarios": [
            {
                "id": str(s.id),
                "name": s.name,
                "confidence_level": s.confidence_level,
                "momentum_state": s.momentum_state,
                "axis1_pole": s.axis1_pole,
                "axis2_pole": s.axis2_pole,
                "support_score": s.support_score,
            }
            for s in scenarios
        ],
        "cells": cells,
        "axes": [
            {
                "axis_number": a.axis_number,
                "driver_name": a.driver_name,
                "pole_high": a.pole_high,
                "pole_low": a.pole_low,
            }
            for a in db.query(ScenarioAxis)
            .filter(ScenarioAxis.theme_id == theme_id, ScenarioAxis.user_confirmed == True)  # noqa: E712
            .order_by(ScenarioAxis.axis_number)
            .all()
        ],
    }
