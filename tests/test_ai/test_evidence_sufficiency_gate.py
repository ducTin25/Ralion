"""Unit tests for the post-retrieval evidence-sufficiency gate (weakness #2 remainder,
CHANGE_LOG.md 2026-08-21).

No live LLM here -- a fake `ChatCompletionPort` records what it was asked and returns a canned
verdict. This pins the *contract* (fail-closed, one call, JSON parsing, chunk-id validation,
secret redaction, disabled = no-op); the gate's actual judging accuracy against real questions is
proven separately by a real eval run against the golden fixture, recorded in CHANGE_LOG.md, since
no fake here could stand in for that.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.ai.orchestration.evidence_sufficiency_gate import (
    EvidenceSufficiencyGate,
    EvidenceSufficiencyGateConfig,
    EvidenceSufficiencyVerdict,
)
from src.ai.retrieval_engine.retrieval_engine import RetrievalResult
from src.model.enums import DocumentDomain
from src.shared.ai.external_failures import ExternalFailureCode, ExternalServiceFailure
from src.shared.ai.request_budget import RequestBudget


def _candidate(chunk_id: int = 11) -> RetrievalResult:
    return RetrievalResult(
        chunk=SimpleNamespace(
            chunk_id=chunk_id,
            content="Run cargo test before submitting a pull request.",
            section_path="Tests",
            heading=None,
        ),
        knowledge_domain=DocumentDomain.PROJECT,
        document_id=1,
        version_id=1,
        dense_score=0.70,
        hybrid_score=0.03,
    )


class _FakeProvider:
    def __init__(self, verdict) -> None:
        self.verdict = verdict
        self.calls: list[tuple[list[tuple[str, str]], str]] = []

    async def complete(self, messages, _budget, operation):
        self.calls.append((list(messages), operation))
        if isinstance(self.verdict, Exception):
            raise self.verdict
        return SimpleNamespace(content=self.verdict)


def _budget() -> RequestBudget:
    return RequestBudget(30.0, 0.0, 30.0, 0.0)


@pytest.mark.asyncio
async def test_disabled_config_never_calls_the_provider() -> None:
    provider = _FakeProvider('{"verdict": "INSUFFICIENT", "supporting_chunk_ids": []}')
    gate = EvidenceSufficiencyGate(provider, EvidenceSufficiencyGateConfig(enabled=False))

    result = await gate.check("What is the leave policy?", [_candidate()], _budget())

    assert result.sufficient is True
    assert result.verdict is EvidenceSufficiencyVerdict.SUFFICIENT
    assert result.errored is False
    assert provider.calls == []


@pytest.mark.asyncio
async def test_sufficient_verdict_keeps_valid_chunk_ids() -> None:
    provider = _FakeProvider('{"verdict": "SUFFICIENT", "supporting_chunk_ids": [11]}')
    gate = EvidenceSufficiencyGate(provider, EvidenceSufficiencyGateConfig(enabled=True))

    result = await gate.check("How do I run tests?", [_candidate(11)], _budget())

    assert result.sufficient is True
    assert result.verdict is EvidenceSufficiencyVerdict.SUFFICIENT
    assert result.errored is False
    assert result.supporting_chunk_ids == frozenset({11})
    assert provider.calls[0][1] == "evidence_sufficiency_gate"


@pytest.mark.asyncio
async def test_insufficient_verdict_is_not_sufficient_but_not_errored() -> None:
    """A genuine NO must be distinguishable from an internal fault -- chat_service.py maps this
    to fallback_reason='insufficient_evidence', never 'system_error' (invariant 8)."""
    provider = _FakeProvider('{"verdict": "INSUFFICIENT", "supporting_chunk_ids": []}')
    gate = EvidenceSufficiencyGate(provider, EvidenceSufficiencyGateConfig(enabled=True))

    result = await gate.check("What is the storage cost per GB?", [_candidate()], _budget())

    assert result.sufficient is False
    assert result.verdict is EvidenceSufficiencyVerdict.INSUFFICIENT
    assert result.errored is False


@pytest.mark.asyncio
async def test_partial_verdict_is_sufficient_when_enabled() -> None:
    """Implementation spec §9.2/§9.4: PARTIAL still proceeds to generation (`.sufficient`), but
    stays a distinguishable verdict from SUFFICIENT for chat_service.py's honesty-note dispatch."""
    provider = _FakeProvider('{"verdict": "PARTIAL", "supporting_chunk_ids": [11]}')
    gate = EvidenceSufficiencyGate(
        provider, EvidenceSufficiencyGateConfig(enabled=True, partial_verdict_enabled=True)
    )

    result = await gate.check("A composite question", [_candidate(11)], _budget())

    assert result.sufficient is True
    assert result.verdict is EvidenceSufficiencyVerdict.PARTIAL
    assert result.errored is False


