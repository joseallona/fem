from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class RunOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    theme_id: UUID
    started_at: datetime
    completed_at: Optional[datetime]
    status: str
    sources_scanned: int
    documents_fetched: int
    signals_created: int
    notes: Optional[str]
    current_stage: Optional[str] = None
    estimated_duration_seconds: Optional[int] = None
