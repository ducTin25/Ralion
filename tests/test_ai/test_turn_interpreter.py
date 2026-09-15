"""Unit tests for `TurnInterpreter` (F5_SEMANTIC_TURN_INTERPRETER_REVIEW.md rev. 2, §4/§5/§8).

No live LLM here -- a scripted `ChatCompletionPort` fake drives the parser/dispatcher contract
directly, same shape as `tests/test_ai/test_scope_gate.py`/`test_evidence_sufficiency_gate.py`.
Live-precision (does the real model route/resolve correctly) is Suite B's job (rev. 2 §10),
gated behind `--live` -- not exercised here.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.ai.orchestration.conversation_memory import TopicState
from src.ai.orchestration.social_reply import SocialIntent
from src.core.telemetry import TraceRecorder, bind_trace
from src.ai.orchestration.turn_interpreter import (
    _SYSTEM_INSTRUCTIONS,
    ConversationControlApplication,
    InterpreterContext,
    InterpreterRoute,
    InterpreterScope,
    KnowledgePolicy,
    PriorTurn,
    TurnInterpreter,
    TurnInterpreterConfig,
)
from src.model.enums import DocumentDomain
from src.shared.ai.external_failures import ExternalFailureCode, ExternalServiceFailure
from src.shared.ai.request_budget import RequestBudget


class _ScriptedProvider:
    def __init__(self, content: str | None = None, *, raises: Exception | None = None) -> None:
        self.content = content
        self.raises = raises
        self.calls: list[list[tuple[str, str]]] = []

    async def complete(self, messages, _budget, _operation):
        self.calls.append(list(messages))
        if self.raises is not None:
            raise self.raises
        return SimpleNamespace(content=self.content)


def _budget() -> RequestBudget:
    return RequestBudget(10.0, 5.0, 5.0)


def _context(**overrides) -> InterpreterContext:
    defaults = dict(
        knowledge_domain=DocumentDomain.POLICY,
        current_utterance="còn VPN thì sao?",
        project_name=None,
        previous_turn=PriorTurn(
            question="Chính sách thiết bị công ty là gì?",
            grounded=True,
            answer_summary="Nhân viên được cấp laptop công ty.",
        ),
        turn_before_that=None,
        evidence_titles=("Device Policy",),
    )
    defaults.update(overrides)
    return InterpreterContext(**defaults)


@pytest.mark.asyncio
async def test_valid_response_parses_all_four_fields() -> None:
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "KNOWLEDGE", '
        '"resolved_question": "Chính sách VPN của công ty", '
        '"presentation": {"language": null, "detail": null}}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig())

    verdict = await interpreter.interpret(_context(), _budget())

    assert verdict.scope is InterpreterScope.IN_SCOPE
    assert verdict.route is InterpreterRoute.KNOWLEDGE
    assert verdict.resolved_question == "Chính sách VPN của công ty"
    assert verdict.presentation.language is None
    assert verdict.presentation.detail is None
    assert verdict.malformed is False
    assert verdict.errored is False


@pytest.mark.asyncio
async def test_presentation_fields_extracted() -> None:
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "REUSE", '
        '"resolved_question": "Quy định thiết bị công ty", '
        '"presentation": {"language": "vi", "detail": "detailed"}}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig())

    verdict = await interpreter.interpret(_context(current_utterance="trả lời bằng tiếng việt thật chi tiết"), _budget())

    assert verdict.route is InterpreterRoute.REUSE
    assert verdict.presentation.language == "vi"
    assert verdict.presentation.detail == "detailed"


@pytest.mark.asyncio
async def test_markdown_fenced_json_is_accepted() -> None:
    provider = _ScriptedProvider(
        '```json\n{"scope": "IN_SCOPE", "route": "CATALOG", "resolved_question": "tài liệu gì", '
        '"presentation": {"language": null, "detail": null}}\n```'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig())

    verdict = await interpreter.interpret(_context(), _budget())

    assert verdict.route is InterpreterRoute.CATALOG


@pytest.mark.asyncio
async def test_malformed_json_falls_back_to_knowledge_with_raw_utterance() -> None:
    """Rev. 2 §8: malformed/unparseable output -> route=KNOWLEDGE, resolved_question=<raw
    utterance>, presentation all-null, `malformed=True` annotated for the caller."""
    provider = _ScriptedProvider("not json at all")
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig())

    verdict = await interpreter.interpret(_context(current_utterance="còn VPN thì sao?"), _budget())

    assert verdict.malformed is True
    assert verdict.route is InterpreterRoute.KNOWLEDGE
    assert verdict.resolved_question == "còn VPN thì sao?"
    assert verdict.presentation.language is None
    assert verdict.presentation.detail is None


@pytest.mark.asyncio
async def test_unrecognized_scope_value_is_treated_as_malformed() -> None:
    """§8 "Unknown enum value" row: an unrecognized `scope` has no safe default -- unlike route/
    presentation, it takes the malformed row, even though route/resolved_question look fine."""
    provider = _ScriptedProvider(
        '{"scope": "MAYBE", "route": "KNOWLEDGE", "resolved_question": "VPN policy", '
        '"presentation": {"language": null, "detail": null}}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig())

    verdict = await interpreter.interpret(_context(current_utterance="what about VPN?"), _budget())

    assert verdict.malformed is True
    assert verdict.resolved_question == "what about VPN?"


@pytest.mark.asyncio
async def test_unknown_route_value_defaults_to_knowledge_not_malformed() -> None:
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "SOMETHING_NEW", "resolved_question": "VPN policy", '
        '"presentation": {"language": null, "detail": null}}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig())

    verdict = await interpreter.interpret(_context(), _budget())

    assert verdict.malformed is False
    assert verdict.route is InterpreterRoute.KNOWLEDGE


@pytest.mark.asyncio
async def test_empty_resolved_question_falls_back_to_raw_utterance_and_demotes_route() -> None:
    """§8: an unusable `resolved_question` (empty here) falls back to the raw utterance, and the
    caller must demote a REUSE turn to KNOWLEDGE -- it cannot be ESG-judged with no subject."""
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "REUSE", "resolved_question": "", '
        '"presentation": {"language": null, "detail": null}}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig())

    verdict = await interpreter.interpret(_context(current_utterance="giải thích kỹ hơn"), _budget())

    assert verdict.sanitized is True
    assert verdict.route is InterpreterRoute.KNOWLEDGE
    assert verdict.resolved_question == "giải thích kỹ hơn"


@pytest.mark.asyncio
async def test_overlong_resolved_question_falls_back_and_demotes_route() -> None:
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "REUSE", "resolved_question": "' + ("a" * 250) + '", '
        '"presentation": {"language": null, "detail": null}}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig())

    verdict = await interpreter.interpret(_context(current_utterance="giải thích kỹ hơn"), _budget())

    assert verdict.sanitized is True
    assert verdict.route is InterpreterRoute.KNOWLEDGE


@pytest.mark.asyncio
async def test_reuse_route_echoing_current_utterance_is_demoted_to_knowledge() -> None:
    """2026-08-22 live Suite B finding / §4.4 defense-in-depth guard: a REUSE verdict whose
    resolved_question is just the current utterance echoed back verbatim (the rev. 1 bug) must be
    demoted to KNOWLEDGE, exactly like an empty/overlong resolved_question already is."""
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "REUSE", "resolved_question": "tóm tắt riêng phần cuối", '
        '"presentation": {"language": null, "detail": null}}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig())

    verdict = await interpreter.interpret(_context(current_utterance="tóm tắt riêng phần cuối"), _budget())

    assert verdict.route is InterpreterRoute.KNOWLEDGE
    assert verdict.sanitized is True


@pytest.mark.asyncio
async def test_reuse_route_with_real_subject_is_not_demoted() -> None:
    """Control for the guard above: a REUSE verdict with a genuinely rewritten subject must NOT
    be touched by the echo guard."""
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "REUSE", '
        '"resolved_question": "Quy định remote wipe với thiết bị công ty", '
        '"presentation": {"language": null, "detail": null}}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig())

    verdict = await interpreter.interpret(
        _context(current_utterance="giải thích kỹ hơn phần remote wipe"), _budget()
    )

    assert verdict.route is InterpreterRoute.REUSE
    assert verdict.sanitized is False
    assert verdict.resolved_question == "Quy định remote wipe với thiết bị công ty"


@pytest.mark.asyncio
async def test_knowledge_route_mirroring_utterance_is_not_demoted() -> None:
    """The echo guard is scoped to route=REUSE only: a standalone KNOWLEDGE question whose
    resolved_question naturally mirrors the current utterance is expected, correct behavior."""
    question = "Coding style guide của Thanos nói gì về defer Close()?"
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "KNOWLEDGE", "resolved_question": "'
        + question
        + '", "presentation": {"language": null, "detail": null}}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig())

    verdict = await interpreter.interpret(_context(current_utterance=question, previous_turn=None), _budget())

    assert verdict.route is InterpreterRoute.KNOWLEDGE
    assert verdict.sanitized is False
    assert verdict.resolved_question == question


@pytest.mark.asyncio
async def test_clarify_route_demoted_to_knowledge_when_disabled_by_default() -> None:
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "CLARIFY", "resolved_question": "cái đó là gì", '
        '"presentation": {"language": null, "detail": null}}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig(clarify_enabled=False))

    verdict = await interpreter.interpret(_context(), _budget())

    assert verdict.route is InterpreterRoute.KNOWLEDGE


@pytest.mark.asyncio
async def test_clarify_route_kept_when_explicitly_enabled() -> None:
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "CLARIFY", "resolved_question": "cái đó là gì", '
        '"presentation": {"language": null, "detail": null}}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig(clarify_enabled=True))

    verdict = await interpreter.interpret(_context(), _budget())

    assert verdict.route is InterpreterRoute.CLARIFY


@pytest.mark.asyncio
async def test_provider_timeout_returns_marked_degraded_verdict() -> None:
    """Rev. 2 §8 timeout row is diagnostic and never raises; ChatService stops it before dispatch."""
    failure = ExternalServiceFailure(
        service="llm", code=ExternalFailureCode.TIMEOUT, retryable=True, attempts=1, timeout_scope="stage"
    )
    provider = _ScriptedProvider(raises=failure)
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig())

    verdict = await interpreter.interpret(_context(current_utterance="còn VPN thì sao?"), _budget())

    assert verdict.errored is True
    assert verdict.scope is InterpreterScope.IN_SCOPE
    assert verdict.route is InterpreterRoute.KNOWLEDGE
    assert verdict.resolved_question == "còn VPN thì sao?"


@pytest.mark.asyncio
async def test_never_raises_on_unexpected_provider_exception() -> None:
    provider = _ScriptedProvider(raises=RuntimeError("boom"))
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig())

    verdict = await interpreter.interpret(_context(), _budget())

    assert verdict.errored is True


@pytest.mark.asyncio
async def test_prior_turns_are_wrapped_as_untrusted_user_role_and_answers_unwrapped_assistant_role() -> None:
    """Rev. 2 §5.1: a past USER turn is untrusted, wrapped, delivered in the `user` role; the
    server-authored answer summary is delivered unwrapped in the `assistant` role."""
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "KNOWLEDGE", "resolved_question": "VPN policy", '
        '"presentation": {"language": null, "detail": null}}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig())

    await interpreter.interpret(_context(), _budget())

    messages = provider.calls[0]
    roles = [role for role, _ in messages]
    assert "user" in roles and "assistant" in roles
    user_messages = [content for role, content in messages if role == "user"]
    assistant_messages = [content for role, content in messages if role == "assistant"]
    assert any("Chính sách thiết bị công ty là gì?" in content for content in user_messages)
    assert any("UNTRUSTED PAST USER TURN" in content for content in user_messages)
    assert any("Nhân viên được cấp laptop công ty." == content for content in assistant_messages)


@pytest.mark.asyncio
async def test_evidence_titles_are_wrapped_as_untrusted() -> None:
    """Rev. 2 §5.1: evidence titles are content-derived from ingested documents -- untrusted,
    not in the `project_name` trusted class -- so they must be wrapped, unlike `project_name`."""
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "KNOWLEDGE", "resolved_question": "VPN policy", '
        '"presentation": {"language": null, "detail": null}}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig())

    await interpreter.interpret(_context(project_name="Thanos"), _budget())

    messages = provider.calls[0]
    final_user_message = [content for role, content in messages if role == "user"][-1]
    assert "UNTRUSTED REFERENCE DATA" in final_user_message
    assert "Device Policy" in final_user_message
    trusted_system_message = messages[1][1]
    assert "Thanos" in trusted_system_message
    assert "UNTRUSTED" not in trusted_system_message


@pytest.mark.asyncio
async def test_turn_one_has_no_prior_turn_in_context() -> None:
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "KNOWLEDGE", "resolved_question": "device policy", '
        '"presentation": {"language": null, "detail": null}}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig())
    context = InterpreterContext(
        knowledge_domain=DocumentDomain.POLICY,
        current_utterance="device policy?",
        project_name=None,
        previous_turn=None,
        turn_before_that=None,
        evidence_titles=(),
    )

    verdict = await interpreter.interpret(context, _budget())

    assert verdict.route is InterpreterRoute.KNOWLEDGE
    messages = provider.calls[0]
    assert "n/a" in messages[1][1]


# ------------------------------------------------------------------------------------------
# F5 audit 2026-08-30, root cause #3: `topic_state` must survive `interpret()`'s own redaction
# step. A test that calls `_messages()` directly cannot catch a regression here -- it has to go
# through `interpret()`, the only code path a real call ever takes, exactly like the live bug did.
# ------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_topic_state_survives_interpret_and_reaches_the_rendered_prompt() -> None:
    """Confirmed root cause: `interpret()` rebuilt `redacted_context` without forwarding
    `topic_state`, so `active_topic_state.subject`/`.entities` always rendered "unset" in the
    prompt actually sent to the model -- the v13 third-anchor mechanism was dead code in
    production even though `_interpreter_context` (chat_service.py) correctly populated it.
    Live symptom this closes: "chúng tương tác với nhau như thế nào?" after a multi-component
    list lost the full component set and resolved against whichever entity survived
    `previous_turn.answer_summary`'s truncation."""
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "KNOWLEDGE", "resolved_question": "component interactions", '
        '"presentation": {"language": null, "detail": null}}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig())
    context = _context(
        topic_state=TopicState(
            subject="Các thành phần chính của dự án Thanos",
            entities=("Sidecar", "Store Gateway", "Compactor", "Receiver", "Ruler", "Query Gateway"),
        )
    )

    await interpreter.interpret(context, _budget())

    system_message = provider.calls[0][1][1]
    assert "active_topic_state.subject: Các thành phần chính của dự án Thanos" in system_message
    assert "Sidecar, Store Gateway, Compactor, Receiver, Ruler, Query Gateway" in system_message


