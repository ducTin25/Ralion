"""Merge access-management and embedding/chat migration heads.

Revision ID: d4e5f6a0b1c2
Revises: c3d4e5f9a0b1, c5d7e9f1a3b4
Create Date: 2026-08-24
"""

from collections.abc import Sequence

revision: str = "d4e5f6a0b1c2"
down_revision: str | Sequence[str] | None = ("c3d4e5f9a0b1", "c5d7e9f1a3b4")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join the two schema histories without changing data."""


def downgrade() -> None:
    """Split the histories without changing data."""
