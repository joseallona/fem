from datetime import date, datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel


class BriefGenerateRequest(BaseModel):
    generation_mode: str = "on_demand"  # weekly | on_demand
    period_start: Optional[date] = None
    period_end: Optional[date] = None


class BriefOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    theme_id: UUID
    period_start: Optional[date]
    period_end: Optional[date]
    generation_mode: str
    status: str
    structured_payload_json: Dict[str, Any]
    rendered_text: Optional[str]
    created_at: datetime
