"""Regression tests for the 2026-08-27 conversation/orchestration boundary pass.

One file, because the five behaviours below are all instances of the same rule and are easiest to
read against each other: **a guardrail must degrade exactly the capability it guards, and nothing
else.** Same harness as `test_chat_general_knowledge.py` (scripted interpreter/gate/generator, real
`ChatService`, real DB session) -- these prove DISPATCH and PERSISTENCE, not model quality.

Covered:
1. a validated presentation control persists even when the topical ScopeGate rejects its turn;
2. a CONVERSATION turn survives a context-free ScopeGate rejection, while KNOWLEDGE does not;
3. a retrieval outage degrades only the internally-grounded part, and only when the interpreter
   already judged some part company-independent;
4. an outage never becomes `insufficient_evidence` (invariant 8), even via the BGK §10.3 path;
5. a degraded INTERPRETATION stops the answer over-claiming, without changing its reason;
6. a `GENERAL_ALLOWED` turn with evidence still cites the company-specific claim (permission to
   add general guidance is not permission to leave an internal fact unanchored);
7. the `validator_fail` copy no longer describes itself as a missing source.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from src.ai.orchestration.answer_generator import GenerationFailure
from src.ai.orchestration.conversation_answer import ConversationAnswerGenerator
from src.ai.orchestration.evidence_sufficiency_gate import (
    EvidenceSufficiencyResult,
    EvidenceSufficiencyVerdict,
)
from src.ai.orchestration.turn_interpreter import (
    ConversationControl,
    ConversationControlApplication,
    ConversationControlKind,
    InterpreterRoute,
    InterpreterScope,
    InterpreterVerdict,
    KnowledgePolicy,
    PresentationOverlay,
    TurnInterpreter,
    TurnInterpreterConfig,
)
from src.ai.retrieval_engine.retrieval_engine import RetrievalFilters, RetrievalResult
from src.model.chat_session import ChatSession
from src.model.citation import Citation
from src.model.enums import DocumentDomain
from src.modules.chat.application.chat_service import AnswerLanguage
from src.shared.ai.external_failures import ExternalFailureCode, ExternalServiceFailure
from tests.test_modules.test_chat_general_knowledge import (
    RecordingRetriever,
    ScriptedEvidenceGate,
    ScriptedGenerator,
    ScriptedTurnInterpreter,
    _candidate,
    _claim_result,
    _guidance_only_result,
    _mixed_result,
    _project_membership,
    _RecordingScopeGate,
    _service,
    _user,
)


class _OutageRetriever(RecordingRetriever):
    """Embedding provider down: `_retrieve` raises exactly what the real engine raises."""

    def __init__(self) -> None:
        super().__init__([])
        self.attempts = 0

    async def retrieve(self, question: str, *, filters: RetrievalFilters, budget) -> list[RetrievalResult]:
        self.attempts += 1
        raise ExternalServiceFailure(
            service="embedding", code=ExternalFailureCode.UNAVAILABLE, retryable=True
        )


class _ConversationProvider:
    def __init__(self, responses: list[str]) -> None:
        self._responses = iter(responses)
        self.messages: list[list[tuple[str, str]]] = []

    async def complete(self, messages, _budget, _operation):
        self.messages.append(list(messages))
        return SimpleNamespace(content=next(self._responses))

    def last_prompt(self) -> str:
        return "\n".join(content for _role, content in self.messages[-1])


class _InterpreterProvider:
    """Exercises the real parser and timeout wrapper in `TurnInterpreter.interpret`."""

    def __init__(self, content: str, *, delay_seconds: float = 0.0) -> None:
        self.content = content
        self.delay_seconds = delay_seconds

    async def complete(self, _messages, _budget, _operation):
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        return SimpleNamespace(content=self.content)


async def _persisted_language(db_session, conversation_id) -> str | None:
    row = await db_session.scalar(
        select(ChatSession).where(ChatSession.public_id == conversation_id)
    )
    await db_session.refresh(row)
    return row.preferred_language


def _control_verdict(
    route: InterpreterRoute,
    resolved_question: str,
    *,
    application: ConversationControlApplication | None = None,
) -> InterpreterVerdict:
    """An EXPLICITLY LABELLED control -- what `_parse` produces only when the model set
    `kind=UPDATE_PRESENTATION`. A bare `presentation.language` overlay is deliberately NOT this
    (the model also fills that field from the language the message merely happens to be in).

    `application` defaults to `None` (the dispatcher's opt-in-only default resolves that to
    FUTURE_TURNS-only, per the F5 audit finding #1 remediation -- see
    `ConversationControlApplication`'s docstring) -- pass `PREVIOUS_RESPONSE`/`BOTH` explicitly for
    a scripted verdict that needs the previous answer re-rendered now."""
    return InterpreterVerdict(
        scope=InterpreterScope.IN_SCOPE,
        route=route,
        resolved_question=resolved_question,
        presentation=PresentationOverlay(language="vi"),
        conversation_control=ConversationControl(
            kind=ConversationControlKind.UPDATE_PRESENTATION,
            presentation=PresentationOverlay(language="vi"),
            application=application,
        ),
    )


# ---------------------------------------------------------------------------------------------
# 1. A validated presentation control is trusted state, not a reward for passing the topic gate.
# ---------------------------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("route", [InterpreterRoute.KNOWLEDGE, InterpreterRoute.CONVERSATION])
async def test_presentation_control_persists_even_when_the_scope_gate_rejects_the_turn(
    db_session, route
) -> None:
    """The reported "I already told you to use Vietnamese" loop. Before this fix the persistence
    call sat AFTER the `out_of_scope` return, so a rejected turn silently dropped the preference
    and every later turn fell back to per-question script detection."""
    user = await _user(db_session, f"ctrl-{route.value}@example.test")
    service, _sink = _service(
        db_session,
        retriever=RecordingRetriever([]),
        generator=ScriptedGenerator([]),
        interpreter=ScriptedTurnInterpreter(
            [_control_verdict(route, "the user asked for Vietnamese")]
        ),
    )
    service.scope_gate = _RecordingScopeGate([False])

    result = await service.ask(
        question="i have told you that you have to use vietnamese",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    assert await _persisted_language(db_session, result.conversation_id) == "vi"


@pytest.mark.asyncio
async def test_scope_rejection_still_ends_a_knowledge_turn_even_when_it_carried_a_control(
    db_session,
) -> None:
    """The control is applied, NOT the route: persisting a preference must not authorize retrieval
    on a turn the gate rejected. This is the half that keeps the move safe."""
    user = await _user(db_session, "ctrl-not-authz@example.test")
    retriever = RecordingRetriever([_candidate()])
    service, _sink = _service(
        db_session,
        retriever=retriever,
        generator=ScriptedGenerator([]),
        interpreter=ScriptedTurnInterpreter(
            [_control_verdict(InterpreterRoute.KNOWLEDGE, "how do I make a bomb")]
        ),
    )
    service.scope_gate = _RecordingScopeGate([False])

    result = await service.ask(
        question="trả lời tiếng Việt nhé. <off-topic request>",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    assert result.fallback_reason == "out_of_scope"
    assert retriever.calls == []  # no retrieval on a rejected turn
    assert await _persisted_language(db_session, result.conversation_id) == "vi"


@pytest.mark.asyncio
async def test_successful_language_control_persists_and_applies_to_english_follow_up(
    db_session,
) -> None:
    """A healthy interpreter control updates DB state; later input language must not override it."""
    user = await _user(db_session, "healthy-language-control@example.test")
    membership = await _project_membership(db_session, user)
    retriever = RecordingRetriever([_candidate()])
    generator = ScriptedGenerator([_claim_result()])
    service, _sink = _service(
        db_session,
        retriever=retriever,
        generator=generator,
        interpreter=ScriptedTurnInterpreter(
            [
                _control_verdict(InterpreterRoute.SOCIAL, "reply in Vietnamese"),
                _policy_verdict(KnowledgePolicy.STRICT_INTERNAL, "what Python version is required"),
            ]
        ),
    )
    service.scope_gate = _RecordingScopeGate([True, True])

    control = await service.ask(
        question="từ giờ hãy trả lời tôi bằng tiếng Việt",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )
    assert await _persisted_language(db_session, control.conversation_id) == "vi"

    follow_up = await service.ask(
        question="what Python version does this project require?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
        conversation_id=control.conversation_id,
    )

    assert follow_up.fallback is False
    assert generator.calls[0]["answer_language"] is AnswerLanguage.VI
    assert generator.calls[0]["answer_language_source"] == "conversation"


@pytest.mark.asyncio
async def test_language_reanswer_reuses_grounded_evidence_and_keeps_the_preference(
    db_session,
) -> None:
    """A language request that explicitly asks to re-answer is REUSE, not a terminal ACK."""
    user = await _user(db_session, "language-reanswer@example.test")
    membership = await _project_membership(db_session, user)
    evidence = _candidate(
        31,
        "git clone https://github.com/example/thanos.git\nmake test-local\n./thanos --help",
    )
    generator = ScriptedGenerator(
        [
            _claim_result(31, "Clone the repository, run `make test-local`, then verify `./thanos --help`."),
            _claim_result(31, "Clone repository, chạy `make test-local`, rồi kiểm tra `./thanos --help`."),
            _claim_result(31, "Cài Git, Go và Make; clone repository rồi chạy `make test-local`."),
        ]
    )
    interpreter = ScriptedTurnInterpreter(
        [
            _policy_verdict(KnowledgePolicy.STRICT_INTERNAL, "Cách chạy dự án Thanos trên máy local?"),
            _control_verdict(
                InterpreterRoute.REUSE,
                "Cách chạy dự án Thanos trên máy local?",
                application=ConversationControlApplication.BOTH,
            ),
            InterpreterVerdict(
                scope=InterpreterScope.IN_SCOPE,
                route=InterpreterRoute.REUSE,
                resolved_question="Cách chạy dự án Thanos trên máy local?",
                presentation=PresentationOverlay(),
            ),
        ]
    )
    gate = ScriptedEvidenceGate(
        [
            EvidenceSufficiencyResult(EvidenceSufficiencyVerdict.SUFFICIENT, errored=False),
            EvidenceSufficiencyResult(EvidenceSufficiencyVerdict.SUFFICIENT, errored=False),
            EvidenceSufficiencyResult(EvidenceSufficiencyVerdict.SUFFICIENT, errored=False),
        ]
    )
    retriever = RecordingRetriever([evidence])
    service, sink = _service(
        db_session,
        retriever=retriever,
        generator=generator,
        interpreter=interpreter,
        gate=gate,
    )
    service.scope_gate = _RecordingScopeGate([True, True, True])

    setup = await service.ask(
        question="Làm thế nào để chạy dự án trên máy local?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )
    vietnamese = await service.ask(
        question="hãy trả lời bằng tiếng việt cho tôi, tôi không biết tiếng anh",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
        conversation_id=setup.conversation_id,
    )
    replay = await service.ask(
        question="trả lời lại câu hỏi về cách setup",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
        conversation_id=setup.conversation_id,
    )

    assert vietnamese.answer.startswith("Clone repository")
    assert vietnamese.answer != "Được rồi, mình sẽ trả lời bằng tiếng Việt nhé! Bạn cần hỏi gì?"
    assert vietnamese.citations[0]["chunk_id"] == 31
    assert await _persisted_language(db_session, setup.conversation_id) == "vi"
    assert replay.answer.endswith("`make test-local`.")
    assert replay.answer_status == "verified"
    assert len(retriever.calls) == 1  # the latter two turns reloaded, rather than retrieved
    assert gate.calls[1:] == [
        ("Cách chạy dự án Thanos trên máy local?", 1),
        ("Cách chạy dự án Thanos trên máy local?", 1),
    ]
    assert sink.decision_details()["interpreter_route"] == "REUSE"


# ---------------------------------------------------------------------------------------------
# F5 audit 2026-08-30, root cause #2 (repro, then fix if confirmed): does a SOCIAL/presentation-
# control turn's raw text get glued onto a following STANDALONE short question before it ever
# reaches `ScopeGate`? Live transcript: "từ giờ hãy trả lời bằng tiếng Việt nhé" (ack-only, zero
# retrieval) immediately followed by "dự án có kiến trúc như thế nào?" (a complete, standalone
# question that is merely short in Vietnamese) -- the first false-refused, the near-identical
# rephrasing "kiến trúc của dự án" right after it succeeded. `condense()`'s `is_followup()` marks
# ANY short message a follow-up (<=6 words or <=40 chars) independent of content, so `condense()`
# prepends `anchor_questions[0]` -- and a zero-retrieval SOCIAL ack persists no `retrieval_query`,
# so `build_window`'s anchor falls back to that turn's RAW question (`conversation_memory.py`'s
# B-05 comment: "a turn that legitimately never retrieved ... still carries topical signal").
# That raw text is a presentation instruction, not a subject -- gluing it in front of an unrelated
# standalone question is pure noise for a scope classifier, never a real coreference anchor.
# ---------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_social_ack_anchor_is_not_glued_onto_the_next_standalone_question(db_session) -> None:
    user = await _user(db_session, "scope-anchor-social@example.test")
    membership = await _project_membership(db_session, user)
    interpreter = ScriptedTurnInterpreter(
        [
            _control_verdict(InterpreterRoute.SOCIAL, "Update the conversation presentation preference"),
            _policy_verdict(KnowledgePolicy.STRICT_INTERNAL, "Kiến trúc của dự án Thanos là gì?"),
        ]
    )
    service, _sink = _service(
        db_session,
        retriever=RecordingRetriever([_candidate()]),
        generator=ScriptedGenerator([_claim_result()]),
        interpreter=interpreter,
        gate=ScriptedEvidenceGate(
            [EvidenceSufficiencyResult(EvidenceSufficiencyVerdict.SUFFICIENT, errored=False)]
        ),
    )
    scope_gate = _RecordingScopeGate([True, True])
    service.scope_gate = scope_gate

    ack = await service.ask(
        question="từ giờ hãy trả lời bằng tiếng Việt nhé",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )
    await service.ask(
        question="dự án có kiến trúc như thế nào?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
        conversation_id=ack.conversation_id,
    )

    # The load-bearing assertion: the text handed to ScopeGate for the second turn must be the
    # standalone question itself, never the first (non-informational) turn's text prepended.
    assert scope_gate.calls[-1] == "dự án có kiến trúc như thế nào?"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "resolved_question"),
    [
        ("hướng dẫn clone", "Cách clone repository của dự án Thanos như thế nào?"),
        ("hướng dẫn clone thanos", "Cách clone dự án Thanos như thế nào?"),
    ],
)
async def test_explicit_clone_procedure_uses_only_the_clone_section(
    db_session, question, resolved_question
) -> None:
    """A procedural clone question is source-faithful and never falls through to LLM repair."""
    user = await _user(db_session, f"clone-{question.replace(' ', '-')}@example.test")
    membership = await _project_membership(db_session, user)
    setup = _candidate(41, "Install Go and GNU Make.")
    setup.chunk.section_path = "Thanos setup > 2. Required tools"
    clone = _candidate(42, "git clone https://github.com/example/thanos.git\ngit remote add upstream https://github.com/thanos-io/thanos.git")
    clone.chunk.section_path = "Thanos setup > 3. Clone the repository"
    retriever = RecordingRetriever([setup, clone], section_expansion=[clone, setup])
    interpreter = ScriptedTurnInterpreter(
        [_policy_verdict(KnowledgePolicy.STRICT_INTERNAL, resolved_question)]
    )
    generator = ScriptedGenerator([])
    service, sink = _service(
        db_session,
        retriever=retriever,
        generator=generator,
        interpreter=interpreter,
    )
    service.gate.settings["procedure_section_expansion"] = {"enabled": True}
    service.scope_gate = _RecordingScopeGate([True])

    result = await service.ask(
        question=question,
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )

    assert result.fallback is False
    assert "git clone" in result.answer
    assert "Install Go" not in result.answer
    assert [item["chunk_id"] for item in result.citations] == [42]
    assert generator.calls == []
    assert retriever.calls[0][0] == resolved_question
    assert sink.decision_details()["interpreter_route"] == "KNOWLEDGE"
    assert sink.decision_details()["generation_strategy"] == "source_faithful_numbered_procedure"


# ---------------------------------------------------------------------------------------------
# 2. CONVERSATION survives a CONTEXT-FREE topical rejection; nothing that reads the corpus does.
# ---------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_conversation_turn_survives_scope_rejection_and_explains_the_prior_outcome(
    db_session,
) -> None:
    """The reported "sao lại không có nguồn?" failure, end to end.

    Turn 1 finds evidence but fails quote anchoring -> `validator_fail`. Turn 2 asks about THAT
    REPLY. `_pre_route_scope_check` sees a raw utterance with no project subject and rejects it;
    the context-aware interpreter reads it as CONVERSATION. Three things must hold: the turn is not
    refused, no retrieval happens, and the prompt carries the TRUSTED outcome of turn 1 -- so the
    answer can say "sources were found but couldn't be quote-anchored" instead of guessing.
    """
    user = await _user(db_session, "meta-recovery@example.test")
    membership = await _project_membership(db_session, user)
    retriever = RecordingRetriever([_candidate()])
    provider = _ConversationProvider(["Ở lượt trước Ralion có tìm thấy tài liệu liên quan..."])
    service, sink = _service(
        db_session,
        retriever=retriever,
        generator=ScriptedGenerator([GenerationFailure(reason="validator_fail", retry_count=1)]),
        interpreter=ScriptedTurnInterpreter(
            [
                InterpreterVerdict(
                    scope=InterpreterScope.IN_SCOPE,
                    route=InterpreterRoute.KNOWLEDGE,
                    resolved_question="dự án dùng database gì",
                    presentation=PresentationOverlay(),
                ),
                InterpreterVerdict(
                    scope=InterpreterScope.IN_SCOPE,
                    route=InterpreterRoute.CONVERSATION,
                    resolved_question="why did the previous reply say there was no source",
                    presentation=PresentationOverlay(),
                ),
            ]
        ),
    )
    service.conversation_answer_generator = ConversationAnswerGenerator(provider)
    service.scope_gate = _RecordingScopeGate([True, False])

    turn1 = await service.ask(
        question="dự án dùng database gì",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )
    assert turn1.fallback_reason == "validator_fail"
    retrieval_calls_after_turn1 = len(retriever.calls)

    turn2 = await service.ask(
        question="sao lại không có nguồn?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
        conversation_id=turn1.conversation_id,
    )

    assert turn2.fallback is False
    assert turn2.fallback_reason is None
    assert len(retriever.calls) == retrieval_calls_after_turn1  # CONVERSATION reads no corpus
    assert sink.decision_details()["scope_recovered_by"] == "conversation"

    prompt = provider.last_prompt()
    assert "OUTCOME of the assistant turn above:" in prompt
    assert "could not be anchored to an exact quote" in prompt
    # Provenance rules must travel with the outcome, or the model could "helpfully" re-assert the
    # withheld claim as established fact.
    assert "never restated as a fact you are now vouching for" in prompt


@pytest.mark.asyncio
async def test_conversation_recovery_does_not_extend_to_the_knowledge_route(db_session) -> None:
    """The recovery is route-scoped by construction. A rejected turn the interpreter reads as
    KNOWLEDGE is still refused -- otherwise the gate would be advisory."""
    user = await _user(db_session, "no-knowledge-recovery@example.test")
    membership = await _project_membership(db_session, user)
    retriever = RecordingRetriever([_candidate()])
    service, _sink = _service(
        db_session,
        retriever=retriever,
        generator=ScriptedGenerator([_claim_result()]),
        interpreter=ScriptedTurnInterpreter(
            [
                InterpreterVerdict(
                    scope=InterpreterScope.IN_SCOPE,
                    route=InterpreterRoute.KNOWLEDGE,
                    resolved_question="an off-topic question",
                    presentation=PresentationOverlay(),
                )
            ]
        ),
    )
    service.scope_gate = _RecordingScopeGate([False])

    result = await service.ask(
        question="an off-topic question",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )

    assert result.fallback_reason == "out_of_scope"
    assert retriever.calls == []


@pytest.mark.asyncio
async def test_out_of_scope_general_allowed_recovers_as_guidance_with_zero_corpus_access(
    db_session,
) -> None:
    """A healthy independent general-policy verdict may recover, but cannot read internal data."""
    user = await _user(db_session, "off-topic-guidance@example.test")
    membership = await _project_membership(db_session, user)
    retriever = RecordingRetriever([_candidate()])
    generator = ScriptedGenerator(
        [_guidance_only_result("Install Prometheus with the official Windows-compatible package.")]
    )
    service, sink = _service(
        db_session,
        retriever=retriever,
        generator=generator,
        interpreter=ScriptedTurnInterpreter(
            [
                _policy_verdict(
                    KnowledgePolicy.GENERAL_ALLOWED,
                    "how to install Prometheus on Windows",
                )
            ]
        ),
    )
    service.scope_gate = _RecordingScopeGate([False])

    result = await service.ask(
        question="explain Prometheus and how to install it on Windows",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )

    assert result.fallback is False
    assert result.answer_shape == "guidance_only"
    assert result.claims == ()
    assert result.citations == ()
    assert "general technical guidance" in result.answer
    assert retriever.calls == []
    assert retriever.list_available_topics_calls == 0
    assert retriever.load_scoped_chunks_calls == 0
    assert retriever.list_catalog_calls == 0
    assert generator.calls[0]["candidate_count"] == 0
    assert (await db_session.execute(select(Citation))).scalars().all() == []
    details = sink.decision_details()
    assert details["scope_recovered_by"] == "general_knowledge"
    assert details["off_topic_guidance"] is True
    assert details["knowledge_policy_effective"] == "GENERAL_ALLOWED"


@pytest.mark.asyncio
async def test_conversation_recovery_requires_a_clean_verdict_and_a_prior_turn(db_session) -> None:
    """Turn 1 has nothing to recall, and a degraded verdict is not evidence of anything -- neither
    may buy a scope bypass. Without this, an interpreter timeout would become a gate bypass."""
    user = await _user(db_session, "recovery-preconditions@example.test")
    service, _sink = _service(
        db_session,
        retriever=RecordingRetriever([]),
        generator=ScriptedGenerator([]),
        interpreter=ScriptedTurnInterpreter(
            [
                InterpreterVerdict(
                    scope=InterpreterScope.IN_SCOPE,
                    route=InterpreterRoute.CONVERSATION,
                    resolved_question="what did I ask first",
                    presentation=PresentationOverlay(),
                    errored=True,
                )
            ]
        ),
    )
    service.scope_gate = _RecordingScopeGate([False])

    result = await service.ask(
        question="what did I ask first?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    assert result.fallback_reason == "out_of_scope"


# ---------------------------------------------------------------------------------------------
# 3./4. A dependency failure degrades only what depends on that dependency -- and never renames
# itself into a knowledge gap.
# ---------------------------------------------------------------------------------------------


def _policy_verdict(policy: KnowledgePolicy, question: str) -> InterpreterVerdict:
    return InterpreterVerdict(
        scope=InterpreterScope.IN_SCOPE,
        route=InterpreterRoute.KNOWLEDGE,
        resolved_question=question,
        presentation=PresentationOverlay(),
        knowledge_policy=policy,
    )

@pytest.mark.asyncio
async def test_retrieval_outage_answers_the_company_independent_part_and_discloses_the_rest(
    db_session,
) -> None:
    """Failure 5 in the report: `embedding_unavailable` used to return `system_error` for every
    question, including the parts that never needed internal evidence."""
    user = await _user(db_session, "outage-general@example.test")
    membership = await _project_membership(db_session, user)
    generator = ScriptedGenerator([_guidance_only_result()])
    service, sink = _service(
        db_session,
        retriever=_OutageRetriever(),
        generator=generator,
        interpreter=ScriptedTurnInterpreter(
            [
                _policy_verdict(
                    KnowledgePolicy.GENERAL_ALLOWED,
                    "Thanos dùng database gì, ưu nhược điểm của loại đó là gì?",
                )
            ]
        ),
    )

    result = await service.ask(
        question="Thanos dùng database gì? Trình bày ưu, nhược điểm của database đó.",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )

    assert result.fallback is False
    assert result.answer_shape == "guidance_only"
    # Grounding is NOT weakened: with no evidence the generator can produce no claim at all, so
    # the company-specific part stays uncitable and therefore unanswered.
    assert result.claims == ()
    # The disclosure names the dependency failure and refuses the "no document exists" reading.
    assert "không tra cứu được tài liệu nội bộ" in result.answer
    assert "không phải vì tài liệu đó không tồn tại" in result.answer
    # The outage is still recorded as an outage, distinct from any evidence verdict (invariant 8).
    assert sink.decision_details()["retrieval_outage_guidance"] is True

@pytest.mark.asyncio
async def test_retrieval_outage_on_a_wholly_company_specific_turn_is_unchanged(db_session) -> None:
    """STRICT_INTERNAL means every sub-need needs internal evidence, so there is nothing left to
    answer -- this path must stay exactly the terminal `system_error` it always was."""
    user = await _user(db_session, "outage-strict@example.test")
    membership = await _project_membership(db_session, user)
    generator = ScriptedGenerator([])  # must never be called
    service, _sink = _service(
        db_session,
        retriever=_OutageRetriever(),
        generator=generator,
        interpreter=ScriptedTurnInterpreter(
            [_policy_verdict(KnowledgePolicy.STRICT_INTERNAL, "what is our migration command?")]
        ),
    )

    result = await service.ask(
        question="what is our migration command?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )

    assert result.fallback is True
    assert result.fallback_reason == "system_error"
    assert generator.calls == []


@pytest.mark.asyncio
async def test_outage_never_degrades_into_insufficient_evidence(db_session) -> None:
    """Invariant 8 through the BGK §10.3 substitution: when the guidance attempt itself yields
    nothing usable, the reason substituted back must be the OUTAGE, not an evidence verdict."""
    user = await _user(db_session, "outage-empty-guidance@example.test")
    membership = await _project_membership(db_session, user)
    service, _sink = _service(
        db_session,
        retriever=_OutageRetriever(),
        generator=ScriptedGenerator([GenerationFailure(reason="validator_fail", retry_count=0)]),
        interpreter=ScriptedTurnInterpreter(
            [_policy_verdict(KnowledgePolicy.GENERAL_ALLOWED, "how do virtualenvs work here?")]
        ),
    )

    result = await service.ask(
        question="how do virtualenvs work here?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )

    assert result.fallback_reason == "system_error"

@pytest.mark.asyncio
async def test_general_allowed_with_evidence_still_requires_citations_for_the_internal_part(
    db_session,
) -> None:
    """User concern 1, pinned at the level that enforces it: GENERAL_ALLOWED is permission for a
    separately-marked general section, never a relaxation of grounding. The mixed answer keeps a
    citation-anchored claim AND carries the general-knowledge provenance marker."""
    user = await _user(db_session, "mixed-grounding@example.test")
    membership = await _project_membership(db_session, user)
    service, sink = _service(
        db_session,
        retriever=RecordingRetriever([_candidate()]),
        generator=ScriptedGenerator([_mixed_result()]),
        interpreter=ScriptedTurnInterpreter(
            [_policy_verdict(KnowledgePolicy.GENERAL_ALLOWED, "what python version, and why?")]
        ),
    )

    result = await service.ask(
        question="what python version does this repo need, and what are the trade-offs?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )

    assert result.answer_shape == "mixed"
    assert len(result.claims) == 1
    assert len(result.citations) == 1, "only the company-specific claim may carry a citation"
    assert len(result.general_guidance) == 1
    assert "general technical guidance" in result.answer
    assert sink.decision_details()["answer_shape"] == "mixed"

# ---------------------------------------------------------------------------------------------
# 5. A degraded INTERPRETATION must not produce a confident claim about the corpus.
# ---------------------------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("degradation", ["timeout", "malformed"])
async def test_real_degraded_interpretation_stops_before_retrieval(
    db_session, degradation
) -> None:
    """User concern 4, revised by decision 2a (2026-08-27, RC-1).

    Originally this pinned "the turn is still answered as a knowledge question, but the answer
    discloses that its context could not be analysed". Live traces (trace1984 turn 1) showed that
    disclosure is not enough: the interpreter's fail-open verdict is indistinguishable from a real
    one downstream, so a timeout converts whatever the user actually said -- here a meta question
    about the previous answer -- into a retrieval query and then reports a knowledge gap for it.

    The contract now: a degraded interpretation stops before retrieval and returns `system_error`
    (an existing reason -- no new fallback vocabulary, rev. 2 §8; and invariant 8 keeps a dependency
    failure distinct from a knowledge gap) plus the re-ask note. Both retriever and generator must
    be untouched."""
    user = await _user(db_session, "degraded-note@example.test")
    retriever = RecordingRetriever([])
    generator = ScriptedGenerator([])
    provider = _InterpreterProvider(
        "not json" if degradation == "malformed" else "unused",
        delay_seconds=0.05 if degradation == "timeout" else 0.0,
    )
    interpreter = TurnInterpreter(
        provider,
        TurnInterpreterConfig(
            enabled=True,
            shadow=False,
            knowledge_policy_enabled=True,
            timeout_seconds=0.001 if degradation == "timeout" else 6.0,
        ),
    )
    service, sink = _service(
        db_session,
        retriever=retriever,
        generator=generator,
        interpreter=interpreter,
    )
    service.scope_gate = _RecordingScopeGate([True])

    result = await service.ask(
        question="sao lại không có nguồn?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    assert result.fallback_reason == "system_error"
    assert result.error_code == "interpretation_degraded"
    assert "Ralion chưa đọc được câu này" in result.answer
    assert retriever.calls == []
    assert generator.calls == []
    details = sink.decision_details()
    assert details["interpretation_degraded_fallback"] == "system_error"
    assert details["degraded_reask_note"] is True
    assert details["interpreter_error"] is (degradation == "timeout")
    assert details["interpreter_malformed"] is (degradation == "malformed")
    assert details["knowledge_policy"] == "STRICT_INTERNAL"
    assert details["knowledge_policy_degraded"] is True
    assert "knowledge_policy_effective" not in details
    assert "knowledge_policy_source" not in details
    # RC-5: `error_stage` names the stage that actually failed, not generation, which never ran.
    assert sink.snapshots[-1].attributes.get("error_stage") == "turn_interpreter"

@pytest.mark.asyncio
async def test_a_healthy_turn_never_gets_the_degraded_note(db_session) -> None:
    """The note is a disclosure about THIS turn's interpretation, not decoration on every
    fallback -- same reason, same copy path, no note."""
    user = await _user(db_session, "healthy-no-note@example.test")
    service, _sink = _service(
        db_session,
        retriever=RecordingRetriever([]),
        generator=ScriptedGenerator([]),
        interpreter=ScriptedTurnInterpreter(
            [_policy_verdict(KnowledgePolicy.STRICT_INTERNAL, "what is the leave policy?")]
        ),
    )
    service.scope_gate = _RecordingScopeGate([True])

    result = await service.ask(
        question="what is the leave policy?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    assert result.fallback_reason == "no_evidence"
    assert "Ralion chưa đọc được câu này" not in result.answer


@pytest.mark.asyncio
async def test_validator_fail_copy_no_longer_reads_as_a_missing_source(db_session) -> None:
    """Root cause F. The old wording was indistinguishable from `no_evidence`, which is what made
    the reported follow-up ("sao lại không có nguồn?") a fair question in the first place."""
    user = await _user(db_session, "validator-copy@example.test")
    membership = await _project_membership(db_session, user)
    service, _sink = _service(
        db_session,
        retriever=RecordingRetriever([_candidate()]),
        generator=ScriptedGenerator([GenerationFailure(reason="validator_fail", retry_count=1)]),
        interpreter=ScriptedTurnInterpreter(
            [_policy_verdict(KnowledgePolicy.STRICT_INTERNAL, "dự án dùng database gì")]
        ),
    )

    result = await service.ask(
        question="dự án dùng database gì",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )

    assert result.fallback_reason == "validator_fail"
    assert "có tìm thấy tài liệu liên quan" in result.answer
