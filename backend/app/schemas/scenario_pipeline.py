from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel


# ── Trend ──────────────────────────────────────────────────────────────────

class TrendOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    theme_id: UUID
    name: str
    description: Optional[str]
    steep_domains: List[str]
    signal_count: int
    momentum: float
    s_curve_position: str
    horizon: Optional[str]
    supporting_signal_ids: List[str]
    ontology_alignment: float
    cluster_id: Optional[str]
    created_at: datetime
    updated_at: datetime


# ── Driver ─────────────────────────────────────────────────────────────────

class DriverOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    theme_id: UUID
    trend_id: Optional[UUID]
    name: str
    description: Optional[str]
    impact_score: float
    uncertainty_score: float
    is_predetermined: bool
    steep_domain: Optional[str]
    cross_impacts: dict
    created_at: datetime
    updated_at: datetime


# ── Scenario Axis ──────────────────────────────────────────────────────────

class ScenarioAxisUpdate(BaseModel):
    driver_name: Optional[str] = None
    pole_low: Optional[str] = None
    pole_high: Optional[str] = None
    rationale: Optional[str] = None
    axis_locked: Optional[bool] = None


class ScenarioAxisOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    theme_id: UUID
    axis_number: int
    driver_id: Optional[UUID]
    driver_name: Optional[str]
    pole_low: Optional[str]
    pole_high: Optional[str]
    rationale: Optional[str]
    user_confirmed: bool
    confirmed_at: Optional[datetime]
    axis_locked: bool
    created_at: datetime
    updated_at: datetime


# ── Scenario Draft ─────────────────────────────────────────────────────────

class ScenarioDraftUpdate(BaseModel):
    name: Optional[str] = None
    narrative: Optional[str] = None
    key_characteristics: Optional[List[str]] = None
    stakeholder_implications: Optional[str] = None
    early_indicators: Optional[List[str]] = None
    opportunities: Optional[List[str]] = None
    threats: Optional[List[str]] = None
    user_notes: Optional[str] = None


class ScenarioDraftOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    theme_id: UUID
    quadrant: str
    axis1_pole: Optional[str]
    axis2_pole: Optional[str]
    name: str
    narrative: Optional[str]
    key_characteristics: List[Any]
    stakeholder_implications: Optional[str]
    early_indicators: List[Any]
    opportunities: List[Any]
    threats: List[Any]
    status: str
    user_notes: Optional[str]
    approved_at: Optional[datetime]
    approved_scenario_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime


# ── Scenario Indicator ─────────────────────────────────────────────────────

class ScenarioIndicatorOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    scenario_id: UUID
    theme_id: UUID
    description: str
    monitoring_query: Optional[str]
    last_signal_id: Optional[UUID]
    last_match_at: Optional[datetime]
    match_count: int
    created_at: datetime


# ── Pipeline Status ────────────────────────────────────────────────────────

class PipelineStatusOut(BaseModel):
    state: str  # no_data | trends_ready | axes_pending | axes_confirmed |
                # scenarios_pending | monitoring
    trend_count: int
    driver_count: int
    axes: List[ScenarioAxisOut]
    draft_count: int
    drafts_approved: int
    live_scenario_count: int
    monitoring_active: bool
    alerts: List[dict]
