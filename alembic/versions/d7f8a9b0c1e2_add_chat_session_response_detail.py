"""Add conversation-scoped response detail preference.

Revision ID: d7f8a9b0c1e2
Revises: f3a4b5c6d7e8
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d7f8a9b0c1e2"
down_revision: str | Sequence[str] | None = "f3a4b5c6d7e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chat_sessions", sa.Column("preferred_response_detail", sa.String(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("chat_sessions", "preferred_response_detail")
