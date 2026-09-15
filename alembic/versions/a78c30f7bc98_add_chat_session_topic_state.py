"""Add chat_sessions.topic_subject / topic_entities (server-derived conversation memory).

Revision ID: a78c30f7bc98
Revises: d7f8a9b0c1e2
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a78c30f7bc98"
down_revision: str | Sequence[str] | None = "d7f8a9b0c1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chat_sessions", sa.Column("topic_subject", sa.String(), nullable=True))
    op.add_column("chat_sessions", sa.Column("topic_entities", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_sessions", "topic_entities")
    op.drop_column("chat_sessions", "topic_subject")
