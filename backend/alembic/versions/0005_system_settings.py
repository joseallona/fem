"""add system_settings table

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.String(2000), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )


def downgrade():
    op.drop_table("system_settings")