# ------------------------------------------------------------------------------------------
# TI-* cases: F5_BOUNDED_GENERAL_KNOWLEDGE_SPEC.md §5.1/§15.1.
# ------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ti01_knowledge_policy_disabled_by_default_stays_strict_internal() -> None:
    """§5.6 shipping default: `knowledge_policy_enabled=False` -- even a well-formed
    GENERAL_ALLOWED payload from the model is coerced to STRICT_INTERNAL before any caller sees
    it, with no `knowledge_policy_degraded` annotation (this is the intentional master switch,
    not a parse failure)."""
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "KNOWLEDGE", "resolved_question": "cai virtualenv la gi", '
        '"presentation": {"language": null, "detail": null}, "knowledge_policy": "GENERAL_ALLOWED"}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig(knowledge_policy_enabled=False))

    verdict = await interpreter.interpret(_context(), _budget())

    assert verdict.knowledge_policy is KnowledgePolicy.STRICT_INTERNAL
    assert verdict.knowledge_policy_degraded is False


@pytest.mark.asyncio
async def test_ti02_knowledge_policy_enabled_parses_general_allowed() -> None:
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "KNOWLEDGE", "resolved_question": "cai virtualenv la gi", '
        '"presentation": {"language": null, "detail": null}, "knowledge_policy": "GENERAL_ALLOWED"}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig(knowledge_policy_enabled=True))

    verdict = await interpreter.interpret(_context(), _budget())

    assert verdict.knowledge_policy is KnowledgePolicy.GENERAL_ALLOWED
    assert verdict.knowledge_policy_degraded is False


