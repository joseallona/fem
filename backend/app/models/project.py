import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    owner = Column(String(255))
    status = Column(String(50), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    themes = relationship("ProjectTheme", back_populates="project", cascade="all, delete-orphan")
