from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime

import pytest

from src.model.enums import RuleEvidenceType
from src.model.raw_pr_comment import RawPrComment
from src.modules.knowledge.mining.evidence_grouping import EvidenceUnit
from src.modules.knowledge.mining.rule_extraction import (
    MAX_CONCURRENT_LLM_CALLS,
    NO_EXPLICIT_RATIONALE,
    extract_rule_candidate,
    extract_rule_candidates,
)


@dataclass
class _StubResponse:
    content: str
    response_metadata: dict = field(default_factory=dict)
    usage_metadata: dict = field(default_factory=dict)


class _StubLLM:
    def __init__(self, payload: dict | None = None, *, raise_error: Exception | None = None) -> None:
        self._payload = payload
        self._raise_error = raise_error

    async def ainvoke(self, messages, config=None):
        if self._raise_error:
            raise self._raise_error
        return _StubResponse(json.dumps(self._payload), response_metadata={"model_name": "stub-model"})


def _unit(body: str = "avoid double-negative boolean naming") -> EvidenceUnit:
    row = RawPrComment(
        raw_pr_comment_id=1,
        repo="acme/widgets",
        pr_number=1,
        pr_author="pr-author",
        type="review_comment(diff)",
        author="alice",
        is_bot_comment=False,
        body=body,
        review_state=None,
        in_reply_to_id=None,
        url="https://x/1",
        created_at=datetime(2025, 8, 1),
        secret_scanned_at=datetime(2025, 8, 1),
    )
    return EvidenceUnit(pr_number=1, comments=(row,))


@pytest.mark.asyncio
async def test_extraction_parses_valid_json_response() -> None:
    llm = _StubLLM(
        {
            "evidence_type": "REUSABLE_CORRECTION",
            "reuse_scope": 2,
            "rule_text_draft": "Avoid double-negative boolean naming.",
            "rationale": NO_EXPLICIT_RATIONALE,
        }
    )
    result = await extract_rule_candidate(llm, _unit())
    assert result.evidence_type == RuleEvidenceType.REUSABLE_CORRECTION
    assert result.reuse_scope == 2
    assert result.rule_text_draft == "Avoid double-negative boolean naming."
    assert result.eligible is True
    assert result.error is None


@pytest.mark.asyncio
async def test_missing_rationale_defaults_to_fixed_string() -> None:
    llm = _StubLLM(
        {
            "evidence_type": "CONVENTION",
            "reuse_scope": 1,
            "rule_text_draft": "Follow the style guide.",
            "rationale": "",
        }
    )
    result = await extract_rule_candidate(llm, _unit())
    assert result.rationale == NO_EXPLICIT_RATIONALE


@pytest.mark.asyncio
async def test_local_correction_is_not_eligible() -> None:
    llm = _StubLLM(
        {
            "evidence_type": "LOCAL_CORRECTION",
            "reuse_scope": 0,
            "rule_text_draft": "",
            "rationale": NO_EXPLICIT_RATIONALE,
        }
    )
    result = await extract_rule_candidate(llm, _unit())
    assert result.eligible is False


@pytest.mark.asyncio
async def test_reuse_scope_zero_is_not_eligible_even_if_type_matches() -> None:
    llm = _StubLLM(
        {
            "evidence_type": "REUSABLE_CORRECTION",
            "reuse_scope": 0,
            "rule_text_draft": "",
            "rationale": NO_EXPLICIT_RATIONALE,
        }
    )
    result = await extract_rule_candidate(llm, _unit())
    assert result.eligible is False


@pytest.mark.asyncio
async def test_malformed_json_degrades_to_ineligible_result_without_raising() -> None:
    class _BrokenLLM:
        async def ainvoke(self, messages, config=None):
            return _StubResponse("not valid json{{{")

    result = await extract_rule_candidate(_BrokenLLM(), _unit())
    assert result.eligible is False
    assert result.evidence_type == RuleEvidenceType.NOISE_OTHER
    assert result.error is not None


@pytest.mark.asyncio
async def test_llm_exception_degrades_to_ineligible_result_without_raising() -> None:
    llm = _StubLLM(raise_error=RuntimeError("provider timeout"))
    result = await extract_rule_candidate(llm, _unit())
    assert result.eligible is False
    assert result.error == "provider timeout"


# ------------------------------------------------------- extract_rule_candidates() concurrency


