"""add initial_crawl_done to sources

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "sources",
        sa.Column("initial_crawl_done", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade():
    op.drop_column("sources", "initial_crawl_done")
