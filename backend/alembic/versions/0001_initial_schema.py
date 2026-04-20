"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("owner", sa.String(255)),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "themes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("primary_subject", sa.String(255)),
        sa.Column("focal_question", sa.Text),
        sa.Column("time_horizon", sa.String(100)),
        sa.Column("stakeholders_json", postgresql.JSONB, server_default="[]"),
        sa.Column("related_subjects_json", postgresql.JSONB, server_default="[]"),
        sa.Column("scope_text", sa.Text),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "project_themes",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), primary_key=True),
        sa.Column("theme_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("themes.id"), primary_key=True),
    )

    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("theme_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("themes.id"), nullable=False),
        sa.Column("name", sa.String(255)),
        sa.Column("domain", sa.String(255)),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("source_type", sa.String(100)),
        sa.Column("discovery_mode", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("relevance_score", sa.Float, server_default="0.0"),
        sa.Column("trust_score", sa.Float, server_default="0.5"),
        sa.Column("crawl_frequency", sa.String(50), server_default="daily"),
        sa.Column("status", sa.String(50), nullable=False, server_default="suggested"),
        sa.Column("last_crawled_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_sources_theme_id", "sources", ["theme_id"])

    op.create_table(
        "crawl_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("theme_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("themes.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(50), nullable=False, server_default="running"),
        sa.Column("sources_scanned", sa.Integer, server_default="0"),
        sa.Column("documents_fetched", sa.Integer, server_default="0"),
        sa.Column("signals_created", sa.Integer, server_default="0"),
        sa.Column("notes", sa.Text),
    )

    op.create_table(
        "raw_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("crawl_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crawl_runs.id")),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("title", sa.Text),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("raw_text", sa.Text),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("canonical_url", sa.Text),
        sa.Column("metadata_json", postgresql.JSONB, server_default="{}"),
    )
    op.create_index("ix_raw_documents_content_hash", "raw_documents", ["content_hash"])

    op.create_table(
        "scenarios",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("theme_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("themes.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("narrative", sa.Text),
        sa.Column("assumptions", postgresql.JSONB, server_default="[]"),
        sa.Column("confidence_level", sa.String(20), server_default="low"),
        sa.Column("momentum_state", sa.String(20), server_default="stable"),
        sa.Column("support_score", sa.Float, server_default="0.0"),
        sa.Column("contradiction_score", sa.Float, server_default="0.0"),
        sa.Column("internal_score", sa.Float, server_default="0.0"),
        sa.Column("recent_delta", sa.Float, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("theme_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("themes.id"), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id")),
        sa.Column("raw_document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("raw_documents.id")),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("summary", sa.Text),
        sa.Column("signal_type", sa.String(50)),
        sa.Column("steep_category", sa.String(50)),
        sa.Column("horizon", sa.String(10)),
        sa.Column("importance_score", sa.Float, server_default="0.5"),
        sa.Column("novelty_score", sa.Float, server_default="0.5"),
        sa.Column("relevance_score", sa.Float, server_default="0.5"),
        sa.Column("status", sa.String(50), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_signals_theme_id", "signals", ["theme_id"])

    op.create_table(
        "signal_scenarios",
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("signals.id"), primary_key=True),
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scenarios.id"), primary_key=True),
        sa.Column("relationship_type", sa.String(50), nullable=False, server_default="neutral"),
        sa.Column("relationship_score", sa.Float, server_default="0.0"),
        sa.Column("user_confirmed", sa.Boolean, server_default="false"),
        sa.Column("explanation_text", sa.Text),
    )

    op.create_table(
        "briefs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("theme_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("themes.id"), nullable=False),
        sa.Column("period_start", sa.Date),
        sa.Column("period_end", sa.Date),
        sa.Column("generation_mode", sa.String(50), server_default="on_demand"),
        sa.Column("status", sa.String(50), server_default="generating"),
        sa.Column("structured_payload_json", postgresql.JSONB, server_default="{}"),
        sa.Column("rendered_text", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "user_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("signals.id"), nullable=False),
        sa.Column("feedback_type", sa.String(50)),
        sa.Column("old_value", sa.Text),
        sa.Column("new_value", sa.Text),
        sa.Column("note", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("user_feedback")
    op.drop_table("signal_scenarios")
    op.drop_table("briefs")
    op.drop_table("signals")
    op.drop_table("scenarios")
    op.drop_table("raw_documents")
    op.drop_table("crawl_runs")
    op.drop_table("sources")
    op.drop_table("project_themes")
    op.drop_table("themes")
    op.drop_table("projects")
