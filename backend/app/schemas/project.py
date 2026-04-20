from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    owner: Optional[str] = None
    status: str = "active"


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = None
    status: Optional[str] = None


class ProjectOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    name: str
    description: Optional[str]
    owner: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