@pytest.mark.asyncio
async def test_ti03_knowledge_policy_field_absent_defaults_strict_internal_and_degraded() -> None:
    """§5.1: missing field -> STRICT_INTERNAL, `knowledge_policy_degraded=True`. NOT a
    `malformed` verdict -- scope/route/resolved_question still parse normally."""
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "KNOWLEDGE", "resolved_question": "cai virtualenv la gi", '
        '"presentation": {"language": null, "detail": null}}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig(knowledge_policy_enabled=True))

    verdict = await interpreter.interpret(_context(), _budget())

    assert verdict.knowledge_policy is KnowledgePolicy.STRICT_INTERNAL
    assert verdict.knowledge_policy_degraded is True
    assert verdict.malformed is False


@pytest.mark.asyncio
async def test_ti04_knowledge_policy_unrecognized_value_defaults_and_degraded() -> None:
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "KNOWLEDGE", "resolved_question": "cai virtualenv la gi", '
        '"presentation": {"language": null, "detail": null}, "knowledge_policy": "MAYBE"}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig(knowledge_policy_enabled=True))

    verdict = await interpreter.interpret(_context(), _budget())

    assert verdict.knowledge_policy is KnowledgePolicy.STRICT_INTERNAL
    assert verdict.knowledge_policy_degraded is True


@pytest.mark.asyncio
async def test_ti05_malformed_verdict_forces_strict_internal() -> None:
    provider = _ScriptedProvider("not json at all")
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig(knowledge_policy_enabled=True))

    verdict = await interpreter.interpret(_context(), _budget())

    assert verdict.malformed is True
    assert verdict.knowledge_policy is KnowledgePolicy.STRICT_INTERNAL
    assert verdict.knowledge_policy_degraded is False


@pytest.mark.asyncio
async def test_ti06_errored_verdict_forces_strict_internal() -> None:
    failure = ExternalServiceFailure(
        service="llm", code=ExternalFailureCode.TIMEOUT, retryable=True, attempts=1, timeout_scope="stage"
    )
    provider = _ScriptedProvider(raises=failure)
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig(knowledge_policy_enabled=True))

    verdict = await interpreter.interpret(_context(), _budget())

    assert verdict.errored is True
    assert verdict.knowledge_policy is KnowledgePolicy.STRICT_INTERNAL


@pytest.mark.asyncio
async def test_ti07_sanitized_verdict_forces_strict_internal() -> None:
    """§5.1: a sanitized (unusable resolved_question) verdict forces STRICT_INTERNAL
    unconditionally, and is NOT counted as `knowledge_policy_degraded` (a distinct condition)."""
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "REUSE", "resolved_question": "", '
        '"presentation": {"language": null, "detail": null}, "knowledge_policy": "GENERAL_ALLOWED"}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig(knowledge_policy_enabled=True))

    verdict = await interpreter.interpret(_context(current_utterance="giải thích kỹ hơn"), _budget())

    assert verdict.sanitized is True
    assert verdict.knowledge_policy is KnowledgePolicy.STRICT_INTERNAL
    assert verdict.knowledge_policy_degraded is False


@pytest.mark.asyncio
async def test_ti08_prompt_version_matches_the_current_prompt() -> None:
    """Deliberately an EXACT pin, not a "not the old value" check: this constant is logged on
    every interpreter call, so an eval run either side of a prompt edit is only comparable if the
    version moved. Failing here means the prompt changed -- bump the constant and update this
    literal in the same commit, never the other way round.

    v2 -> v3 (2026-08-25): `=== social_intent ===` gained BUDDY_SUPPORT and its two exclusions.
    v3 -> v4 (2026-08-25): BUDDY_SUPPORT extended to the question form; `presentation.language`
    told explicitly that the message's own language is not a switch request.
    v4 -> v5 (2026-08-25, audit B-04/B-05/B-06): CONVERSATION owns history-verification
    questions; a user assertion resolves to the corresponding question; `resolved_question`
    preserves the current turn's intent instead of collapsing to the previous turn's subject.
    v5 -> v6 (2026-08-25): no edit here -- `_SCOPE_SUBSTANCE` is imported from
    `scope_gate._SCOPE_SYSTEM`, which moved to v3 after the live false-reject finding, so this
    prompt's bytes changed with it. A shared prompt fragment means a shared version bump.
    v6 -> v7 (2026-08-25): the intent rule gained its mirror half -- a specific question
    (bao nhiêu / nào / khi nào) must not be softened into an existence question. Measured on the
    90-case RAG run, not guessed.
    v7 -> v8 (2026-08-25): the contract gained a sixth field, `affect`, orthogonal to `route`;
    BUDDY_SUPPORT was restated as a semantic condition instead of a phrase description; and
    `_SCOPE_SUBSTANCE` moved with `scope_gate` v4.
    v8 -> v9 (2026-08-26): no edit here -- `scope_gate` moved to v5 (ordinary conversational turns
    are IN_SCOPE), and this prompt imports its substance.
    v10 -> v11 (2026-08-27): `previous_turn.outcome`/`turn_before_that.outcome` let a question
    about a PRIOR REPLY's own
    behaviour is answerable at all; (2) the CONVERSATION section defines that class of turn ("sao
    lại không có nguồn?", "why did you say that?") with a worked example keyed on that outcome;
    (3) `knowledge_policy` was rewritten from verb-specific carve-outs into a sub-need split --
    GENERAL_ALLOWED when at least one part is company-independent, STRICT_INTERNAL only when every
    part is company-specific -- plus the explicit statement that the field is a permission for a
    separately-marked general section, never permission to answer a company-specific part from
    general knowledge.
    v11 -> v12 (2026-08-28): a language/detail request that asks to re-answer the previous
    grounded response routes through REUSE while persisting its presentation preference.
    v12 -> v13 (2026-08-29, F5 audit root causes A/B/C): `active_topic_state` trusted lines give
    the interpreter a third, always-current anchor beyond `previous_turn`/`turn_before_that`;
    the REUSE rule gained its converse (a request to cover MORE than the previous answer named is
    KNOWLEDGE, not REUSE); `resolved_question` states its resolution precedence explicitly.
    v13 -> v14 (2026-08-29, F5 audit failure 1): `conversation_control` gained an explicit
    `application` field (FUTURE_TURNS/PREVIOUS_RESPONSE/BOTH) so the dispatcher no longer has to
    infer which turn(s) a presentation control governs from `route`/`sanitized`.
    v14 -> v15 (2026-08-29, F5 audit remediation): `application`'s 3-way label is replaced by two
    independent `apply_now`/`persist_future` booleans, derived in code; `has_answerable_subject`
    is added as its own field so the dispatcher can compose affect with route deterministically.
    v15 -> v16 (2026-08-29, F5 audit remediation): `knowledge_policy` gained an explicit
    name-collision rule -- an explicit genericity marker ('nói chung'/'in general') selects the
    generic reading of a term even when that same term also names one of this project's own
    components, overriding conversation-history bias toward the project-specific entity.
    v16 -> v17 (2026-08-29, F5 audit remediation, confirmed via live trace): the REUSE route rule
    gained a third decision signal -- naming a DIFFERENT specific entity than the previous
    answer's subject is a new subject (KNOWLEDGE), regardless of message length or how many REUSE
    turns immediately preceded it.
    v17 -> v18 (2026-08-30, F5 audit remediation #4a): `knowledge_policy`'s name-collision rule no
    longer requires an explicit genericity marker ('nói chung'/'in general') -- restated as a
    semantic question-form test (is this asking about the pattern/concept itself, or about this
    project's own instance/location/configuration of it), so "Sidecar in software architecture?"/
    "Explain the Sidecar design pattern"/"Sidecar pros/cons" resolve to GENERAL_ALLOWED without an
    explicit marker, while "Where is Thanos Sidecar implemented?" stays STRICT_INTERNAL.
    v18 -> v19 (2026-08-30, F5 audit remediation #4b): no edit to this module's own text --
    `_SCOPE_SUBSTANCE` is derived from `scope_gate._SCOPE_SYSTEM`, which moved to v8 (a standalone
    technology comparison/definition needing no company-specific evidence is IN_SCOPE, aligning
    the scope boundary with `KnowledgePolicy.GENERAL_ALLOWED` instead of contradicting it), so this
    prompt's bytes changed with it.
    v19 -> v20 (2026-08-30, F5 audit remediation #5, live-trace-confirmed regression): the REUSE
    route's "short examples for calibration" list gained a third worked example for the pure
    standing-preference shape (apply_now=false, persist_future=true) -- v15's rewrite of the old
    labelled `application` field into the apply_now/persist_future question pair had dropped this
    exact case from that list, leaving both remaining examples there apply_now=true. No code
    change -- restores a calibration anchor the semantic contract always intended to have.
    v20 -> v21 (2026-08-30, same remediation #5, after a live 5-repeat rerun of v20 still showed
    apply_now=true in 4/5 runs): the REUSE bullet's own opening definition -- read before the
    apply_now/persist_future test 40 lines later -- listed "switching language ('answer in
    Vietnamese', ...)" as a REUSE example with no "right now" qualifier, and that unqualified
    anchor was outweighing the later rule on most samples. Fix qualifies the opening definition
    itself ("re-present ... RIGHT NOW") and names the 'từ giờ' exception at first mention. No code
    change.
    v21 -> v22 (2026-08-30, same remediation #5, after a live 5-repeat rerun of v21 measured 0/5):
    moved the apply_now test to the earliest possible position in the whole prompt -- a one-
    paragraph "single most common mistake" preview immediately after the JSON schema, before even
    `=== TRUST BOUNDARY ===`. No code change.
    v22 -> v23 (2026-08-30, remediation #5, Thread A): a third 5-repeat live rerun of v22 measured
    1/10, no better than v20/v21 (2/20 combined). Historical trace comparison showed v14 (before
    `apply_now`/`persist_future` existed at all) was 3/3 correct on this exact live turn using a
    DIFFERENT mechanism -- a labelled 3-way `application` field with a named case for this shape --
    not merely different wording of the same boolean mechanism v15-v22 all shared. Reverts v20/
    v21/v22's three rewrites (measured no value) and restores v14's labelled-case (A)/(B)/(C)
    TEACHING structure at the REUSE decision point, while keeping the `apply_now`/`persist_future`
    OUTPUT contract unchanged -- each case now states which two booleans it maps to, so `_parse`
    and the dispatcher need no changes. Also adds the English worked example for case (C) that was
    the actual bug v15's rewrite was meant to fix ("from now on answer in English and repeat that
    answer" losing "repeat") -- v15 conflated a missing example with a mechanism problem.
    """
    from src.ai.orchestration.turn_interpreter import TURN_INTERPRETER_PROMPT_VERSION

    assert TURN_INTERPRETER_PROMPT_VERSION == "turn-interpreter-v23"


