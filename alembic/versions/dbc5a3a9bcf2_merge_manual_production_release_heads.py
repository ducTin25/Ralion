"""Merge the heads promoted in the manual production release.

Revision ID: dbc5a3a9bcf2
Revises: b9e0f1a2c3d4, e9f0a1b2c3d4, f9b0c1d2e3f4
Create Date: 2026-09-01 21:18:38.004886
"""

from collections.abc import Sequence

revision: str = "dbc5a3a9bcf2"
down_revision: str | Sequence[str] | None = (
    "b9e0f1a2c3d4",
    "e9f0a1b2c3d4",
    "f9b0c1d2e3f4",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge branches without changing schema objects."""


def downgrade() -> None:
    """Split the version graph without changing schema objects."""
