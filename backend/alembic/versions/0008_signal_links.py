"""signal_links table and embedding column on signals

Revision ID: 0008_signal_links
Revises: 0007_axis_locked
Create Date: 2026-04-20

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_signal_links"
down_revision: Union[str, None] = "0007_axis_locked"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("signals", sa.Column("embedding", sa.Text(), nullable=True))

    op.create_table(
        "signal_links",
        sa.Column("signal_a_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("signals.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("signal_b_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("signals.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("link_type", sa.String(20), nullable=False),
        sa.Column("strength", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("relationship_type", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_signal_links_a", "signal_links", ["signal_a_id"])
    op.create_index("ix_signal_links_b", "signal_links", ["signal_b_id"])


def downgrade() -> None:
    op.drop_index("ix_signal_links_b", table_name="signal_links")
    op.drop_index("ix_signal_links_a", table_name="signal_links")
    op.drop_table("signal_links")
    op.drop_column("signals", "embedding")
