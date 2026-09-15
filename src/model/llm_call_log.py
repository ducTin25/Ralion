from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Integer, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base

_JSON_DOCUMENT = JSON().with_variant(JSONB(), "postgresql")


class LlmCallLog(Base):
    __tablename__ = "llm_call_logs"

    log_id: Mapped[int] = mapped_column(primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    module: Mapped[str] = mapped_column(String(32), nullable=False, default="chat")
    # Nhiều LLM call có thể thuộc cùng một trace_id (query_rewrite rồi generate). Không có cột này
    # thì hai row cùng trace_id không phân biệt được. NULL = row cũ, trước khi tách stage.
    stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    gate_decision: Mapped[str] = mapped_column(String(32), nullable=False)
    validator_outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fallback_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cost_estimate: Mapped[str | None] = mapped_column(String(32), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Observability v2: one terminal ``chat_request`` summary per turn.  The
    # legacy ``latency_ms`` column keeps its old per-operation meaning.
    observability_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    project_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    membership_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    knowledge_domain: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    conversation_id: Mapped[UUID | None] = mapped_column(Uuid(), nullable=True)
    turn_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    question_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    total_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generation_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stage_timings_ms: Mapped[dict | None] = mapped_column(_JSON_DOCUMENT, nullable=True)
    retrieval_attempt_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    candidate_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    accepted_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    selected_chunk_ids: Mapped[list | None] = mapped_column(_JSON_DOCUMENT, nullable=True)
    retrieval_scores: Mapped[list | None] = mapped_column(_JSON_DOCUMENT, nullable=True)
    decision_details: Mapped[dict | None] = mapped_column(_JSON_DOCUMENT, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    repair_retry_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_retry_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_retry_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retrieval_config_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # The provenance migration created this column as portable JSON (not PostgreSQL JSONB).
    # Keep the model identical so Alembic autogenerate remains drift-free.
    generation_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