def test_reuse_language_request_states_three_labelled_cases_with_apply_now_mapping() -> None:
    """F5 audit 2026-08-30 remediation #5, Thread A: pins the restored v14-style labelled
    (A)/(B)/(C) teaching at the REUSE decision point -- the mechanism historical trace comparison
    showed was 3/3 reliable live, versus v15-v22's boolean-only mechanism which never exceeded
    ~15-20% across four prompt variants. Each label states its apply_now/persist_future mapping
    directly, so the JSON output contract (and `_parse`) are unchanged."""
    assert "(A) re-answer ONLY" in _SYSTEM_INSTRUCTIONS
    assert "route=REUSE, apply_now=true, " in _SYSTEM_INSTRUCTIONS
    assert "(B) standing preference ONLY" in _SYSTEM_INSTRUCTIONS
    assert "từ giờ hãy trả lời bằng tiếng Việt nhé" in _SYSTEM_INSTRUCTIONS
    assert "this is SOCIAL, NEVER REUSE" in _SYSTEM_INSTRUCTIONS
    assert "(C) both" in _SYSTEM_INSTRUCTIONS
    assert "route=REUSE, apply_now=true, persist_future=true" in _SYSTEM_INSTRUCTIONS


def test_reuse_case_c_has_an_english_worked_example() -> None:
    """The actual bug that justified v15's rewrite: case (C)'s English phrasing ("from now on
    answer in English and repeat that answer") had no worked example, only a Vietnamese one, so a
    model asked to match a labelled case in English had nothing to match. Restoring the labelled
    mechanism without also fixing this would reopen that original bug -- pin that it's covered
    directly, in English, this time."""
    assert "from now on answer in English and repeat that answer" in _SYSTEM_INSTRUCTIONS
    assert "must not be dropped just because the sentence also states a" in _SYSTEM_INSTRUCTIONS


def test_reuse_bullet_no_longer_carries_the_reverted_experiments() -> None:
    """Pins that v20/v21/v22's three rewrites (a trailing calibration example, a qualified opening
    REUSE-bullet definition, and a top-of-prompt preview paragraph) were actually removed, not left
    alongside the v23 restoration -- all three measured no live value (2/20 combined) and would
    only add prompt length/noise if kept."""
    assert "THE SINGLE MOST COMMON MISTAKE" not in _SYSTEM_INSTRUCTIONS
    assert "TWO INDEPENDENT YES/NO QUESTIONS" not in _SYSTEM_INSTRUCTIONS
    assert "Three short examples for calibration only" not in _SYSTEM_INSTRUCTIONS


@pytest.mark.asyncio
async def test_pure_standing_preference_after_grounded_answer_parses_apply_now_false() -> None:
    """Deterministic companion to the prompt-text pin above: even with the calibration example
    restored, `_parse` must still treat `apply_now=false, persist_future=true` from the model as
    SOCIAL, never REUSE -- this was already correct in `_parse`/the dispatcher (confirmed by live
    trace: the dispatcher derives `wants_previous_reanswer`/`route` correctly from whatever
    booleans it is given), so this only re-pins that a healthy payload of this exact shape stays
    correct after the prompt-only change above."""
    provider = _ScriptedProvider(
        '{"scope":"IN_SCOPE","route":"SOCIAL","resolved_question":"Yêu cầu trả lời bằng tiếng Việt",'
        '"presentation":{"language":"vi","detail":null},'
        '"conversation_control":{"kind":"UPDATE_PRESENTATION","presentation":'
        '{"language":"vi","detail":null},"apply_now":false,"persist_future":true},'
        '"social_intent":"LANGUAGE_PREFERENCE"}'
    )
    verdict = await TurnInterpreter(provider, TurnInterpreterConfig()).interpret(
        _context(current_utterance="từ giờ hãy trả lời bằng tiếng Việt nhé"), _budget()
    )

    assert verdict.route is InterpreterRoute.SOCIAL
    assert verdict.apply_now is False
    assert verdict.persist_future is True
    assert verdict.conversation_control.application == ConversationControlApplication.FUTURE_TURNS


@pytest.mark.asyncio
async def test_explicit_conversation_control_parses_separately_from_turn_presentation() -> None:
    provider = _ScriptedProvider(
        '{"scope":"IN_SCOPE","route":"SOCIAL","resolved_question":"reply preference",'
        '"presentation":{"language":"vi","detail":null},'
        '"conversation_control":{"kind":"UPDATE_PRESENTATION","presentation":'
        '{"language":"vi","detail":null}},"social_intent":"LANGUAGE_PREFERENCE"}'
    )
    verdict = await TurnInterpreter(provider, TurnInterpreterConfig()).interpret(
        _context(current_utterance="from now on use Vietnamese"), _budget()
    )

    assert verdict.conversation_control.updates_presentation is True
    assert verdict.conversation_control.presentation.language == "vi"


