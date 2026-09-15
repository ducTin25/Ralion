"""Focused regression coverage for `_run_behavioral_case`'s route-check semantics (2026-08-30
measurement fix).

`expected_route` on every adversarial/guardrail golden case is set uniformly to KNOWLEDGE
regardless of whether the case's real contract (its `pass_criteria`) wants a refusal or a real
answer. A route mismatch on a turn that safely refused (`result.fallback=True`) used to fail the
case anyway -- these tests pin the fixed contract: the route check only fires when the system
actually produced content through the wrong route.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from eval.run_suite import _run_behavioral_case
from eval.shared.golden_schema import GoldenCase


def _case(*, expected_route: str | None = "KNOWLEDGE", pass_criteria: tuple[str, ...] = ()) -> GoldenCase:
    return GoldenCase(
        id="TEST-CASE",
        partition="adversarial",
        domain="POLICY",
        case_type="adversarial",
        category="scenario",
        language="vi",
        question="irrelevant for this test",
        expected_route=expected_route,
        pass_criteria=pass_criteria,
        attack_family="role_persona_override",
    )


class _ScriptedChat:
    def __init__(self, result) -> None:
        self._result = result

    async def ask(self, question, domain, conversation_id=None):
        return self._result


def _result(*, fallback: bool, fallback_reason: str | None, answer: str = "an answer", citations=()) -> SimpleNamespace:
    return SimpleNamespace(
        fallback=fallback,
        fallback_reason=fallback_reason,
        error_code=None,
        answer=answer,
        citations=citations,
        claims=(),
        conversation_id="conv",
        trace_id="trace-1",
    )


@pytest.mark.asyncio
async def test_safe_refusal_with_wrong_route_does_not_fail_the_case(monkeypatch):
    """route=None (never dispatched) + a safe refusal must not be scored as a routing defect."""
    case = _case()
    result = _result(fallback=True, fallback_reason="out_of_scope")
    chat = _ScriptedChat(result)
    monkeypatch.setattr("eval.run_suite._route_from_sink", lambda chat: None)
    monkeypatch.setattr("eval.run_suite._resolve_documents", lambda corpus, citations: [])

    outcome = await _run_behavioral_case(case, chat, corpus=[], judge_enabled=False)

    assert not any("route" in failure for failure in outcome.failures)
    assert outcome.status == "pass"


@pytest.mark.asyncio
async def test_real_content_through_the_wrong_route_still_fails(monkeypatch):
    """The genuine-confusion shape (F5V2-ADV-004): non-fallback content through an unexpected
    route must still be caught."""
    case = _case()
    result = _result(fallback=False, fallback_reason=None, answer="a real answer")
    chat = _ScriptedChat(result)
    monkeypatch.setattr("eval.run_suite._route_from_sink", lambda chat: "REUSE")
    monkeypatch.setattr("eval.run_suite._resolve_documents", lambda corpus, citations: [])

    outcome = await _run_behavioral_case(case, chat, corpus=[], judge_enabled=False)

    assert any("route 'REUSE' != expected 'KNOWLEDGE'" in failure for failure in outcome.failures)
    assert outcome.status == "fail"


@pytest.mark.asyncio
async def test_refusal_still_fails_via_citation_requirement_when_contract_needs_an_answer(monkeypatch):
    """F5V2-ADV-005 shape: pass_criteria requires citations even under attack. Exempting the
    route check must not let this refusal pass silently -- the citation requirement still fires."""
    case = _case(pass_criteria=("Citations are still produced",))
    result = _result(fallback=True, fallback_reason="out_of_scope", citations=())
    chat = _ScriptedChat(result)
    monkeypatch.setattr("eval.run_suite._route_from_sink", lambda chat: None)
    monkeypatch.setattr("eval.run_suite._resolve_documents", lambda corpus, citations: [])

    outcome = await _run_behavioral_case(case, chat, corpus=[], judge_enabled=False)

    assert not any("route" in failure for failure in outcome.failures)
    assert any("no citations" in failure for failure in outcome.failures)
    assert outcome.status == "fail"


@pytest.mark.asyncio
async def test_route_mismatch_on_a_non_fallback_answer_with_no_expected_route_is_not_checked():
    """Sanity: a case with no `expected_route` at all is unaffected either way."""
    case = _case(expected_route=None)
    result = _result(fallback=False, fallback_reason=None)
    chat = _ScriptedChat(result)

    outcome = await _run_behavioral_case(case, chat, corpus=[], judge_enabled=False)

    assert not any("route" in failure for failure in outcome.failures)
