"""Persist structured general guidance for transcript rehydration."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f3a4b5c6d7e8"
down_revision: str | Sequence[str] | None = "f2a3b4c5d6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable keeps this migration safe for existing assistant messages and for older clients;
    # newly generated guidance turns write a structured JSON array.
    op.add_column(
        "chat_messages",
        sa.Column("general_guidance", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "general_guidance")
