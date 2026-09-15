"""hop nhat 2 head sau khi merge develop (eval-cost-dashboard)

Revision ID: f174da39ddff
Revises: f3194e228632, e4f5a6b7c8d9
Create Date: 2026-08-21 23:12:33.327322

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f174da39ddff'
down_revision: Union[str, Sequence[str], None] = ('f3194e228632', 'e4f5a6b7c8d9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
