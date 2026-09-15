"""merge pm-document-management onboarding-plan branch with develop auth and chat branches

Revision ID: 446b46c22988
Revises: 0a1b2c3d4e5f, c8a1f5d73e42, d4e5f6a7b8c9
Create Date: 2026-08-14 16:31:13.911213

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '446b46c22988'
down_revision: Union[str, Sequence[str], None] = ('0a1b2c3d4e5f', 'c8a1f5d73e42', 'd4e5f6a7b8c9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