@pytest.mark.asyncio
async def test_bare_control_label_without_a_valid_patch_fails_closed() -> None:
    provider = _ScriptedProvider(
        '{"scope":"IN_SCOPE","route":"SOCIAL","resolved_question":"hello",'
        '"presentation":{"language":"en","detail":null},'
        '"conversation_control":{"kind":"UPDATE_PRESENTATION","presentation":'
        '{"language":null,"detail":null}},"social_intent":"GREETING"}'
    )
    verdict = await TurnInterpreter(provider, TurnInterpreterConfig()).interpret(
        _context(current_utterance="hello"), _budget()
    )

    assert verdict.conversation_control.updates_presentation is False


# ------------------------------------------------------------------------------------------
# `conversation_control.application` (v14, F5 audit failure 1) -- FUTURE_TURNS/PREVIOUS_RESPONSE/
# BOTH, populated by the model, never inferred downstream from `route`/wording.
# ------------------------------------------------------------------------------------------


# ------------------------------------------------------------------------------------------
# `conversation_control.application` (v14, F5 audit failure 1) -- FUTURE_TURNS/PREVIOUS_RESPONSE/
# BOTH, populated by the model, never inferred downstream from `route`/wording.
# ------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_control_application_future_turns_parses() -> None:
    provider = _ScriptedProvider(
        '{"scope":"IN_SCOPE","route":"SOCIAL","resolved_question":"reply preference",'
        '"presentation":{"language":"vi","detail":null},'
        '"conversation_control":{"kind":"UPDATE_PRESENTATION","presentation":'
        '{"language":"vi","detail":null},"application":"FUTURE_TURNS"},'
        '"social_intent":"LANGUAGE_PREFERENCE"}'
    )
    verdict = await TurnInterpreter(provider, TurnInterpreterConfig()).interpret(
        _context(current_utterance="từ giờ hãy trả lời bằng tiếng Việt"), _budget()
    )

    assert verdict.conversation_control.application == ConversationControlApplication.FUTURE_TURNS


@pytest.mark.asyncio
async def test_control_application_previous_response_parses() -> None:
    provider = _ScriptedProvider(
        '{"scope":"IN_SCOPE","route":"REUSE","resolved_question":"how to set up locally",'
        '"presentation":{"language":"vi","detail":null},'
        '"conversation_control":{"kind":"UPDATE_PRESENTATION","presentation":'
        '{"language":"vi","detail":null},"application":"PREVIOUS_RESPONSE"}}'
    )
    verdict = await TurnInterpreter(provider, TurnInterpreterConfig()).interpret(
        _context(current_utterance="trả lời bằng tiếng Việt đi"), _budget()
    )

    assert (
        verdict.conversation_control.application
        == ConversationControlApplication.PREVIOUS_RESPONSE
    )


@pytest.mark.asyncio
async def test_control_application_both_parses() -> None:
    provider = _ScriptedProvider(
        '{"scope":"IN_SCOPE","route":"REUSE","resolved_question":"how to set up locally",'
        '"presentation":{"language":"en","detail":null},'
        '"conversation_control":{"kind":"UPDATE_PRESENTATION","presentation":'
        '{"language":"en","detail":null},"application":"BOTH"}}'
    )
    verdict = await TurnInterpreter(provider, TurnInterpreterConfig()).interpret(
        _context(current_utterance="answer that in English and keep using English afterwards"),
        _budget(),
    )

    assert verdict.conversation_control.application == ConversationControlApplication.BOTH


@pytest.mark.asyncio
async def test_control_application_missing_field_parses_as_none() -> None:
    """A pre-v14 payload/fixture: the dispatcher's route-based bridge handles this, not the
    parser -- the parser must not silently invent FUTURE_TURNS here, or the bridge could never
    tell "not specified" apart from "explicitly FUTURE_TURNS"."""
    provider = _ScriptedProvider(
        '{"scope":"IN_SCOPE","route":"SOCIAL","resolved_question":"reply preference",'
        '"presentation":{"language":"vi","detail":null},'
        '"conversation_control":{"kind":"UPDATE_PRESENTATION","presentation":'
        '{"language":"vi","detail":null}},"social_intent":"LANGUAGE_PREFERENCE"}'
    )
    verdict = await TurnInterpreter(provider, TurnInterpreterConfig()).interpret(
        _context(current_utterance="from now on use Vietnamese"), _budget()
    )

    assert verdict.conversation_control.application is None


@pytest.mark.asyncio
async def test_control_application_unrecognized_value_parses_as_none() -> None:
    provider = _ScriptedProvider(
        '{"scope":"IN_SCOPE","route":"SOCIAL","resolved_question":"reply preference",'
        '"presentation":{"language":"vi","detail":null},'
        '"conversation_control":{"kind":"UPDATE_PRESENTATION","presentation":'
        '{"language":"vi","detail":null},"application":"SOMETHING_ELSE"},'
        '"social_intent":"LANGUAGE_PREFERENCE"}'
    )
    verdict = await TurnInterpreter(provider, TurnInterpreterConfig()).interpret(
        _context(current_utterance="from now on use Vietnamese"), _budget()
    )

    assert verdict.conversation_control.application is None


# --------------------------------------------------------------------------------------------
# A2 remediation (F5 audit): `apply_now`/`persist_future` independent booleans, preferred over
# the legacy `application` label above. Parametrized over both languages and every phrasing shape
# the live-test failure covered, since the whole point of the fix is that correctness no longer
# depends on the model matching a labelled example -- these tests pin the DETERMINISTIC derivation
# in `_parse`, not the model's semantic judgment (unchanged -- see the module docstring).
# --------------------------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("apply_now", "persist_future", "expected"),
    [
        (True, False, ConversationControlApplication.PREVIOUS_RESPONSE),
        (False, True, ConversationControlApplication.FUTURE_TURNS),
        (True, True, ConversationControlApplication.BOTH),
        (False, False, None),
    ],
)
async def test_apply_now_persist_future_booleans_derive_application_deterministically(
    apply_now: bool, persist_future: bool, expected: ConversationControlApplication | None
) -> None:
    provider = _ScriptedProvider(
        '{"scope":"IN_SCOPE","route":"REUSE","resolved_question":"how to set up locally",'
        '"presentation":{"language":"en","detail":null},'
        '"conversation_control":{"kind":"UPDATE_PRESENTATION","presentation":'
        '{"language":"en","detail":null},'
        f'"apply_now":{str(apply_now).lower()},"persist_future":{str(persist_future).lower()}}}}}'
    )
    verdict = await TurnInterpreter(provider, TurnInterpreterConfig()).interpret(
        _context(current_utterance="regression fixture, wording irrelevant to this assertion"),
        _budget(),
    )

    assert verdict.conversation_control.application is expected


@pytest.mark.asyncio
async def test_interpret_annotates_apply_now_persist_future_control_application_and_topic_state() -> None:
    """F5 audit 2026-08-30 (observability remediation): `interpret()` must put the raw
    `apply_now`/`persist_future` the model sent, the `control_application` derived from them, and
    the `active_topic_state` this call was given onto the current trace -- the fields needed to
    reconstruct why a turn like "từ giờ hãy trả lời bằng tiếng Việt nhé" did or didn't re-render
    the previous answer, without re-deriving them from the raw completion payload."""
    provider = _ScriptedProvider(
        '{"scope":"IN_SCOPE","route":"SOCIAL","resolved_question":"Yêu cầu trả lời bằng tiếng Việt",'
        '"presentation":{"language":"vi","detail":null},'
        '"conversation_control":{"kind":"UPDATE_PRESENTATION","presentation":'
        '{"language":"vi","detail":null},"apply_now":false,"persist_future":true},'
        '"social_intent":"LANGUAGE_PREFERENCE"}'
    )
    trace = TraceRecorder("trace-apply-now-test")
    with bind_trace(trace):
        verdict = await TurnInterpreter(provider, TurnInterpreterConfig()).interpret(
            _context(
                current_utterance="từ giờ hãy trả lời bằng tiếng Việt nhé",
                topic_state=TopicState(subject="Kiến trúc Thanos", entities=("Sidecar",)),
            ),
            _budget(),
        )

    assert verdict.apply_now is False
    assert verdict.persist_future is True
    details = trace.snapshot().attributes["decision_details"]
    assert details["turn_interpreter_apply_now"] is False
    assert details["turn_interpreter_persist_future"] is True
    assert details["turn_interpreter_control_application"] == "FUTURE_TURNS"
    assert details["turn_interpreter_topic_state_subject"] == "Kiến trúc Thanos"
    assert details["turn_interpreter_topic_state_entities"] == ["Sidecar"]


