from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel


class ScenarioCreate(BaseModel):
    name: str
    narrative: Optional[str] = None
    assumptions: List[Any] = []
    confidence_level: str = "low"
    momentum_state: str = "stable"


class ScenarioUpdate(BaseModel):
    name: Optional[str] = None
    narrative: Optional[str] = None
    assumptions: Optional[List[Any]] = None
    confidence_level: Optional[str] = None
    momentum_state: Optional[str] = None


class SignalLinkCreate(BaseModel):
    signal_id: UUID
    relationship_type: str = "neutral"  # supports | weakens | neutral
    relationship_score: float = 0.0
    explanation_text: Optional[str] = None
    user_confirmed: bool = False


class SignalLinkOut(BaseModel):
    model_config = {"from_attributes": True}

    signal_id: UUID
    scenario_id: UUID
    relationship_type: str
    relationship_score: float
    user_confirmed: bool
    explanation_text: Optional[str]
    # Denormalized signal fields for display
    signal_title: Optional[str] = None
    signal_type: Optional[str] = None
    steep_category: Optional[str] = None
    horizon: Optional[str] = None
    importance_score: Optional[float] = None
    source_url: Optional[str] = None


class ScenarioOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    theme_id: UUID
    name: str
    narrative: Optional[str]
    assumptions: List[Any]
    confidence_level: str
    momentum_state: str
    support_score: float
    contradiction_score: float
    internal_score: float
    recent_delta: float
    created_at: datetime
    updated_at: datetime
