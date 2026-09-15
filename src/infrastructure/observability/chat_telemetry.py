"""Fail-open exporters for chat telemetry.

The request path only serializes one safe JSON line and performs a bounded
``put_nowait``. Database and Langfuse I/O run in a background worker.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config import get_settings
from src.core.telemetry import TelemetrySink, TelemetrySnapshot
from src.model.llm_call_log import LlmCallLog
from src.model.session import AsyncSessionLocal

logger = logging.getLogger("chat_observability")
_QUEUE_SIZE = 512
_LANGFUSE_CLIENT: Any | None = None


def fingerprint_question(question: str) -> str:
    """Stable non-reversible correlation token; the question is never exported."""
    normalized = " ".join(question.casefold().split()).encode("utf-8")
    key = get_settings().session_secret.encode("utf-8")
    return hmac.new(key, normalized, hashlib.sha256).hexdigest()


def _safe_error_code(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    allowed = {
        "provider_timeout",
        "provider_error",
        "embedding_unavailable",
        "retrieval_unavailable",
        "persistence_error",
        "unexpected_error",
        "validator_fail",
        "request_rejected",
        "connection",
        "timeout",
        "rate_limited",
        "unavailable",
        "authentication",
        "bad_request",
        "protocol",
        "rate_limit",
        "daily_request_cap",
        "daily_cost_cap",
        "project_daily_cost_cap",
    }
    return text if text in allowed else "unexpected_error"


def _cost_estimate(data: dict[str, Any]) -> str | None:
    """F-22: derive a USD cost estimate from tracked token usage, config-priced.

    Returns None when no LLM call was actually made this turn (no_evidence, embedding
    failure) — those turns cost $0 and must not be conflated with "not measured".
    """
    prompt_tokens = data.get("prompt_tokens")
    completion_tokens = data.get("completion_tokens")
    if not prompt_tokens and not completion_tokens:
        return None
    settings = get_settings()
    cost = (
        (prompt_tokens or 0) / 1000 * settings.chat_cost_per_1k_prompt_tokens_usd
        + (completion_tokens or 0) / 1000 * settings.chat_cost_per_1k_completion_tokens_usd
    )
    return f"{cost:.6f}"


def _row(snapshot: TelemetrySnapshot) -> LlmCallLog:
    data = snapshot.attributes
    return LlmCallLog(
        trace_id=snapshot.trace_id,
        module="chat",
        stage="chat_request",
        gate_decision=str(data.get("gate_decision", "not_reached")),
        validator_outcome=data.get("validator_outcome"),
        fallback_reason=data.get("fallback_reason"),
        prompt_tokens=data.get("prompt_tokens"),
        completion_tokens=data.get("completion_tokens"),
        model=data.get("model"),
        cost_estimate=_cost_estimate(data),
        retry_count=int(data.get("repair_retry_count", 0)),
        observability_version=2,
        outcome=data.get("outcome"),
        user_id=data.get("user_id"),
        project_id=data.get("project_id"),
        membership_id=data.get("membership_id"),
        knowledge_domain=data.get("knowledge_domain"),
        conversation_id=data.get("conversation_id"),
        turn_index=data.get("turn_index"),
        question_fingerprint=data.get("question_fingerprint"),
        total_latency_ms=snapshot.total_latency_ms,
        generation_latency_ms=round(snapshot.stage_timings_ms.get("generation.provider", 0)),
        stage_timings_ms=snapshot.stage_timings_ms,
        retrieval_attempt_count=data.get("retrieval_attempt_count"),
        candidate_count=data.get("candidate_count"),
        accepted_count=data.get("accepted_count"),
        selected_chunk_ids=data.get("selected_chunk_ids"),
        retrieval_scores=data.get("retrieval_scores"),
        decision_details=data.get("decision_details"),
        provider=data.get("provider"),
        repair_retry_count=data.get("repair_retry_count"),
        provider_retry_count=data.get("provider_retry_count"),
        embedding_retry_count=data.get("embedding_retry_count"),
        error_stage=data.get("error_stage"),
        error_code=_safe_error_code(data.get("external_failure_code") or data.get("error_code")),
        prompt_version=data.get("prompt_version"),
        retrieval_config_version=data.get("retrieval_config_version"),
        generation_config=data.get("generation_config"),
    )


def _terminal_log(snapshot: TelemetrySnapshot) -> None:
    data = snapshot.attributes
    timings = snapshot.stage_timings_ms
    slowest = max(timings, key=timings.get) if timings else None
    event = "chat.failed" if data.get("outcome") == "error" else "chat.completed"
    payload = {
        "event": event,
        "trace_id": snapshot.trace_id,
        "outcome": data.get("outcome"),
        "fallback_reason": data.get("fallback_reason"),
        "error_stage": data.get("error_stage"),
        "error_code": _safe_error_code(data.get("error_code")),
        "external_service": data.get("external_service"),
        "external_failure_code": data.get("external_failure_code"),
        "timeout_scope": data.get("timeout_scope"),
        "operation": data.get("external_operation"),
        "provider_exception_type": data.get("provider_exception_type"),
        "provider_status_code": data.get("provider_status_code"),
        "provider_error_message": data.get("provider_error_message"),
        "provider_request_id": data.get("provider_request_id"),
        "provider_endpoint": data.get("provider_endpoint"),
        "provider_prompt_message_count": data.get("provider_prompt_message_count"),
        "provider_prompt_characters": data.get("provider_prompt_characters"),
        "provider_prompt_token_estimate": data.get("provider_prompt_token_estimate"),
        "remaining_budget_ms": data.get("remaining_budget_ms"),
        "knowledge_domain": data.get("knowledge_domain"),
        "total_latency_ms": snapshot.total_latency_ms,
        "slowest_stage": slowest,
        "slowest_stage_ms": timings.get(slowest) if slowest else None,
    }
    log = logger.error if data.get("external_failure_code") == "authentication" else logger.info
    log(json.dumps({key: value for key, value in payload.items() if value is not None}, sort_keys=True))


def _export_langfuse(snapshot: TelemetrySnapshot) -> None:
    """Metadata-only export. SDK absence/configuration failure is a normal no-op."""
    settings = get_settings()
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return
    try:
        global _LANGFUSE_CLIENT
        from src.infrastructure.observability.langfuse import get_langfuse_client

        if _LANGFUSE_CLIENT is None:
            _LANGFUSE_CLIENT = get_langfuse_client()
        if _LANGFUSE_CLIENT is None:
            return
        client = _LANGFUSE_CLIENT
        start = getattr(client, "start_observation", None)
        if start is None:
            return
        root = start(
            name="chat.request",
            as_type="span",
            trace_context={"trace_id": snapshot.trace_id},
            metadata={
                "external_trace_id": snapshot.trace_id,
                "outcome": snapshot.attributes.get("outcome"),
                "knowledge_domain": snapshot.attributes.get("knowledge_domain"),
                "measured_total_latency_ms": snapshot.total_latency_ms,
                "stage_timings_ms": snapshot.stage_timings_ms,
            },
        )
        child_start = getattr(root, "start_observation", start)
        for item in snapshot.spans:
            child = child_start(
                name=item.name,
                as_type="generation" if item.name == "generation.provider" else "span",
                metadata={
                    **item.attributes,
                    "measured_duration_ms": round(item.duration_ms, 3),
                    "start_offset_ms": round(item.start_offset_ms, 3),
                },
            )
            if hasattr(child, "end"):
                child.end()
        if hasattr(root, "end"):
            root.end()
    except Exception:  # noqa: BLE001 - telemetry must never affect chat
        logger.warning('{"event":"telemetry.langfuse_export_failed"}')


class ImmediateSessionTelemetrySink(TelemetrySink):
    """Deterministic test adapter; production uses the queued sink below."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def submit(self, snapshot: TelemetrySnapshot) -> None:
        _terminal_log(snapshot)
        try:
            self.session.add(_row(snapshot))
            await self.session.commit()
        except Exception:  # noqa: BLE001
            await self.session.rollback()


