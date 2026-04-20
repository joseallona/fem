"""Add cluster_id and score_breakdown to signals

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("signals", sa.Column("cluster_id", sa.String(100), nullable=True))
    op.add_column("signals", sa.Column("score_breakdown", JSON, nullable=True))


def downgrade():
    op.drop_column("signals", "score_breakdown")
    op.drop_column("signals", "cluster_id")
