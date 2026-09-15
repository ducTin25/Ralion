"""merge onboarding-plan branch head with github ingestion versioning branch

Revision ID: 97a9cd973ca6
Revises: 446b46c22988, 5a6b7c8d9e0f
Create Date: 2026-08-14 17:31:42.591210

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '97a9cd973ca6'
down_revision: Union[str, Sequence[str], None] = ('446b46c22988', '5a6b7c8d9e0f')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
