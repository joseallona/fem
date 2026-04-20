from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel


class SignalCreate(BaseModel):
    title: str
    summary: Optional[str] = None
    signal_type: Optional[str] = None
    steep_category: Optional[str] = None
    horizon: Optional[str] = None
    importance_score: float = 0.5
    novelty_score: float = 0.5
    relevance_score: float = 0.5
    source_id: Optional[UUID] = None
    raw_document_id: Optional[UUID] = None
    status: str = "active"


class SignalUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    signal_type: Optional[str] = None
    steep_category: Optional[str] = None
    horizon: Optional[str] = None
    importance_score: Optional[float] = None
    novelty_score: Optional[float] = None
    relevance_score: Optional[float] = None
    status: Optional[str] = None


class SignalOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    theme_id: UUID
    source_id: Optional[UUID]
    raw_document_id: Optional[UUID]
    title: str
    summary: Optional[str]
    signal_type: Optional[str]
    steep_category: Optional[str]
    horizon: Optional[str]
    importance_score: float
    novelty_score: float
    relevance_score: float
    status: str
    cluster_id: Optional[str]
    score_breakdown: Optional[Dict[str, Any]]
    created_at: datetime
    source_url: Optional[str] = None


class FeedbackCreate(BaseModel):
    feedback_type: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    note: Optional[str] = None


class FeedbackOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    signal_id: UUID
    feedback_type: str
    old_value: Optional[str]
    new_value: Optional[str]
    note: Optional[str]
    created_at: datetime
