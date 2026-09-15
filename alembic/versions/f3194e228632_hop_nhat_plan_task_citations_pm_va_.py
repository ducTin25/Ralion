"""hop nhat plan_task_citations (PM) va policy_acknowledgement (develop)

Revision ID: f3194e228632
Revises: c2d3e4f5a6b7, f6a7b8c9d0e1
Create Date: 2026-08-15 19:06:50.082632

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3194e228632'
down_revision: Union[str, Sequence[str], None] = ('c2d3e4f5a6b7', 'f6a7b8c9d0e1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
