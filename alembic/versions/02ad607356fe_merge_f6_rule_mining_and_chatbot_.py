"""merge F6 rule mining and chatbot optimization heads with develop

Revision ID: 02ad607356fe
Revises: 0dd345991838, f174da39ddff
Create Date: 2026-08-22 01:02:54.044220

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '02ad607356fe'
down_revision: Union[str, Sequence[str], None] = ('0dd345991838', 'f174da39ddff')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