@pytest.mark.asyncio
async def test_apply_now_boolean_is_preferred_over_a_stale_application_string() -> None:
    """If a payload somehow carries both (a transitional model, or a hand-written fixture), the
    new independent booleans -- the deterministic mechanism -- win over the legacy label."""
    provider = _ScriptedProvider(
        '{"scope":"IN_SCOPE","route":"REUSE","resolved_question":"q",'
        '"presentation":{"language":null,"detail":null},'
        '"conversation_control":{"kind":"UPDATE_PRESENTATION","presentation":'
        '{"language":"vi","detail":null},"application":"FUTURE_TURNS",'
        '"apply_now":true,"persist_future":true}}'
    )
    verdict = await TurnInterpreter(provider, TurnInterpreterConfig()).interpret(
        _context(current_utterance="q"), _budget()
    )

    assert verdict.conversation_control.application == ConversationControlApplication.BOTH


@pytest.mark.asyncio
async def test_application_string_still_parses_when_no_booleans_are_sent() -> None:
    """Pre-v15 payload/fixture (only the legacy `application` string, no `apply_now`/
    `persist_future` keys at all): must behave byte-identically to before this field existed --
    this is the exact case `test_control_application_both_parses` above already pins, restated
    here to make the precedence rule explicit."""
    provider = _ScriptedProvider(
        '{"scope":"IN_SCOPE","route":"REUSE","resolved_question":"q",'
        '"presentation":{"language":null,"detail":null},'
        '"conversation_control":{"kind":"UPDATE_PRESENTATION","presentation":'
        '{"language":"vi","detail":null},"application":"PREVIOUS_RESPONSE"}}'
    )
    verdict = await TurnInterpreter(provider, TurnInterpreterConfig()).interpret(
        _context(current_utterance="q"), _budget()
    )

    assert (
        verdict.conversation_control.application
        == ConversationControlApplication.PREVIOUS_RESPONSE
    )


# --------------------------------------------------------------------------------------------
# A1 remediation (F5 audit): `has_answerable_subject`, parsed independently of route/affect.
# --------------------------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("raw_value", ["true", "false"])
async def test_has_answerable_subject_parses_the_boolean(raw_value: str) -> None:
    provider = _ScriptedProvider(
        '{"scope":"IN_SCOPE","route":"SOCIAL","resolved_question":"q",'
        '"presentation":{"language":null,"detail":null},'
        f'"social_intent":"BUDDY_SUPPORT","affect":"SUPPORT_NEEDED",'
        f'"has_answerable_subject":{raw_value}}}'
    )
    verdict = await TurnInterpreter(provider, TurnInterpreterConfig()).interpret(
        _context(current_utterance="q"), _budget()
    )

    assert verdict.has_answerable_subject is (raw_value == "true")


@pytest.mark.asyncio
async def test_has_answerable_subject_fails_safe_to_false_when_missing() -> None:
    """A pre-v15 payload/fixture that never sends the field must degrade to `False` -- the value
    that fires no override anywhere it is consulted, so old behaviour is unaffected."""
    provider = _ScriptedProvider(
        '{"scope":"IN_SCOPE","route":"SOCIAL","resolved_question":"q",'
        '"presentation":{"language":null,"detail":null},'
        '"social_intent":"BUDDY_SUPPORT","affect":"SUPPORT_NEEDED"}'
    )
    verdict = await TurnInterpreter(provider, TurnInterpreterConfig()).interpret(
        _context(current_utterance="q"), _budget()
    )

    assert verdict.has_answerable_subject is False


@pytest.mark.asyncio
async def test_has_answerable_subject_survives_the_clarify_demotion() -> None:
    """Same discipline as `affect`: demoting CLARIFY to KNOWLEDGE is a route repair and must not
    silently drop this field (see the `interpret()` comment next to the CLARIFY-demotion block)."""
    provider = _ScriptedProvider(
        '{"scope":"IN_SCOPE","route":"CLARIFY","resolved_question":"q",'
        '"presentation":{"language":null,"detail":null},'
        '"has_answerable_subject":true}'
    )
    verdict = await TurnInterpreter(provider, TurnInterpreterConfig()).interpret(
        _context(current_utterance="q"), _budget()
    )

    assert verdict.route is InterpreterRoute.KNOWLEDGE  # clarify_enabled defaults False
    assert verdict.has_answerable_subject is True


@pytest.mark.asyncio
async def test_ti09_prompt_contains_knowledge_policy_section_and_migration_worked_example() -> None:
    """§6.1(a): the worked STRICT_INTERNAL example must be present verbatim in spirit -- pins
    that the migration-command case is stated, since it is the exact failure mode this field
    exists to prevent."""
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "KNOWLEDGE", "resolved_question": "q", '
        '"presentation": {"language": null, "detail": null}, "knowledge_policy": "STRICT_INTERNAL"}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig(knowledge_policy_enabled=True))

    await interpreter.interpret(_context(), _budget())

    system_message = provider.calls[0][0][1]
    assert "knowledge_policy" in system_message
    assert "migration command" in system_message
    assert "alembic upgrade head" in system_message


@pytest.mark.asyncio
async def test_ti10_knowledge_policy_name_collision_rule_is_semantic_not_marker_based() -> None:
    """F5 audit 2026-08-30 remediation #4a: the name-collision rule must no longer require an
    explicit genericity marker ('nói chung'/'in general') -- it is a QUESTION-FORM test instead,
    so a question about the pattern/concept itself resolves to GENERAL_ALLOWED even with no such
    marker, while a question about THIS project's own instance stays STRICT_INTERNAL. Pins the
    exact four worked examples from the audit's remediation request, the same way `test_ti09`
    pins the migration-command worked example -- whether the live model actually obeys this is
    Suite B's job, not this one."""
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "KNOWLEDGE", "resolved_question": "q", '
        '"presentation": {"language": null, "detail": null}, "knowledge_policy": "GENERAL_ALLOWED"}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig(knowledge_policy_enabled=True))

    await interpreter.interpret(_context(), _budget())

    system_message = provider.calls[0][0][1]
    # The rule is stated as a question-form test, not a marker lookup.
    assert "QUESTION FORM, not by spotting a marker word" in system_message
    assert "an explicit genericity marker is sufficient but was never necessary" in system_message
    # All four worked examples from the audit request, verbatim.
    assert '"Sidecar in software architecture?"' in system_message
    assert '"Explain the Sidecar design pattern"' in system_message
    assert '"Sidecar pros/cons"' in system_message
    assert "Where is Thanos Sidecar implemented?" in system_message
    # The two must land on opposite sides of the same worked example.
    assert (
        'all ask about the PATTERN -> GENERAL_ALLOWED, every one of them, marker or no marker'
        in system_message
    )
    assert "ask to LOCATE THIS PROJECT'S instance -> STRICT_INTERNAL" in system_message


# ------------------------------------------------------------------------------------------
# `social_intent` -- 2026-08-23 root-cause fix (CHANGE_LOG.md): the dispatcher used to
# unconditionally demote every interpreter-only SOCIAL verdict to KNOWLEDGE because it had no
# subtype to render a template with. The interpreter now emits `social_intent` alongside
# `route=SOCIAL`, closing that dispatch-contract gap without growing `social_reply.py`'s closed
# regex dictionary.
# ------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_social_intent_parses_a_named_subtype() -> None:
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "SOCIAL", "resolved_question": "cam on", '
        '"presentation": {"language": null, "detail": null}, "social_intent": "GRATITUDE"}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig())

    verdict = await interpreter.interpret(_context(current_utterance="cam on nhieu nha"), _budget())

    assert verdict.route is InterpreterRoute.SOCIAL
    assert verdict.social_intent is SocialIntent.GRATITUDE


