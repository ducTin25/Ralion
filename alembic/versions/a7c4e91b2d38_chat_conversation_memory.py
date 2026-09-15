"""Conversation memory for F5 chat: chat_sessions becomes a conversation aggregate.

Additive only. Existing rows (one session per turn, ASSISTANT message only) survive as
single-turn conversations; the USER question of those turns was never recorded and cannot be
reconstructed, so nothing is backfilled for it.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a7c4e91b2d38"
down_revision: str | Sequence[str] | None = "f3194e228632"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Ràng buộc scope chỉ được thêm sau khi dữ liệu hiện có đã thoả. Fail-fast tường minh thay vì
# NOT VALID âm thầm: một row lệch nghĩa là đã từng có đường ghi bỏ qua ChatService._scope, đó là
# thông tin phải nhìn thấy chứ không phải thứ để bỏ qua.
_SCOPE_CHECK = (
    "(knowledge_domain = 'POLICY' AND project_id IS NULL AND membership_id IS NULL)"
    " OR (knowledge_domain = 'PROJECT' AND project_id IS NOT NULL AND membership_id IS NOT NULL)"
)


def upgrade() -> None:
    op.add_column("chat_sessions", sa.Column("public_id", sa.Uuid(), nullable=True))
    op.execute("UPDATE chat_sessions SET public_id = gen_random_uuid() WHERE public_id IS NULL")
    op.alter_column("chat_sessions", "public_id", nullable=False)
    op.create_unique_constraint(op.f("uq_chat_sessions_public_id"), "chat_sessions", ["public_id"])

    op.add_column("chat_sessions", sa.Column("last_message_at", sa.DateTime(), nullable=True))
    op.execute(
        "UPDATE chat_sessions AS conversation SET last_message_at = ("
        "SELECT max(message.created_at) FROM chat_messages AS message "
        "WHERE message.session_id = conversation.session_id)"
    )
    op.create_index(
        "ix_chat_sessions_user_id_last_message_at",
        "chat_sessions",
        ["user_id", "last_message_at"],
    )

    offending = op.get_bind().execute(
        sa.text(f"SELECT count(*) FROM chat_sessions WHERE NOT ({_SCOPE_CHECK})")
    ).scalar_one()
    if offending:
        raise RuntimeError(
            f"{offending} chat_sessions rows violate the domain/scope pairing invariant. "
            "Inspect them before adding ck_chat_sessions_scope_matches_domain."
        )
    op.create_check_constraint("scope_matches_domain", "chat_sessions", _SCOPE_CHECK)

    op.add_column(
        "chat_messages",
        sa.Column("turn_index", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("chat_messages", "turn_index", server_default=None)
    op.add_column("chat_messages", sa.Column("trace_id", sa.String(length=32), nullable=True))
    op.add_column(
        "chat_messages", sa.Column("fallback_reason", sa.String(length=32), nullable=True)
    )
    op.add_column("chat_messages", sa.Column("retrieval_query", sa.Text(), nullable=True))
    op.create_unique_constraint(
        op.f("uq_chat_messages_session_id"), "chat_messages", ["session_id", "turn_index", "role"]
    )
    op.create_index(
        "ix_chat_messages_session_id_message_id", "chat_messages", ["session_id", "message_id"]
    )

    op.add_column("llm_call_logs", sa.Column("stage", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("llm_call_logs", "stage")

    op.drop_index("ix_chat_messages_session_id_message_id", table_name="chat_messages")
    op.drop_constraint(op.f("uq_chat_messages_session_id"), "chat_messages", type_="unique")
    op.drop_column("chat_messages", "retrieval_query")
    op.drop_column("chat_messages", "fallback_reason")
    op.drop_column("chat_messages", "trace_id")
    op.drop_column("chat_messages", "turn_index")

    op.drop_constraint("ck_chat_sessions_scope_matches_domain", "chat_sessions", type_="check")
    op.drop_index("ix_chat_sessions_user_id_last_message_at", table_name="chat_sessions")
    op.drop_column("chat_sessions", "last_message_at")
    op.drop_constraint(op.f("uq_chat_sessions_public_id"), "chat_sessions", type_="unique")
    op.drop_column("chat_sessions", "public_id")
