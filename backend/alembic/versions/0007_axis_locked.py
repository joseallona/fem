"""axis_locked field on scenario_axes

Revision ID: 0007_axis_locked
Revises: 411a237e3663
Create Date: 2026-04-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0007_axis_locked'
down_revision: Union[str, None] = '411a237e3663'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'scenario_axes',
        sa.Column('axis_locked', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade() -> None:
    op.drop_column('scenario_axes', 'axis_locked')