class QueuedChatTelemetrySink(TelemetrySink):
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self.factory = factory
        self.queue: asyncio.Queue[TelemetrySnapshot | None] = asyncio.Queue(maxsize=_QUEUE_SIZE)
        self.worker: asyncio.Task[None] | None = None

    async def submit(self, snapshot: TelemetrySnapshot) -> None:
        _terminal_log(snapshot)
        if self.worker is None or self.worker.done():
            self.worker = asyncio.create_task(self._run(), name="chat-telemetry-exporter")
        try:
            self.queue.put_nowait(snapshot)
        except asyncio.QueueFull:
            logger.warning('{"event":"telemetry.dropped","reason":"queue_full"}')

    async def _run(self) -> None:
        while True:
            item = await self.queue.get()
            try:
                if item is None:
                    return
                try:
                    async with self.factory() as session:
                        session.add(_row(item))
                        await session.commit()
                except Exception:  # noqa: BLE001
                    logger.warning('{"event":"telemetry.persistence_failed"}')
                await asyncio.to_thread(_export_langfuse, item)
            finally:
                self.queue.task_done()

    async def shutdown(self) -> None:
        if self.worker is None:
            return
        try:
            await asyncio.wait_for(self.queue.join(), timeout=2.0)
        except TimeoutError:
            logger.warning('{"event":"telemetry.shutdown_timeout"}')
        self.queue.put_nowait(None)
        try:
            await asyncio.wait_for(self.worker, timeout=2.0)
        except TimeoutError:
            self.worker.cancel()
        if _LANGFUSE_CLIENT is not None and hasattr(_LANGFUSE_CLIENT, "flush"):
            try:
                await asyncio.wait_for(asyncio.to_thread(_LANGFUSE_CLIENT.flush), timeout=2.0)
            except Exception:  # noqa: BLE001
                logger.warning('{"event":"telemetry.langfuse_flush_failed"}')


chat_telemetry_sink = QueuedChatTelemetrySink(AsyncSessionLocal)


async def shutdown_chat_telemetry() -> None:
    await chat_telemetry_sink.shutdown()
