"""Add privacy-safe terminal chat observability fields."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d1e2f3a4b5c6"
down_revision: str | Sequence[str] | None = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = [
        sa.Column("observability_version", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("membership_id", sa.Integer(), nullable=True),
        sa.Column("knowledge_domain", sa.String(length=16), nullable=True),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("turn_index", sa.Integer(), nullable=True),
        sa.Column("question_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("total_latency_ms", sa.Integer(), nullable=True),
        sa.Column("generation_latency_ms", sa.Integer(), nullable=True),
        sa.Column("stage_timings_ms", postgresql.JSONB(), nullable=True),
        sa.Column("retrieval_attempt_count", sa.Integer(), nullable=True),
        sa.Column("candidate_count", sa.Integer(), nullable=True),
        sa.Column("accepted_count", sa.Integer(), nullable=True),
        sa.Column("selected_chunk_ids", postgresql.JSONB(), nullable=True),
        sa.Column("retrieval_scores", postgresql.JSONB(), nullable=True),
        sa.Column("decision_details", postgresql.JSONB(), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=True),
        sa.Column("repair_retry_count", sa.Integer(), nullable=True),
        sa.Column("provider_retry_count", sa.Integer(), nullable=True),
        sa.Column("embedding_retry_count", sa.Integer(), nullable=True),
        sa.Column("error_stage", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
    ]
    for column in columns:
        op.add_column("llm_call_logs", column)
    op.create_index("ix_llm_call_logs_outcome", "llm_call_logs", ["outcome"])
    op.create_index(
        "ix_llm_call_logs_knowledge_domain", "llm_call_logs", ["knowledge_domain"]
    )


def downgrade() -> None:
    op.drop_index("ix_llm_call_logs_knowledge_domain", table_name="llm_call_logs")
    op.drop_index("ix_llm_call_logs_outcome", table_name="llm_call_logs")
    for name in reversed(
        [
            "observability_version",
            "outcome",
            "user_id",
            "project_id",
            "membership_id",
            "knowledge_domain",
            "conversation_id",
            "turn_index",
            "question_fingerprint",
            "total_latency_ms",
            "generation_latency_ms",
            "stage_timings_ms",
            "retrieval_attempt_count",
            "candidate_count",
            "accepted_count",
            "selected_chunk_ids",
            "retrieval_scores",
            "decision_details",
            "provider",
            "repair_retry_count",
            "provider_retry_count",
            "embedding_retry_count",
            "error_stage",
            "error_code",
        ]
    ):
        op.drop_column("llm_call_logs", name)