@pytest.mark.asyncio
async def test_partial_verdict_coerces_to_insufficient_when_disabled() -> None:
    """§14 Phase 0 gating: a verdict this deployment hasn't enabled must never reach the caller,
    even if the judge renders it -- coerced down to the safe INSUFFICIENT default."""
    provider = _FakeProvider('{"verdict": "PARTIAL", "supporting_chunk_ids": [11]}')
    gate = EvidenceSufficiencyGate(
        provider, EvidenceSufficiencyGateConfig(enabled=True, partial_verdict_enabled=False)
    )

    result = await gate.check("A composite question", [_candidate(11)], _budget())

    assert result.sufficient is False
    assert result.verdict is EvidenceSufficiencyVerdict.INSUFFICIENT
    assert result.errored is False


@pytest.mark.asyncio
async def test_ambiguous_verdict_coerces_to_insufficient_by_default() -> None:
    """AMBIGUOUS defaults OFF in this implementation pass -- no live LLM/golden-fixture sweep was
    available to measure the judge's precision on it (CHANGE_LOG.md), so it is a documented,
    config-gated deferral, not a design rejection."""
    provider = _FakeProvider('{"verdict": "AMBIGUOUS", "supporting_chunk_ids": []}')
    gate = EvidenceSufficiencyGate(provider, EvidenceSufficiencyGateConfig(enabled=True))

    result = await gate.check("An ambiguous question", [_candidate()], _budget())

    assert result.sufficient is False
    assert result.verdict is EvidenceSufficiencyVerdict.INSUFFICIENT
    assert result.errored is False


@pytest.mark.asyncio
async def test_ambiguous_verdict_passes_through_when_explicitly_enabled() -> None:
    provider = _FakeProvider('{"verdict": "AMBIGUOUS", "supporting_chunk_ids": []}')
    gate = EvidenceSufficiencyGate(
        provider, EvidenceSufficiencyGateConfig(enabled=True, ambiguous_verdict_enabled=True)
    )

    result = await gate.check("An ambiguous question", [_candidate()], _budget())

    assert result.sufficient is False
    assert result.verdict is EvidenceSufficiencyVerdict.AMBIGUOUS
    assert result.errored is False


@pytest.mark.asyncio
async def test_markdown_fenced_json_is_still_parsed() -> None:
    provider = _FakeProvider('```json\n{"verdict": "SUFFICIENT", "supporting_chunk_ids": [11]}\n```')
    gate = EvidenceSufficiencyGate(provider, EvidenceSufficiencyGateConfig(enabled=True))

    result = await gate.check("How do I run tests?", [_candidate(11)], _budget())

    assert result.sufficient is True
    assert result.errored is False


@pytest.mark.asyncio
async def test_hallucinated_chunk_id_is_dropped_from_supporting_ids() -> None:
    """The judge only ever sees real chunk_ids in its prompt; any id it returns that isn't in the
    accepted set is a malformed/hallucinated reference and must not leak downstream."""
    provider = _FakeProvider('{"verdict": "SUFFICIENT", "supporting_chunk_ids": [11, 999]}')
    gate = EvidenceSufficiencyGate(provider, EvidenceSufficiencyGateConfig(enabled=True))

    result = await gate.check("How do I run tests?", [_candidate(11)], _budget())

    assert result.supporting_chunk_ids == frozenset({11})


@pytest.mark.asyncio
async def test_provider_failure_fails_closed() -> None:
    """The central guarantee of this gate, opposite of ScopeGate: a hiccup must never let an
    unverified answer through. Covers both a raw exception and the SDK's own typed failure."""
    for failure in (
        RuntimeError("boom"),
        ExternalServiceFailure("llm", ExternalFailureCode.TIMEOUT, True, timeout_scope="attempt"),
    ):
        provider = _FakeProvider(failure)
        gate = EvidenceSufficiencyGate(
            provider, EvidenceSufficiencyGateConfig(enabled=True, timeout_seconds=1.0)
        )

        result = await gate.check("any question", [_candidate()], _budget())

        assert result.sufficient is False
        assert result.errored is True


