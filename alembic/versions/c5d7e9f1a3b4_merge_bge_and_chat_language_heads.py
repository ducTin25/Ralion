"""Merge pinned BGE-M3 and chat-language migration branches.

Revision ID: c5d7e9f1a3b4
Revises: a4c6e8f0b2d3, b4c5d6e7f8a9
Create Date: 2026-08-24
"""

from collections.abc import Sequence

revision: str = "c5d7e9f1a3b4"
down_revision: str | Sequence[str] | None = ("a4c6e8f0b2d3", "b4c5d6e7f8a9")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join the two schema histories without changing data."""


def downgrade() -> None:
    """Split the histories without changing data."""
