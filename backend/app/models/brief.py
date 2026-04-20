import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Brief(Base):
    __tablename__ = "briefs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    theme_id = Column(UUID(as_uuid=True), ForeignKey("themes.id"), nullable=False)
    period_start = Column(Date)
    period_end = Column(Date)
    generation_mode = Column(String(50), default="on_demand")  # weekly | on_demand
    status = Column(String(50), default="generating")  # generating | completed | failed
    structured_payload_json = Column(JSONB, default=dict)
    rendered_text = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    theme = relationship("Theme", back_populates="briefs")
