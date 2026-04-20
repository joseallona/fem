from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel


class ThemeCreate(BaseModel):
    name: str
    description: Optional[str] = None
    primary_subject: Optional[str] = None
    focal_question: Optional[str] = None
    time_horizon: Optional[str] = None
    stakeholders_json: List[Any] = []
    related_subjects_json: List[str] = []
    scope_text: Optional[str] = None
    status: str = "draft"


class ThemeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    primary_subject: Optional[str] = None
    focal_question: Optional[str] = None
    time_horizon: Optional[str] = None
    stakeholders_json: Optional[List[Any]] = None
    related_subjects_json: Optional[List[str]] = None
    scope_text: Optional[str] = None
    status: Optional[str] = None


class ThemeOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    name: str
    description: Optional[str]
    primary_subject: Optional[str]
    focal_question: Optional[str]
    time_horizon: Optional[str]
    stakeholders_json: List[Any]
    related_subjects_json: List[str]
    scope_text: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
