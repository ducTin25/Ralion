from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from src.ai.retrieval_engine.retrieval_engine import (
    RetrievalEngine,
    RetrievalFilters,
    _Candidate,
)
from src.core.telemetry import TraceRecorder, bind_trace, telemetry_span
from src.infrastructure.observability import (
    ImmediateSessionTelemetrySink,
    fingerprint_question,
)
from src.model.enums import DocumentDomain
from src.model.llm_call_log import LlmCallLog
from src.shared.ai.request_budget import RequestBudget


def test_trace_recorder_aggregates_repeated_stages_without_payloads() -> None:
    trace = TraceRecorder("a" * 32)
    with bind_trace(trace):
        with telemetry_span("generation.provider", attempt=1):
            pass
        with telemetry_span("generation.provider", attempt=2):
            pass
        trace.annotate(
            outcome="fallback",
            fallback_reason="validator_fail",
            selected_chunk_ids=[11, 12],
        )

    snapshot = trace.snapshot()
    serialized = json.dumps(
        {
            "attributes": snapshot.attributes,
            "stages": snapshot.stage_timings_ms,
        }
    )
    assert len(snapshot.spans) == 2
    assert "generation.provider" in snapshot.stage_timings_ms
    assert snapshot.attributes["selected_chunk_ids"] == [11, 12]
    assert "question" not in serialized
    assert "chunk_content" not in serialized


@pytest.mark.asyncio
async def test_immediate_sink_persists_v2_terminal_summary(db_session) -> None:
    trace = TraceRecorder("b" * 32)
    conversation_id = uuid.uuid4()
    trace.record_duration("retrieval.embedding", 12.5, attempt=1)
    trace.record_duration("generation.provider", 20.2, attempt=1)
    trace.annotate(
        outcome="success",
        gate_decision="accepted",
        validator_outcome="passed",
        user_id=7,
        knowledge_domain="POLICY",
        conversation_id=conversation_id,
        turn_index=0,
        question_fingerprint="f" * 64,
        candidate_count=5,
        accepted_count=2,
        selected_chunk_ids=[11, 12],
        model="test-model",
        prompt_tokens=10,
        completion_tokens=5,
        repair_retry_count=0,
        prompt_version="grounded-answer-v1",
        retrieval_config_version="retrieval-v1",
        generation_config={"context_max_tokens": 3200},
    )

    await ImmediateSessionTelemetrySink(db_session).submit(trace.snapshot())
    row = await db_session.scalar(
        select(LlmCallLog).where(LlmCallLog.trace_id == "b" * 32)
    )

    assert row is not None
    assert row.stage == "chat_request"
    assert row.observability_version == 2
    assert row.total_latency_ms is not None
    assert row.generation_latency_ms == 20
    assert row.stage_timings_ms["retrieval.embedding"] == 12.5
    assert row.selected_chunk_ids == [11, 12]
    assert row.conversation_id == conversation_id
    assert row.prompt_version == "grounded-answer-v1"
    assert row.retrieval_config_version == "retrieval-v1"
    assert row.generation_config == {"context_max_tokens": 3200}


@pytest.mark.asyncio
async def test_cost_estimate_is_populated_from_token_usage(db_session, monkeypatch) -> None:
    """F-22: cost_estimate must actually be written, priced from config, not left blank."""
    from src.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "chat_cost_per_1k_prompt_tokens_usd", 0.001)
    monkeypatch.setattr(settings, "chat_cost_per_1k_completion_tokens_usd", 0.002)

    trace = TraceRecorder("c" * 32)
    trace.annotate(outcome="success", prompt_tokens=1000, completion_tokens=500)

    await ImmediateSessionTelemetrySink(db_session).submit(trace.snapshot())
    row = await db_session.scalar(select(LlmCallLog).where(LlmCallLog.trace_id == "c" * 32))

    assert row is not None
    assert row.cost_estimate == "0.002000"  # 1000/1000*0.001 + 500/1000*0.002


@pytest.mark.asyncio
async def test_cost_estimate_is_none_when_no_llm_call_was_made(db_session) -> None:
    """A no_evidence/embedding-failure fallback incurs no LLM cost — must stay None, not 0."""
    trace = TraceRecorder("e" * 32)
    trace.annotate(outcome="fallback", fallback_reason="no_evidence")

    await ImmediateSessionTelemetrySink(db_session).submit(trace.snapshot())
    row = await db_session.scalar(select(LlmCallLog).where(LlmCallLog.trace_id == "e" * 32))

    assert row is not None
    assert row.cost_estimate is None


def test_question_fingerprint_is_stable_and_does_not_contain_question() -> None:
    question = "  What is the Leave Policy?  "
    fingerprint = fingerprint_question(question)
    assert fingerprint == fingerprint_question("what is the leave policy?")
    assert len(fingerprint) == 64
    assert question.casefold().strip() not in fingerprint


@pytest.mark.asyncio
async def test_retrieval_records_valuable_stage_boundaries(monkeypatch) -> None:
    chunk = SimpleNamespace(chunk_id=11)
    candidate = _Candidate(
        chunk=chunk,
        knowledge_domain=DocumentDomain.POLICY,
        document_id=1,
        version_id=1,
        score=0.9,
    )

    class Encoder:
        model_version = "test-embedding-v1"

        async def embed_query(self, _text, _budget):
            return [0.0] * 1024

    class Retriever:
        async def retrieve(self, *_args):
            return [candidate]

    engine = RetrievalEngine(SimpleNamespace(), query_encoder=Encoder())
    engine.dense_retriever = Retriever()
    engine.bm25_retriever = Retriever()

    async def allowed(_results, _filters):
        return {11}

    monkeypatch.setattr(engine, "_validate_evidence", allowed)
    trace = TraceRecorder("d" * 32)
    with bind_trace(trace):
        results = await engine.retrieve(
            "leave policy",
            filters=RetrievalFilters(knowledge_domains=frozenset({DocumentDomain.POLICY})),
            budget=RequestBudget(10, 5, 5),
        )

    stages = trace.snapshot().stage_timings_ms
    assert results[0].chunk.chunk_id == 11
    assert {
        "retrieval.embedding",
        "retrieval.dense",
        "retrieval.bm25",
        "retrieval.fusion",
        "retrieval.evidence_scope_validation",
    } <= stages.keys()
