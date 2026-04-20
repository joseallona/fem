import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    theme_id = Column(UUID(as_uuid=True), ForeignKey("themes.id"), nullable=False)
    name = Column(String(255), nullable=False)
    narrative = Column(Text)
    assumptions = Column(JSONB, default=list)
    confidence_level = Column(String(20), default="low")   # low | medium | high
    momentum_state = Column(String(20), default="stable")  # increasing | stable | decreasing
    support_score = Column(Float, default=0.0)
    contradiction_score = Column(Float, default=0.0)
    internal_score = Column(Float, default=0.0)
    recent_delta = Column(Float, default=0.0)
    axis1_pole = Column(String(10))   # "high" | "low" — which pole of axis 1 this scenario assumes
    axis2_pole = Column(String(10))   # "high" | "low" — which pole of axis 2 this scenario assumes
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    theme = relationship("Theme", back_populates="scenarios")
    signal_links = relationship("SignalScenario", back_populates="scenario", cascade="all, delete-orphan")
    indicators = relationship("ScenarioIndicator", back_populates="scenario", cascade="all, delete-orphan",
                              foreign_keys="ScenarioIndicator.scenario_id")