@pytest.mark.asyncio
async def test_social_intent_other_covers_feelings_sharing_not_in_closed_dictionary() -> None:
    """Root-cause regression: "I'm really happy" isn't GRATITUDE/GREETING/FAREWELL/
    ACKNOWLEDGEMENT/TOPIC_CHANGE, so the model reports OTHER -- and the verdict must carry it
    through rather than dropping it."""
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "SOCIAL", "resolved_question": "chia se cam xuc vui", '
        '"presentation": {"language": null, "detail": null}, "social_intent": "OTHER"}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig())

    verdict = await interpreter.interpret(_context(current_utterance="I'm really happy"), _budget())

    assert verdict.route is InterpreterRoute.SOCIAL
    assert verdict.social_intent is SocialIntent.OTHER


@pytest.mark.asyncio
async def test_social_intent_missing_on_social_route_fails_safe_to_other() -> None:
    """Fail-safe default: a route=SOCIAL payload that omits `social_intent` entirely (or sends an
    unrecognized value) must still resolve to a renderable subtype, never `None` -- otherwise the
    dispatcher would be back to silently discarding a genuine SOCIAL verdict."""
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "SOCIAL", "resolved_question": "vui qua", '
        '"presentation": {"language": null, "detail": null}}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig())

    verdict = await interpreter.interpret(_context(current_utterance="vui quá"), _budget())

    assert verdict.route is InterpreterRoute.SOCIAL
    assert verdict.social_intent is SocialIntent.OTHER


@pytest.mark.asyncio
async def test_social_intent_language_preference_parses_alongside_presentation_language() -> None:
    """Third root-cause regression (CHANGE_LOG.md): "bạn nói tiếng việt đi" must parse as
    `social_intent=LANGUAGE_PREFERENCE` with `presentation.language="vi"` set alongside it -- the
    dispatcher needs both together to render a reply that confirms IN the target language rather
    than generic OTHER filler."""
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "SOCIAL", "resolved_question": "chuyen sang tieng viet", '
        '"presentation": {"language": "vi", "detail": null}, '
        '"social_intent": "LANGUAGE_PREFERENCE"}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig())

    verdict = await interpreter.interpret(
        _context(current_utterance="bạn nói tiếng việt đi"), _budget()
    )

    assert verdict.route is InterpreterRoute.SOCIAL
    assert verdict.social_intent is SocialIntent.LANGUAGE_PREFERENCE
    assert verdict.presentation.language == "vi"


@pytest.mark.asyncio
async def test_social_intent_unrecognized_value_fails_safe_to_other() -> None:
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "SOCIAL", "resolved_question": "vui qua", '
        '"presentation": {"language": null, "detail": null}, "social_intent": "EXCITED"}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig())

    verdict = await interpreter.interpret(_context(current_utterance="vui quá"), _budget())

    assert verdict.social_intent is SocialIntent.OTHER


@pytest.mark.asyncio
async def test_social_intent_is_ignored_outside_social_route() -> None:
    """A stray `social_intent` on a non-SOCIAL route must never leak through -- it is only
    meaningful for route=SOCIAL."""
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "KNOWLEDGE", "resolved_question": "VPN policy", '
        '"presentation": {"language": null, "detail": null}, "social_intent": "GRATITUDE"}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig())

    verdict = await interpreter.interpret(_context(), _budget())

    assert verdict.route is InterpreterRoute.KNOWLEDGE
    assert verdict.social_intent is None


@pytest.mark.asyncio
async def test_social_intent_none_when_route_demoted_from_clarify() -> None:
    """A CLARIFY route demoted to KNOWLEDGE (clarify disabled) never had a `social_intent` to
    begin with -- must stay None, not fail-safe to OTHER."""
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "CLARIFY", "resolved_question": "cái đó là gì", '
        '"presentation": {"language": null, "detail": null}}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig(clarify_enabled=False))

    verdict = await interpreter.interpret(_context(), _budget())

    assert verdict.route is InterpreterRoute.KNOWLEDGE
    assert verdict.social_intent is None


@pytest.mark.asyncio
async def test_prompt_excludes_reuse_when_previous_turn_had_no_real_answer() -> None:
    """Second root-cause fix (CHANGE_LOG.md): a language-switch/presentation request after a
    purely social previous turn (no `evidence_titles`, no real answer) must not be routed REUSE
    -- there is nothing to re-present. Pins that the prompt actually states this exclusion and
    its worked example, the same way `test_ti09_...` pins the knowledge_policy worked example."""
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "SOCIAL", "resolved_question": "q", '
        '"presentation": {"language": null, "detail": null}, "social_intent": "OTHER"}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig())

    await interpreter.interpret(_context(), _budget())

    system_message = provider.calls[0][0][1]
    assert "evidence_titles" in system_message
    assert "REUSE cannot apply" in system_message
    assert "bạn nói tiếng việt đi" in system_message


@pytest.mark.asyncio
async def test_social_intent_buddy_support_parses() -> None:
    """`SocialIntent.BUDDY_SUPPORT` (2026-08-25): affect-only onboarding distress. Interpreter-
    only like OTHER -- `classify_social` never produces it (pinned in test_social_reply.py) --
    so the verdict carrying it through IS the whole mechanism."""
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "SOCIAL", "resolved_question": "Chia se cam giac tu ti", '
        '"presentation": {"language": null, "detail": null}, "social_intent": "BUDDY_SUPPORT"}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig())

    verdict = await interpreter.interpret(
        _context(current_utterance="toi thay minh kem qua"), _budget()
    )

    assert verdict.route is InterpreterRoute.SOCIAL
    assert verdict.social_intent is SocialIntent.BUDDY_SUPPORT


@pytest.mark.asyncio
async def test_buddy_support_is_ignored_outside_social_route() -> None:
    """The exclusion rules in the prompt route "affect + a nameable subject" to KNOWLEDGE. If the
    model nevertheless attaches BUDDY_SUPPORT to that verdict, the field must be dropped -- a
    KNOWLEDGE turn that rendered a template instead of retrieving would silently swallow a real
    question behind a sympathetic reply."""
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "KNOWLEDGE", "resolved_question": "Auth module hoat dong '
        'the nao", "presentation": {"language": null, "detail": null}, '
        '"social_intent": "BUDDY_SUPPORT"}'
    )
    interpreter = TurnInterpreter(provider, TurnInterpreterConfig())

    verdict = await interpreter.interpret(
        _context(current_utterance="nan qua, auth module hoat dong the nao?"), _budget()
    )

    assert verdict.route is InterpreterRoute.KNOWLEDGE
    assert verdict.social_intent is None


def test_prompt_states_both_buddy_support_exclusions() -> None:
    """The two exclusions are the only thing standing between BUDDY_SUPPORT and a widened SOCIAL
    surface -- and route=SOCIAL skips `ScopeGate` entirely (`_ask_with_interpreter`), so exclusion
    (2) is the ONLY defense against an injection/credential request wearing an emotional wrapper
    on this path. Pin that both survive future prompt edits."""
    assert "BUDDY_SUPPORT" in _SYSTEM_INSTRUCTIONS
    assert "Affect plus a nameable subject is KNOWLEDGE, never SOCIAL" in _SYSTEM_INSTRUCTIONS
    assert "NEVER route=SOCIAL" in _SYSTEM_INSTRUCTIONS


