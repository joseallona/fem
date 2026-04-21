import uuid

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Signal(Base):
    __tablename__ = "signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    theme_id = Column(UUID(as_uuid=True), ForeignKey("themes.id"), nullable=False)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.id"))
    raw_document_id = Column(UUID(as_uuid=True), ForeignKey("raw_documents.id"))
    title = Column(Text, nullable=False)
    summary = Column(Text)
    signal_type = Column(String(50))   # trend | weak_signal | wildcard | driver | indicator
    steep_category = Column(String(50))  # social | technological | economic | environmental | political
    horizon = Column(String(10))  # H1 | H2 | H3
    importance_score = Column(Float, default=0.5)
    novelty_score = Column(Float, default=0.5)
    relevance_score = Column(Float, default=0.5)
    status = Column(String(50), default="active")  # active | needs_review | archived
    cluster_id = Column(String(100), nullable=True)  # assigned by clustering service
    score_breakdown = Column(JSON, nullable=True)  # {relevance, novelty, impact, source_trust, recency, weights}
    embedding = Column(Text, nullable=True)  # JSON-encoded float array for signal linking
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    theme = relationship("Theme", back_populates="signals")
    source = relationship("Source", back_populates="signals")
    raw_document = relationship("RawDocument", back_populates="signals")
    scenario_links = relationship("SignalScenario", back_populates="signal", cascade="all, delete-orphan")
    feedback = relationship("UserFeedback", back_populates="signal", cascade="all, delete-orphan")
    links_as_a = relationship("SignalLink", foreign_keys="SignalLink.signal_a_id",
                              back_populates="signal_a", cascade="all, delete-orphan")
    links_as_b = relationship("SignalLink", foreign_keys="SignalLink.signal_b_id",
                              back_populates="signal_b", cascade="all, delete-orphan")

    @property
    def source_url(self) -> str | None:
        if self.raw_document and self.raw_document.url:
            return self.raw_document.url
        return self.source.url if self.source else None


class SignalLink(Base):
    __tablename__ = "signal_links"

    signal_a_id = Column(UUID(as_uuid=True), ForeignKey("signals.id", ondelete="CASCADE"), primary_key=True)
    signal_b_id = Column(UUID(as_uuid=True), ForeignKey("signals.id", ondelete="CASCADE"), primary_key=True)
    link_type = Column(String(20), nullable=False)   # cluster | embedding | llm
    strength = Column(Float, nullable=False, default=1.0)
    relationship_type = Column(String(20), nullable=True)  # reinforcing | tensioning
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    signal_a = relationship("Signal", foreign_keys="[SignalLink.signal_a_id]", back_populates="links_as_a")
    signal_b = relationship("Signal", foreign_keys="[SignalLink.signal_b_id]", back_populates="links_as_b")


class SignalScenario(Base):
    __tablename__ = "signal_scenarios"

    signal_id = Column(UUID(as_uuid=True), ForeignKey("signals.id"), primary_key=True)
    scenario_id = Column(UUID(as_uuid=True), ForeignKey("scenarios.id"), primary_key=True)
    relationship_type = Column(String(50), nullable=False, default="neutral")  # supports | weakens | neutral
    relationship_score = Column(Float, default=0.0)
    user_confirmed = Column(Boolean, default=False)
    explanation_text = Column(Text)

    signal = relationship("Signal", back_populates="scenario_links")
    scenario = relationship("Scenario", back_populates="signal_links")


class UserFeedback(Base):
    __tablename__ = "user_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signal_id = Column(UUID(as_uuid=True), ForeignKey("signals.id"), nullable=False)
    feedback_type = Column(String(50))  # importance | irrelevance | reclassify | note | scenario_link
    old_value = Column(Text)
    new_value = Column(Text)
    note = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    signal = relationship("Signal", back_populates="feedback")
