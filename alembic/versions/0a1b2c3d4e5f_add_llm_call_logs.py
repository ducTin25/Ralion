"""Add mandatory operational logs for LLM calls."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0a1b2c3d4e5f"
down_revision: str | Sequence[str] | None = "0c1d2e3f4a5b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_call_logs",
        sa.Column("log_id", sa.Integer(), primary_key=True),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("module", sa.String(length=32), nullable=False, server_default="chat"),
        sa.Column("gate_decision", sa.String(length=32), nullable=False),
        sa.Column("validator_outcome", sa.String(length=32)),
        sa.Column("fallback_reason", sa.String(length=32)),
        sa.Column("prompt_tokens", sa.Integer()),
        sa.Column("completion_tokens", sa.Integer()),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("model", sa.String(length=128)),
        sa.Column("cost_estimate", sa.String(length=32)),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_llm_call_logs_trace_id", "llm_call_logs", ["trace_id"])


def downgrade() -> None:
    op.drop_index("ix_llm_call_logs_trace_id", table_name="llm_call_logs")
    op.drop_table("llm_call_logs")
