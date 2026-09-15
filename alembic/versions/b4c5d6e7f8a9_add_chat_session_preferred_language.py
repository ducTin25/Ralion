"""Add chat_sessions.preferred_language.

CHANGE_LOG.md 2026-08-23 stateful diagnostic, item 2: an explicit in-chat language-switch request
("bạn nói tiếng việt đi") had no state to persist into -- `presentation.language` is turn-local
only by design (rev. 2 §7.2(a)), and the only *durable* preference is `User`-scoped
(PATCH /auth/me, PERSONALIZE_CHATBOT_SPEC.md §0.4). Neither covers "remember this for the rest of
THIS conversation", which is what a mid-chat language request actually means. This column is that
missing middle tier, scoped to one `ChatSession` row, nullable (NULL = no explicit switch yet,
falls through to the existing per-turn heuristic unchanged).

Revision ID: b4c5d6e7f8a9
Revises: a3f8c1d29e47
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b4c5d6e7f8a9"
down_revision: str | Sequence[str] | None = "a3f8c1d29e47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chat_sessions", sa.Column("preferred_language", sa.String(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("chat_sessions", "preferred_language")
