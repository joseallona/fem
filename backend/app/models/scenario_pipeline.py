import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class ScenarioAxis(Base):
    """
    One of the two critical-uncertainty axes that frame the 4-scenario quadrant.
    Two records exist per theme (axis_number 1 and 2).
    user_confirmed=True unlocks scenario draft generation.
    """
    __tablename__ = "scenario_axes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    theme_id = Column(UUID(as_uuid=True), ForeignKey("themes.id"), nullable=False)
    axis_number = Column(Integer, nullable=False)     # 1 or 2
    driver_id = Column(UUID(as_uuid=True), ForeignKey("drivers.id"), nullable=True)
    driver_name = Column(String(255))                 # denormalized for display
    pole_low = Column(String(500))                    # left / bottom pole label
    pole_high = Column(String(500))                   # right / top pole label
    rationale = Column(Text)                          # why this driver was selected
    user_confirmed = Column(Boolean, default=False)
    confirmed_at = Column(DateTime(timezone=True))
    axis_locked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    theme = relationship("Theme", back_populates="scenario_axes")
    driver = relationship("Driver")


class ScenarioDraft(Base):
    """
    LLM-generated scenario draft awaiting user review (Gate 2).
    On approval it is promoted to a live Scenario record.
    """
    __tablename__ = "scenario_drafts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    theme_id = Column(UUID(as_uuid=True), ForeignKey("themes.id"), nullable=False)
    quadrant = Column(String(10), nullable=False)   # Q1|Q2|Q3|Q4
    axis1_pole = Column(String(10))                 # low|high
    axis2_pole = Column(String(10))                 # low|high
    name = Column(String(255), nullable=False)
    narrative = Column(Text)
    key_characteristics = Column(JSONB, default=list)      # list[str]
    stakeholder_implications = Column(Text)
    early_indicators = Column(JSONB, default=list)         # list[str] — fed to monitoring
    opportunities = Column(JSONB, default=list)            # list[str]
    threats = Column(JSONB, default=list)                  # list[str]
    status = Column(String(20), default="draft")           # draft|approved|rejected
    user_notes = Column(Text)                              # optional reviewer notes
    approved_at = Column(DateTime(timezone=True))
    approved_scenario_id = Column(
        UUID(as_uuid=True), ForeignKey("scenarios.id"), nullable=True
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    theme = relationship("Theme", back_populates="scenario_drafts")
    approved_scenario = relationship("Scenario", foreign_keys=[approved_scenario_id])


class ScenarioIndicator(Base):
    """
    An early warning indicator tied to a live Scenario.
    Created from ScenarioDraft.early_indicators on Gate 2 approval.
    Updated each pipeline run when matching signals are found.
    """
    __tablename__ = "scenario_indicators"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scenario_id = Column(UUID(as_uuid=True), ForeignKey("scenarios.id"), nullable=False)
    theme_id = Column(UUID(as_uuid=True), ForeignKey("themes.id"), nullable=False)
    description = Column(Text, nullable=False)
    monitoring_query = Column(String(500))          # keywords for signal matching
    last_signal_id = Column(
        UUID(as_uuid=True), ForeignKey("signals.id"), nullable=True
    )
    last_match_at = Column(DateTime(timezone=True))
    match_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    scenario = relationship("Scenario", back_populates="indicators", foreign_keys=[scenario_id])
    theme = relationship("Theme")
    last_signal = relationship("Signal", foreign_keys=[last_signal_id])