@pytest.mark.asyncio
async def test_unparseable_output_fails_closed() -> None:
    """Unlike ScopeGate's single-word contract, a malformed JSON verdict has no safe partial
    reading -- garbage output must fail CLOSED, not be coerced into a pass."""
    provider = _FakeProvider("I'm not sure how to judge this, could you clarify?")
    gate = EvidenceSufficiencyGate(provider, EvidenceSufficiencyGateConfig(enabled=True))

    result = await gate.check("some question", [_candidate()], _budget())

    assert result.sufficient is False
    assert result.errored is True


@pytest.mark.asyncio
async def test_unknown_verdict_value_fails_closed() -> None:
    provider = _FakeProvider('{"verdict": "MAYBE", "supporting_chunk_ids": []}')
    gate = EvidenceSufficiencyGate(provider, EvidenceSufficiencyGateConfig(enabled=True))

    result = await gate.check("some question", [_candidate()], _budget())

    assert result.sufficient is False
    assert result.errored is True


@pytest.mark.asyncio
async def test_legacy_answerable_field_fails_closed() -> None:
    """The v1 boolean-`answerable` wire shape is no longer understood (prompt v2 always asks
    for `verdict`) -- a stray old-shaped response must fail CLOSED, not be silently accepted."""
    provider = _FakeProvider('{"answerable": true, "supporting_chunk_ids": [11]}')
    gate = EvidenceSufficiencyGate(provider, EvidenceSufficiencyGateConfig(enabled=True))

    result = await gate.check("some question", [_candidate(11)], _budget())

    assert result.sufficient is False
    assert result.errored is True


@pytest.mark.asyncio
async def test_question_is_wrapped_and_secret_redacted() -> None:
    """Same egress discipline as ScopeGate/LlmQueryRewriter (F-11/F-23): delimiter-wrapped, any
    secret pattern redacted before it ever leaves the process."""
    provider = _FakeProvider('{"answerable": true, "supporting_chunk_ids": [11]}')
    gate = EvidenceSufficiencyGate(provider, EvidenceSufficiencyGateConfig(enabled=True))
    secret_bearing = "day la aws key cua toi: AKIAIOSFODNN7EXAMPLE"

    await gate.check(secret_bearing, [_candidate(11)], _budget())

    sent_messages, _operation = provider.calls[0]
    human_message = next(content for role, content in sent_messages if role == "human")
    assert "START (UNTRUSTED CONTENT)" in human_message
    assert "AKIAIOSFODNN7EXAMPLE" not in human_message
    assert "chunk_id: 11" in human_message


@pytest.mark.asyncio
async def test_v3_prompt_requires_separable_parts_before_partial() -> None:
    """First measured precision of PARTIAL, run_20260825T132725Z: it fired on 2 of 7
    `unanswerable` cases and BOTH became a false answer. Both were SINGLE-FACT questions ("mức
    phạt bao nhiêu tiền?", "which operator does the project ship?") where the evidence was merely
    adjacent -- the situation INSUFFICIENT already defines ("being topically close is not being an
    answer"). The v2 wording said "composite/multi-aspect" but never made it a precondition to
    check, so the judge used PARTIAL as a soft INSUFFICIENT and the turn answered around the
    question. Text assertion, same discipline as `test_ti09`: whether the judge OBEYS this is live
    eval, but the precondition must not be silently deleted from the prompt again."""
    from src.ai.orchestration.evidence_sufficiency_gate import (
        EVIDENCE_SUFFICIENCY_GATE_PROMPT_VERSION,
    )

    provider = _FakeProvider('{"verdict": "INSUFFICIENT", "supporting_chunk_ids": []}')
    gate = EvidenceSufficiencyGate(provider, EvidenceSufficiencyGateConfig(enabled=True))

    await gate.check("Mức phạt là bao nhiêu?", [_candidate()], _budget())

    system_message = provider.calls[0][0][0][1]
    assert "PARTIAL REQUIRES A QUESTION WITH SEPARABLE PARTS" in system_message
    assert "has no parts to split" in system_message
    assert "Never use PARTIAL to mean 'related but the answer is missing'" in system_message
    # INSUFFICIENT must keep owning that case -- the two verdicts are only distinguishable while
    # both halves of the boundary are stated.
    assert "being topically close" in system_message
    assert EVIDENCE_SUFFICIENCY_GATE_PROMPT_VERSION == "evidence-sufficiency-gate-v3"
