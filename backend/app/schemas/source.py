from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class SourceCreate(BaseModel):
    url: str
    name: Optional[str] = None
    domain: Optional[str] = None
    source_type: Optional[str] = None
    discovery_mode: str = "manual"
    crawl_frequency: str = "daily"
    relevance_score: float = 0.0
    trust_score: float = 0.5
    status: str = "approved"


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    source_type: Optional[str] = None
    crawl_frequency: Optional[str] = None
    relevance_score: Optional[float] = None
    trust_score: Optional[float] = None
    status: Optional[str] = None


class SourceOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    theme_id: UUID
    name: Optional[str]
    domain: Optional[str]
    url: str
    source_type: Optional[str]
    discovery_mode: str
    relevance_score: float
    trust_score: float
    crawl_frequency: str
    status: str
    last_crawled_at: Optional[datetime]
    initial_crawl_done: bool
    created_at: datetime
