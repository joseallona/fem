"""add current_stage to crawl_runs

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("crawl_runs", sa.Column("current_stage", sa.String(200), nullable=True))


def downgrade():
    op.drop_column("crawl_runs", "current_stage")
