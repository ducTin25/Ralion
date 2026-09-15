"""merge phase3 documents branch with develop policy embedding pipeline

Revision ID: 781ee9706e41
Revises: 9e2a4d6533a4, a8b9c0d1e2f3
Create Date: 2026-08-13 09:53:05.544990

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '781ee9706e41'
down_revision: str | Sequence[str] | None = ('9e2a4d6533a4', 'a8b9c0d1e2f3')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