def _unit_n(n: int, body: str) -> EvidenceUnit:
    row = RawPrComment(
        raw_pr_comment_id=n,
        repo="acme/widgets",
        pr_number=n,
        pr_author="pr-author",
        type="review_comment(diff)",
        author="alice",
        is_bot_comment=False,
        body=body,
        review_state=None,
        in_reply_to_id=None,
        url=f"https://x/{n}",
        created_at=datetime(2025, 8, 1),
        secret_scanned_at=datetime(2025, 8, 1),
    )
    return EvidenceUnit(pr_number=n, comments=(row,))


class _DelayedKeywordLLM:
    """Returns a fixed payload keyed by a substring match, after an artificial per-call delay
    — used to force LLM calls to *complete* out of order even though they're dispatched in a
    fixed order, so tests can prove result order never depends on completion order."""

    def __init__(self, rules: list[tuple[str, dict]], delays: dict[str, float]) -> None:
        self._rules = rules
        self._delays = delays
        self.max_concurrent_seen = 0
        self._in_flight = 0

    async def ainvoke(self, messages, config=None):
        user_content = messages[1][1]
        self._in_flight += 1
        self.max_concurrent_seen = max(self.max_concurrent_seen, self._in_flight)
        try:
            for keyword, delay in self._delays.items():
                if keyword in user_content:
                    await asyncio.sleep(delay)
                    break
            for keyword, payload in self._rules:
                if keyword in user_content:
                    return _StubResponse(json.dumps(payload), response_metadata={"model_name": "stub"})
            raise AssertionError(f"no stub rule matched user content: {user_content!r}")
        finally:
            self._in_flight -= 1


def _eligible_payload(text: str) -> dict:
    return {
        "evidence_type": "REUSABLE_CORRECTION",
        "reuse_scope": 1,
        "rule_text_draft": text,
        "rationale": NO_EXPLICIT_RATIONALE,
    }


@pytest.mark.asyncio
async def test_extract_rule_candidates_result_order_matches_input_order_despite_reordered_completion() -> None:
    # unit-A is dispatched first but finishes LAST; unit-C is dispatched last but finishes
    # FIRST — completion order is the exact reverse of input order.
    units = [_unit_n(1, "keyword-A"), _unit_n(2, "keyword-B"), _unit_n(3, "keyword-C")]
    llm = _DelayedKeywordLLM(
        rules=[
            ("keyword-A", _eligible_payload("rule A")),
            ("keyword-B", _eligible_payload("rule B")),
            ("keyword-C", _eligible_payload("rule C")),
        ],
        delays={"keyword-A": 0.3, "keyword-B": 0.15, "keyword-C": 0.0},
    )

    results = await extract_rule_candidates(llm, units)

    # Positional correspondence to `units` must hold regardless of completion timing.
    assert [r.unit.pr_number for r in results] == [1, 2, 3]
    assert [r.rule_text_draft for r in results] == ["rule A", "rule B", "rule C"]


@pytest.mark.asyncio
async def test_extract_rule_candidates_bounds_concurrency_to_max_constant() -> None:
    units = [_unit_n(i, f"keyword-{i}") for i in range(10)]
    llm = _DelayedKeywordLLM(
        rules=[(f"keyword-{i}", _eligible_payload(f"rule {i}")) for i in range(10)],
        delays={f"keyword-{i}": 0.05 for i in range(10)},  # force overlap so the bound is exercised
    )

    results = await extract_rule_candidates(llm, units)

    assert len(results) == 10
    assert llm.max_concurrent_seen <= MAX_CONCURRENT_LLM_CALLS
    assert llm.max_concurrent_seen > 1  # sanity: calls did actually overlap, not accidentally serial


@pytest.mark.asyncio
async def test_extract_rule_candidates_one_failure_does_not_affect_others() -> None:
    units = [_unit_n(1, "keyword-ok1"), _unit_n(2, "keyword-boom"), _unit_n(3, "keyword-ok2")]

    class _PartiallyBrokenLLM(_DelayedKeywordLLM):
        async def ainvoke(self, messages, config=None):
            if "keyword-boom" in messages[1][1]:
                raise RuntimeError("provider timeout")
            return await super().ainvoke(messages)

    llm = _PartiallyBrokenLLM(
        rules=[
            ("keyword-ok1", _eligible_payload("rule 1")),
            ("keyword-ok2", _eligible_payload("rule 2")),
        ],
        delays={},
    )

    results = await extract_rule_candidates(llm, units)

    assert [r.eligible for r in results] == [True, False, True]
    assert results[1].error == "provider timeout"
    assert results[0].rule_text_draft == "rule 1"
    assert results[2].rule_text_draft == "rule 2"