def test_prompt_covers_the_question_form_of_buddy_support() -> None:
    """Live bug 2026-08-25: the first BUDDY_SUPPORT definition described only DECLARATIONS of
    distress ("tôi thấy mình kém quá"). The user actually typed a QUESTION -- "Bạn có thấy mình
    kém cỏi ko" -- which the model read as a question needing an answer, routed KNOWLEDGE, and
    `ScopeGate` then rejected as personal advice. Asking the assistant for a judgement about the
    user has no answerable subject and must land on the same subtype as the statement."""
    assert "The phrasing is a QUESTION as often as it is a statement" in _SYSTEM_INSTRUCTIONS
    assert "there is no subject to retrieve and it is not KNOWLEDGE" in _SYSTEM_INSTRUCTIONS
    # The dividing line must stay stated, or this widening swallows answerable questions.
    assert "asking what to do, what exists, or what is required" in _SYSTEM_INSTRUCTIONS


def test_prompt_defines_buddy_support_by_condition_not_by_phrase_list() -> None:
    """The redesign's own guardrail against relapse. The v7 prompt described BUDDY_SUPPORT by
    enumerating distress phrasings, which is the same failure mode as the `_SELF_DOUBT` regex one
    layer down -- both cover the shapes someone thought to write, and both are "fixed" by adding
    another. v8 states a CONDITION and demotes the examples to illustration, in as many words, so
    a later editor extending the list can see the list is not the test.
    """
    assert "defined by a CONDITION, not by a list of phrases" in _SYSTEM_INSTRUCTIONS
    assert "the list above is illustration, never the test" in _SYSTEM_INSTRUCTIONS


def test_prompt_declares_affect_orthogonal_to_route() -> None:
    """The whole contract change, pinned as text. `affect` must be asked on EVERY turn and must be
    incapable of moving `route` or `scope` -- if either half of that is deleted from the prompt,
    the field collapses back into "another way to say SOCIAL" and the mixed turn ("tôi nản quá,
    giải thích auth module cho tôi được ko?") loses its correct reading again.
    """
    assert "=== affect ===" in _SYSTEM_INSTRUCTIONS
    assert "Answer this on EVERY turn, whatever the route" in _SYSTEM_INSTRUCTIONS
    assert "This field can NEVER make a turn in-scope" in _SYSTEM_INSTRUCTIONS
    # The mixed-turn worked example is what teaches the pairing; a rule without it did not hold.
    assert "affect=SUPPORT_NEEDED, resolved_question=" in _SYSTEM_INSTRUCTIONS
    assert "route=KNOWLEDGE, affect=NONE" in _SYSTEM_INSTRUCTIONS
    # Unsure -> NONE, the opposite default from `scope`, for the reason stated in the prompt.
    assert "When you are not sure, choose NONE" in _SYSTEM_INSTRUCTIONS


def test_prompt_keeps_the_mixed_affect_exclusion_with_both_reported_examples() -> None:
    """Exclusion (1) is the only thing standing between this feature and an assistant that
    answers "mệt thật, VPN của project cấu hình ở đâu?" with a sympathy template. Both mixed turns
    named in the redesign brief must stay in the prompt as worked KNOWLEDGE examples."""
    assert "Affect plus a nameable subject is KNOWLEDGE, never SOCIAL" in _SYSTEM_INSTRUCTIONS
    assert "mệt thật, VPN của project cấu hình ở đâu?" in _SYSTEM_INSTRUCTIONS
    assert "nản quá, auth module hoạt động thế nào?" in _SYSTEM_INSTRUCTIONS
    # ...and the feeling must still be REPORTED on such a turn, or the acknowledgement half of
    # the design has no input.
    assert "The feeling is NOT discarded on such a turn" in _SYSTEM_INSTRUCTIONS


def test_prompt_says_the_messages_own_language_is_not_a_switch_request() -> None:
    """Same live bug, other half: the model filled `presentation.language="vi"` on a Vietnamese
    message that asked to switch nothing, which the dispatcher then promoted into a
    LANGUAGE_PREFERENCE reply. The dispatcher no longer trusts that field over a specific label
    (`test_chat_buddy_support.py`), but the field should not be wrong in the first place."""
    assert "is NOT a request to switch" in _SYSTEM_INSTRUCTIONS
    assert 'A Vietnamese message is not "vi"' in _SYSTEM_INSTRUCTIONS


# ------------------------------------------------------------------------------------------
# v5 contract sections (audit 2026-08-25). These are text assertions on the prompt, and that is
# all they can be: whether the model OBEYS these rules is a live-eval question. They exist so a
# later prompt edit cannot silently delete a rule that closed a reported production bug -- the
# same job `test_ti09` already does for `knowledge_policy`.
# ------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_v5_prompt_routes_history_verification_questions_to_conversation() -> None:
    """B-04. "Tôi đã nói ở trên rằng team dùng Redis đúng không?" came back SOCIAL/ACKNOWLEDGEMENT
    and was answered with an agreement template. The rule that a tag question asking to CHECK the
    transcript is CONVERSATION -- and explicitly never ACKNOWLEDGEMENT -- must stay stated."""
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "CONVERSATION", "resolved_question": "q", '
        '"presentation": {"language": null, "detail": null}}'
    )
    await TurnInterpreter(provider, TurnInterpreterConfig()).interpret(_context(), _budget())

    system_message = provider.calls[0][0][1]
    assert "VERIFICATION question" in system_message
    assert "đúng không?" in system_message
    assert "never ACKNOWLEDGEMENT" in system_message


@pytest.mark.asyncio
async def test_v5_prompt_requires_resolved_question_to_preserve_intent() -> None:
    """B-06. `resolved_question` for "tại sao dùng database đó?" was collapsing to the previous
    turn's SUBJECT, so `EvidenceSufficiencyGate` judged the reused evidence against the wrong
    proposition, returned SUFFICIENT, and the turn re-emitted the previous answer verbatim. The
    R1/R5 machinery was already correct; it was being asked the wrong question."""
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "KNOWLEDGE", "resolved_question": "q", '
        '"presentation": {"language": null, "detail": null}}'
    )
    await TurnInterpreter(provider, TurnInterpreterConfig()).interpret(_context(), _budget())

    system_message = provider.calls[0][0][1]
    assert "PRESERVE THE CURRENT TURN'S INTENT" in system_message
    assert "tại sao dùng database đó?" in system_message
    # The worked example must show the WHY surviving resolution, not just say so.
    assert "Tại sao dự án dùng" in system_message


@pytest.mark.asyncio
async def test_v5_prompt_resolves_a_user_assertion_into_a_question() -> None:
    """B-05's semantic half. `resolved_question` is persisted as the turn's `retrieval_query` and
    becomes the next turn's coreference anchor (`conversation_memory.build_window`), so echoing an
    assertion here would steer later turns toward what the user claimed."""
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "KNOWLEDGE", "resolved_question": "q", '
        '"presentation": {"language": null, "detail": null}}'
    )
    await TurnInterpreter(provider, TurnInterpreterConfig()).interpret(_context(), _budget())

    system_message = provider.calls[0][0][1]
    assert "ASSERTION" in system_message
    assert "Thanos dùng MongoDB nhé" in system_message
    assert "never to the assertion itself" in system_message


@pytest.mark.asyncio
async def test_v7_prompt_forbids_softening_a_specific_question() -> None:
    """B-06 follow-up, measured on run_20260825T132725Z. v5 stated the intent rule in one
    direction only (do not collapse a WHY into its subject). The trace showed the mirror leak:
    "Công ty áp dụng mức phạt bao nhiêu tiền...?" was resolved to "Công ty có mức phạt nào...
    không?" -- adjacent evidence answers that weaker question, so ESG said PARTIAL rather than
    INSUFFICIENT and the turn answered without the amount. Pin that the mirror half stays."""
    provider = _ScriptedProvider(
        '{"scope": "IN_SCOPE", "route": "KNOWLEDGE", "resolved_question": "q", '
        '"presentation": {"language": null, "detail": null}}'
    )
    await TurnInterpreter(provider, TurnInterpreterConfig()).interpret(_context(), _budget())

    system_message = provider.calls[0][0][1]
    assert "NEVER WEAKEN A SPECIFIC QUESTION INTO AN EXISTENCE QUESTION" in system_message
    assert "mức phạt bao nhiêu tiền" in system_message
    assert "'bao nhiêu' stays 'bao nhiêu'" in system_message
