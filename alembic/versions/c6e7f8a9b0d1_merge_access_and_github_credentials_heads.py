"""Merge access-management and GitHub-credentials heads.

Revision ID: c6e7f8a9b0d1
Revises: d4e5f6a0b1c2, e1a2b3c4d5f6
Create Date: 2026-08-25
"""

from collections.abc import Sequence

revision: str = "c6e7f8a9b0d1"
down_revision: str | Sequence[str] | None = ("d4e5f6a0b1c2", "e1a2b3c4d5f6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join existing schema histories without changing data."""


def downgrade() -> None:
    """Split the histories without changing data."""
