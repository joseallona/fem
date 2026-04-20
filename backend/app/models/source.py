import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Source(Base):
    __tablename__ = "sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    theme_id = Column(UUID(as_uuid=True), ForeignKey("themes.id"), nullable=False)
    name = Column(String(255))
    domain = Column(String(255))
    url = Column(Text, nullable=False)
    source_type = Column(String(100))  # news | academic | government | blog | patent | newsletter
    discovery_mode = Column(String(50), nullable=False, default="manual")  # system | manual
    relevance_score = Column(Float, default=0.0)
    trust_score = Column(Float, default=0.5)
    crawl_frequency = Column(String(50), default="daily")  # daily | weekly
    status = Column(String(50), nullable=False, default="approved")  # suggested | approved | paused | blocked
    last_crawled_at = Column(DateTime(timezone=True))
    initial_crawl_done = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    theme = relationship("Theme", back_populates="sources")
    raw_documents = relationship("RawDocument", back_populates="source", cascade="all, delete-orphan")
    signals = relationship("Signal", back_populates="source")
