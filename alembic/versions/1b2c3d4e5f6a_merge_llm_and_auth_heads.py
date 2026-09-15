"""Merge the LLM/RAG and authentication migration branches.

Revision ID: 1b2c3d4e5f6a
Revises: 0a1b2c3d4e5f, d4e5f6a7b8c9
Create Date: 2026-08-14
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "1b2c3d4e5f6a"
down_revision: str | Sequence[str] | None = ("0a1b2c3d4e5f", "d4e5f6a7b8c9")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Unify independent schema branches without changing database objects."""


def downgrade() -> None:
    """Split the migration graph back into its independent branches."""
