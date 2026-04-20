"""scenario pipeline tables: trends, drivers, scenario_axes, scenario_drafts, scenario_indicators

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trends",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("theme_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("themes.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("steep_domains", postgresql.JSONB, server_default="[]"),
        sa.Column("signal_count", sa.Integer, server_default="0"),
        sa.Column("momentum", sa.Float, server_default="0.5"),
        sa.Column("s_curve_position", sa.String(50), server_default="emerging"),
        sa.Column("horizon", sa.String(10)),
        sa.Column("supporting_signal_ids", postgresql.JSONB, server_default="[]"),
        sa.Column("ontology_alignment", sa.Float, server_default="0.5"),
        sa.Column("cluster_id", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_trends_theme_id", "trends", ["theme_id"])
    op.create_index("ix_trends_cluster_id", "trends", ["cluster_id"])

    op.create_table(
        "drivers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("theme_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("themes.id"), nullable=False),
        sa.Column("trend_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trends.id"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("impact_score", sa.Float, server_default="5.0"),
        sa.Column("uncertainty_score", sa.Float, server_default="5.0"),
        sa.Column("is_predetermined", sa.Boolean, server_default="false"),
        sa.Column("steep_domain", sa.String(50)),
        sa.Column("cross_impacts", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_drivers_theme_id", "drivers", ["theme_id"])

    op.create_table(
        "scenario_axes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("theme_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("themes.id"), nullable=False),
        sa.Column("axis_number", sa.Integer, nullable=False),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("drivers.id"), nullable=True),
        sa.Column("driver_name", sa.String(255)),
        sa.Column("pole_low", sa.String(500)),
        sa.Column("pole_high", sa.String(500)),
        sa.Column("rationale", sa.Text),
        sa.Column("user_confirmed", sa.Boolean, server_default="false"),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_scenario_axes_theme_id", "scenario_axes", ["theme_id"])

    op.create_table(
        "scenario_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("theme_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("themes.id"), nullable=False),
        sa.Column("quadrant", sa.String(10), nullable=False),
        sa.Column("axis1_pole", sa.String(10)),
        sa.Column("axis2_pole", sa.String(10)),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("narrative", sa.Text),
        sa.Column("key_characteristics", postgresql.JSONB, server_default="[]"),
        sa.Column("stakeholder_implications", sa.Text),
        sa.Column("early_indicators", postgresql.JSONB, server_default="[]"),
        sa.Column("opportunities", postgresql.JSONB, server_default="[]"),
        sa.Column("threats", postgresql.JSONB, server_default="[]"),
        sa.Column("status", sa.String(20), server_default="draft"),
        sa.Column("user_notes", sa.Text),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("approved_scenario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scenarios.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_scenario_drafts_theme_id", "scenario_drafts", ["theme_id"])

    op.create_table(
        "scenario_indicators",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scenarios.id"), nullable=False),
        sa.Column("theme_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("themes.id"), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("monitoring_query", sa.String(500)),
        sa.Column("last_signal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("signals.id"), nullable=True),
        sa.Column("last_match_at", sa.DateTime(timezone=True)),
        sa.Column("match_count", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_scenario_indicators_scenario_id", "scenario_indicators", ["scenario_id"])
    op.create_index("ix_scenario_indicators_theme_id", "scenario_indicators", ["theme_id"])


def downgrade() -> None:
    op.drop_table("scenario_indicators")
    op.drop_table("scenario_drafts")
    op.drop_table("scenario_axes")
    op.drop_table("drivers")
    op.drop_table("trends")
