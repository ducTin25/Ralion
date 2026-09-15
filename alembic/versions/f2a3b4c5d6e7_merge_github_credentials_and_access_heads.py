"""Merge GitHub credential and access/embedding migration heads.

Revision ID: f2a3b4c5d6e7
Revises: d4e5f6a0b1c2, e1a2b3c4d5f6
Create Date: 2026-08-25

"""

from collections.abc import Sequence

revision: str = "f2a3b4c5d6e7"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = (  # pragma: allowlist secret
    "d4e5f6a0b1c2",  # pragma: allowlist secret
    "e1a2b3c4d5f6",  # pragma: allowlist secret
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join the schema histories without changing data."""


def downgrade() -> None:
    """Split the schema histories without changing data."""
