import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class CrawlRun(Base):
    __tablename__ = "crawl_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    theme_id = Column(UUID(as_uuid=True), ForeignKey("themes.id"), nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    status = Column(String(50), nullable=False, default="running")  # running | completed | failed
    sources_scanned = Column(Integer, default=0)
    documents_fetched = Column(Integer, default=0)
    signals_created = Column(Integer, default=0)
    notes = Column(Text)
    current_stage = Column(String(200))

    theme = relationship("Theme", back_populates="crawl_runs")
    raw_documents = relationship("RawDocument", back_populates="crawl_run")


class RawDocument(Base):
    __tablename__ = "raw_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.id"), nullable=False)
    crawl_run_id = Column(UUID(as_uuid=True), ForeignKey("crawl_runs.id"))
    url = Column(Text, nullable=False)
    title = Column(Text)
    published_at = Column(DateTime(timezone=True))
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())
    raw_text = Column(Text)
    content_hash = Column(String(64))
    canonical_url = Column(Text)
    metadata_json = Column(JSONB, default=dict)

    source = relationship("Source", back_populates="raw_documents")
    crawl_run = relationship("CrawlRun", back_populates="raw_documents")
    signals = relationship("Signal", back_populates="raw_document")
