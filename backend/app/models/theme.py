import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Theme(Base):
    __tablename__ = "themes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    primary_subject = Column(String(255))
    focal_question = Column(Text)
    time_horizon = Column(String(100))
    stakeholders_json = Column(JSONB, default=list)
    related_subjects_json = Column(JSONB, default=list)
    scope_text = Column(Text)
    status = Column(String(50), nullable=False, default="draft")  # draft | active | archived
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    projects = relationship("ProjectTheme", back_populates="theme")
    sources = relationship("Source", back_populates="theme", cascade="all, delete-orphan")
    signals = relationship("Signal", back_populates="theme", cascade="all, delete-orphan")
    scenarios = relationship("Scenario", back_populates="theme", cascade="all, delete-orphan")
    briefs = relationship("Brief", back_populates="theme", cascade="all, delete-orphan")
    crawl_runs = relationship("CrawlRun", back_populates="theme", cascade="all, delete-orphan")
    trends = relationship("Trend", back_populates="theme", cascade="all, delete-orphan")
    drivers = relationship("Driver", back_populates="theme", cascade="all, delete-orphan")
    scenario_axes = relationship("ScenarioAxis", back_populates="theme", cascade="all, delete-orphan")
    scenario_drafts = relationship("ScenarioDraft", back_populates="theme", cascade="all, delete-orphan")


class ProjectTheme(Base):
    __tablename__ = "project_themes"

    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), primary_key=True)
    theme_id = Column(UUID(as_uuid=True), ForeignKey("themes.id"), primary_key=True)

    project = relationship("Project", back_populates="themes")
    theme = relationship("Theme", back_populates="projects")
