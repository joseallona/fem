import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Trend(Base):
    __tablename__ = "trends"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    theme_id = Column(UUID(as_uuid=True), ForeignKey("themes.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    steep_domains = Column(JSONB, default=list)          # ["T", "E"]
    signal_count = Column(Integer, default=0)
    momentum = Column(Float, default=0.5)                # avg importance_score of member signals
    s_curve_position = Column(String(50), default="emerging")  # emerging|growth|mature|declining
    horizon = Column(String(10))                         # H1|H2|H3
    supporting_signal_ids = Column(JSONB, default=list)  # list of signal UUID strings
    ontology_alignment = Column(Float, default=0.5)      # avg relevance_score of member signals
    cluster_id = Column(String(100))                     # matches signal.cluster_id that originated this trend
    direction = Column(Text)         # the future this cluster is pushing toward (e.g. "decentralised energy")
    counterpole = Column(Text)       # the opposing direction (e.g. "centralised fossil dependency")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    theme = relationship("Theme", back_populates="trends")
    drivers = relationship("Driver", back_populates="trend", cascade="all, delete-orphan")


class Driver(Base):
    __tablename__ = "drivers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    theme_id = Column(UUID(as_uuid=True), ForeignKey("themes.id"), nullable=False)
    trend_id = Column(UUID(as_uuid=True), ForeignKey("trends.id"), nullable=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    impact_score = Column(Float, default=5.0)       # 1–10: how much this shapes the focal theme
    uncertainty_score = Column(Float, default=5.0)  # 1–10: how unpredictable the outcome is
    is_predetermined = Column(Boolean, default=False)  # high impact + low uncertainty
    steep_domain = Column(String(50))
    pole_high_direction = Column(Text)   # what signals look like when this driver resolves toward high
    pole_low_direction = Column(Text)    # what signals look like when this driver resolves toward low
    cross_impacts = Column(JSONB, default=dict)  # {driver_id_str: "reinforces"|"dampens"}
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    theme = relationship("Theme", back_populates="drivers")
    trend = relationship("Trend", back_populates="drivers")
