"""Merge the latest background-job, access, and chat heads.

Revision ID: e9f0a1b2c3d4
Revises: b8d9e0f1a2b3, c6e7f8a9b0d1, d7f8a9b0c1e2
Create Date: 2026-08-29
"""

from collections.abc import Sequence

revision: str = "e9f0a1b2c3d4"
down_revision: str | Sequence[str] | None = (
    "b8d9e0f1a2b3",
    "c6e7f8a9b0d1",
    "d7f8a9b0c1e2",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join the revision histories without changing the schema."""


def downgrade() -> None:
    """Split the revision histories without changing the schema."""
