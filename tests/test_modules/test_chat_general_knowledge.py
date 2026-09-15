"""Service-level execution-path tests for F5_BOUNDED_GENERAL_KNOWLEDGE_SPEC.md (BGK), §15.1.

Same shape as `eval/project_knowledge/conversation_intelligence/test_stateful_fixture.py`'s Suite
A: scripted `TurnInterpreter`/`EvidenceSufficiencyGate`/generator, no live LLM, real `ChatService`
and real DB session -- proves DISPATCH/PERSISTENCE correctness (which branch ran, what was
persisted, what `AnswerGenerator.generate` was actually called with), not real model quality.
That is the live `eval/project_knowledge/general_knowledge/` harness's job (§15.2, `--live`).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.ai.orchestration.answer_generator import (
    ClaimSupport,
    GenerationFailure,
    GenerationSuccess,
    GuidanceKind,
    VerifiedCitation,
    VerifiedClaim,
    VerifiedGuidance,
)
from src.ai.orchestration.evidence_sufficiency_gate import (
    EvidenceSufficiencyResult,
    EvidenceSufficiencyVerdict,
)
from src.ai.orchestration.guidance_validation import GeneralKnowledgeConfig
from src.ai.orchestration.turn_interpreter import (
    InterpreterContext,
    InterpreterRoute,
    InterpreterScope,
    InterpreterVerdict,
    KnowledgePolicy,
    PresentationOverlay,
    TurnInterpreterConfig,
)
from src.ai.retrieval_engine.retrieval_engine import RetrievalFilters, RetrievalResult
from src.core.telemetry import TelemetrySnapshot
from src.model.citation import Citation
from src.model.enums import DocumentDomain, MembershipStatus, ProjectRole, UserStatus
from src.model.project import Project
from src.model.project_membership import ProjectMembership
from src.model.user import User
from src.modules.chat.application.chat_service import FALLBACKS, ChatResult, ChatService


class _CapturingTelemetrySink:
    def __init__(self) -> None:
        self.snapshots: list[TelemetrySnapshot] = []

    async def submit(self, snapshot: TelemetrySnapshot) -> None:
        self.snapshots.append(snapshot)

    def decision_details(self, index: int = -1) -> dict[str, object]:
        return dict(self.snapshots[index].attributes.get("decision_details") or {})


class RecordingRetriever:
    def __init__(
        self,
        results: list[RetrievalResult] | None = None,
        *,
        section_expansion: list[RetrievalResult] | None = None,
    ) -> None:
        self.results = results if results is not None else []
        self.section_expansion = section_expansion
        self.calls: list[tuple[str, RetrievalFilters]] = []
        self.section_expansion_calls: list[list[int]] = []
        self.list_available_topics_calls = 0
        self.load_scoped_chunks_calls = 0
        self.list_catalog_calls = 0

    async def retrieve(self, question: str, *, filters: RetrievalFilters, budget) -> list[RetrievalResult]:
        self.calls.append((question, filters))
        return self.results

    async def list_available_topics(self, filters: RetrievalFilters, *, limit: int = 3) -> list[str]:
        self.list_available_topics_calls += 1
        return []

    async def load_scoped_chunks(self, chunk_ids, *, filters: RetrievalFilters) -> list[RetrievalResult]:
        self.load_scoped_chunks_calls += 1
        by_id = {item.chunk.chunk_id: item for item in self.results}
        return [by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in by_id]

    async def expand_numbered_section(
        self,
        accepted,
        *,
        filters: RetrievalFilters,
        max_sequence_chunks: int,
        max_other_chunks: int,
    ) -> list[RetrievalResult]:
        self.section_expansion_calls.append([item.chunk.chunk_id for item in accepted])
        return self.section_expansion if self.section_expansion is not None else list(accepted)

    async def list_catalog(self, filters: RetrievalFilters, *, limit_per_group: int = 20):
        self.list_catalog_calls += 1
        return []


class ScriptedGenerator:
    """Records every call's `knowledge_policy` kwarg -- the load-bearing assertion for every BGK
    dispatch test -- and returns one scripted result per call, in order."""

    def __init__(self, results: list[GenerationSuccess | GenerationFailure]) -> None:
        self._results = list(results)
        self.calls: list[dict[str, object]] = []

    async def generate(
        self,
        question,
        candidates,
        *,
        history=(),
        budget=None,
        response_length=None,
        response_tone=None,
        answer_language=None,
        response_length_source="user",
        answer_language_source="user",
        knowledge_policy=None,
    ):
        self.calls.append(
            {
                "question": question,
                "candidate_count": len(candidates),
                "candidate_chunk_ids": [item.chunk.chunk_id for item in candidates],
                "knowledge_policy": knowledge_policy,
                "answer_language": answer_language,
                "answer_language_source": answer_language_source,
            }
        )
        return self._results.pop(0)


class ScriptedEvidenceGate:
    def __init__(self, verdicts: list[EvidenceSufficiencyResult]) -> None:
        self._verdicts = list(verdicts)
        self.calls: list[tuple[str, int]] = []

    async def check(self, question: str, accepted: list[RetrievalResult], _budget):
        self.calls.append((question, len(accepted)))
        return self._verdicts.pop(0)


class ScriptedTurnInterpreter:
    def __init__(self, verdicts: list[InterpreterVerdict], *, knowledge_policy_enabled: bool = True) -> None:
        self._verdicts = list(verdicts)
        self.config = TurnInterpreterConfig(
            enabled=True, shadow=False, knowledge_policy_enabled=knowledge_policy_enabled
        )
        self.calls: list[InterpreterContext] = []

    async def interpret(self, context: InterpreterContext, _budget) -> InterpreterVerdict:
        self.calls.append(context)
        return self._verdicts.pop(0)


class _RecordingScopeGate:
    """Records the exact `condensed_query` string it was asked to classify, so a test can assert
    what `_resolve_scope` actually sent -- the raw utterance vs. a Tier 0/1-condensed one."""

    def __init__(self, verdicts: list[bool]) -> None:
        self._verdicts = list(verdicts)
        self.calls: list[str] = []

    async def is_in_scope(
        self, condensed_query, budget, *, subject_name=None, knowledge_domain=None, has_prior_turn=False
    ):
        self.calls.append(condensed_query)
        return self._verdicts.pop(0)


def _verdict(
    route: InterpreterRoute,
    resolved_question: str,
    *,
    knowledge_policy: KnowledgePolicy = KnowledgePolicy.STRICT_INTERNAL,
    scope: InterpreterScope = InterpreterScope.IN_SCOPE,
) -> InterpreterVerdict:
    return InterpreterVerdict(
        scope=scope,
        route=route,
        resolved_question=resolved_question,
        presentation=PresentationOverlay(),
        knowledge_policy=knowledge_policy,
    )


def _candidate(chunk_id: int = 11, content: str = "This repo requires Python 3.11.") -> RetrievalResult:
    return RetrievalResult(
        chunk=SimpleNamespace(
            chunk_id=chunk_id,
            content=content,
            section_path="Setup",
            heading="Setup",
            lexical_identifiers="",
            anchor=None,
        ),
        knowledge_domain=DocumentDomain.PROJECT,
        document_id=1,
        version_id=1,
        dense_score=0.9,
        hybrid_score=0.5,
        document_title="Setup Guide",
    )


async def _user(db_session, email: str) -> User:
    user = User(email=email, display_name=email, status=UserStatus.ACTIVE)
    db_session.add(user)
    await db_session.flush()
    return user


async def _project_membership(db_session, user: User) -> ProjectMembership:
    project = Project(
        key=f"bgk-{user.user_id}",
        name="Ralion",
        created_by_admin_id=user.user_id,
        github_repo="acme/ralion",
        default_branch="main",
    )
    db_session.add(project)
    await db_session.flush()
    membership = ProjectMembership(
        user_id=user.user_id,
        project_id=project.project_id,
        project_role=ProjectRole.ENGINEER,
        status=MembershipStatus.ACTIVE,
        assigned_by_admin_id=user.user_id,
    )
    db_session.add(membership)
    await db_session.commit()
    return membership


def _service(
    db_session,
    *,
    retriever,
    generator,
    interpreter,
    gate=None,
    general_knowledge_config: GeneralKnowledgeConfig | None = None,
) -> tuple[ChatService, _CapturingTelemetrySink]:
    sink = _CapturingTelemetrySink()
    service = ChatService(
        db_session,
        retriever,
        generator,
        evidence_sufficiency_gate=gate,
        turn_interpreter=interpreter,
        telemetry_sink=sink,
        general_knowledge_config=general_knowledge_config or GeneralKnowledgeConfig(enabled=True),
    )
    return service, sink


def _guidance_only_result(text: str = "Run `python -m venv .venv`.") -> GenerationSuccess:
    return GenerationSuccess(
        claims=(),
        retry_count=0,
        guidance=(VerifiedGuidance(text=text, kind=GuidanceKind.INSTRUCTION),),
    )


def _claim_result(chunk_id: int = 11, text: str = "This repo requires Python 3.11.") -> GenerationSuccess:
    citation = VerifiedCitation(
        chunk_id=chunk_id, quote=text, relevance_score=0.9, knowledge_domain=DocumentDomain.PROJECT
    )
    return GenerationSuccess(
        claims=(VerifiedClaim(text, ClaimSupport.DIRECT, (citation,)),), retry_count=0
    )


def _mixed_result() -> GenerationSuccess:
    citation = VerifiedCitation(
        chunk_id=11, quote="Python 3.11", relevance_score=0.9, knowledge_domain=DocumentDomain.PROJECT
    )
    return GenerationSuccess(
        claims=(VerifiedClaim("This repo requires Python 3.11.", ClaimSupport.DIRECT, (citation,)),),
        retry_count=0,
        guidance=(VerifiedGuidance(text="Run `python -m venv .venv`.", kind=GuidanceKind.INSTRUCTION),),
    )


# ---------------------------------------------------------------------------------------------
# §10.1: empty accepted evidence.
# ---------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_general_allowed_empty_evidence_generates_guidance_only(db_session) -> None:
    user = await _user(db_session, "bgk-empty@example.test")
    membership = await _project_membership(db_session, user)
    retriever = RecordingRetriever([])  # RelevanceGate.accept() on [] -> []
    generator = ScriptedGenerator([_guidance_only_result()])
    interpreter = ScriptedTurnInterpreter(
        [_verdict(InterpreterRoute.KNOWLEDGE, "how do I create a virtualenv?", knowledge_policy=KnowledgePolicy.GENERAL_ALLOWED)]
    )
    service, sink = _service(db_session, retriever=retriever, generator=generator, interpreter=interpreter)

    result: ChatResult = await service.ask(
        question="how do I create a virtualenv?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )

    assert result.fallback is False
    assert result.fallback_reason is None
    assert result.answer_shape == "guidance_only"
    assert len(result.general_guidance) == 1
    assert result.claims == ()
    # §10.1: list_available_topics is skipped on this branch.
    assert retriever.list_available_topics_calls == 0
    assert len(retriever.calls) == 1  # _retrieve called exactly once
    assert generator.calls[0]["knowledge_policy"] is KnowledgePolicy.GENERAL_ALLOWED
    assert generator.calls[0]["candidate_count"] == 0
    details = sink.decision_details()
    assert details["answer_shape"] == "guidance_only"
    assert details["knowledge_policy_effective"] == "GENERAL_ALLOWED"


@pytest.mark.asyncio
async def test_strict_internal_empty_evidence_stays_no_evidence_fallback(db_session) -> None:
    """Backward compatibility: an interpreter STRICT_INTERNAL verdict on empty evidence produces
    exactly today's `no_evidence` fallback -- unchanged."""
    user = await _user(db_session, "bgk-strict-empty@example.test")
    membership = await _project_membership(db_session, user)
    retriever = RecordingRetriever([])
    generator = ScriptedGenerator([])  # must never be called
    interpreter = ScriptedTurnInterpreter(
        [_verdict(InterpreterRoute.KNOWLEDGE, "what is the migration command?", knowledge_policy=KnowledgePolicy.STRICT_INTERNAL)]
    )
    service, _sink = _service(db_session, retriever=retriever, generator=generator, interpreter=interpreter)

    result = await service.ask(
        question="what is the migration command?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )

    assert result.fallback is True
    assert result.fallback_reason == "no_evidence"
    assert retriever.list_available_topics_calls == 1
    assert generator.calls == []


@pytest.mark.asyncio
async def test_general_allowed_but_master_switch_disabled_stays_no_evidence_fallback(db_session) -> None:
    """§6.2 DISABLED: `general_knowledge.enabled=False` narrows GENERAL_ALLOWED -> STRICT_INTERNAL
    regardless of what the interpreter proposed -- the one-line rollback."""
    user = await _user(db_session, "bgk-disabled@example.test")
    membership = await _project_membership(db_session, user)
    retriever = RecordingRetriever([])
    generator = ScriptedGenerator([])
    interpreter = ScriptedTurnInterpreter(
        [_verdict(InterpreterRoute.KNOWLEDGE, "how do I create a virtualenv?", knowledge_policy=KnowledgePolicy.GENERAL_ALLOWED)]
    )
    service, _sink = _service(
        db_session,
        retriever=retriever,
        generator=generator,
        interpreter=interpreter,
        general_knowledge_config=GeneralKnowledgeConfig(enabled=False),
    )

    result = await service.ask(
        question="how do I create a virtualenv?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )

    assert result.fallback is True
    assert result.fallback_reason == "no_evidence"
    assert generator.calls == []


# ---------------------------------------------------------------------------------------------
# §10.2: genuine INSUFFICIENT verdict.
# ---------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_insufficient_evidence_general_allowed_drops_evidence_and_generates_guidance(db_session) -> None:
    user = await _user(db_session, "bgk-insufficient@example.test")
    membership = await _project_membership(db_session, user)
    candidate = _candidate()
    retriever = RecordingRetriever([candidate])
    generator = ScriptedGenerator([_guidance_only_result()])
    gate = ScriptedEvidenceGate(
        [EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.INSUFFICIENT, errored=False)]
    )
    interpreter = ScriptedTurnInterpreter(
        [_verdict(InterpreterRoute.KNOWLEDGE, "what does alembic upgrade head do?", knowledge_policy=KnowledgePolicy.GENERAL_ALLOWED)]
    )
    service, sink = _service(
        db_session, retriever=retriever, generator=generator, interpreter=interpreter, gate=gate
    )

    result = await service.ask(
        question="what does alembic upgrade head do?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )

    assert result.fallback is False
    assert result.answer_shape == "guidance_only"
    # §10.2: evidence dropped from generation -- the call that produced the answer saw 0 candidates.
    assert generator.calls[0]["candidate_count"] == 0
    # §10.2: the dropped set is still persisted as shown-not-asserted citations, claim_id=NULL.
    assert len(result.citations) == 1
    assert result.citations[0]["chunk_id"] == candidate.chunk.chunk_id
    stored = (await db_session.execute(Citation.__table__.select())).fetchall()
    assert len(stored) == 1
    assert stored[0].claim_id is None
    details = sink.decision_details()
    assert details["guidance_evidence_state"] == "insufficient_dropped"


@pytest.mark.asyncio
async def test_insufficient_evidence_general_allowed_but_allow_after_insufficient_false(db_session) -> None:
    user = await _user(db_session, "bgk-insufficient-off@example.test")
    membership = await _project_membership(db_session, user)
    retriever = RecordingRetriever([_candidate()])
    generator = ScriptedGenerator([])
    gate = ScriptedEvidenceGate(
        [EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.INSUFFICIENT, errored=False)]
    )
    interpreter = ScriptedTurnInterpreter(
        [_verdict(InterpreterRoute.KNOWLEDGE, "q", knowledge_policy=KnowledgePolicy.GENERAL_ALLOWED)]
    )
    service, _sink = _service(
        db_session,
        retriever=retriever,
        generator=generator,
        interpreter=interpreter,
        gate=gate,
        general_knowledge_config=GeneralKnowledgeConfig(enabled=True, allow_after_insufficient=False),
    )

    result = await service.ask(
        question="q",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )

    assert result.fallback is True
    assert result.fallback_reason == "insufficient_evidence"
    assert generator.calls == []


@pytest.mark.asyncio
async def test_esg_errored_never_rescued_by_bgk(db_session) -> None:
    """§10.2: an `errored` (fail-closed, infra fault) ESG verdict is never rescued by BGK -- stays
    `system_error`, with no guidance."""
    user = await _user(db_session, "bgk-esg-error@example.test")
    membership = await _project_membership(db_session, user)
    retriever = RecordingRetriever([_candidate()])
    generator = ScriptedGenerator([])
    gate = ScriptedEvidenceGate(
        [EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.INSUFFICIENT, errored=True)]
    )
    interpreter = ScriptedTurnInterpreter(
        [_verdict(InterpreterRoute.KNOWLEDGE, "q", knowledge_policy=KnowledgePolicy.GENERAL_ALLOWED)]
    )
    service, _sink = _service(
        db_session, retriever=retriever, generator=generator, interpreter=interpreter, gate=gate
    )

    result = await service.ask(
        question="q",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )

    assert result.fallback is True
    assert result.fallback_reason == "system_error"
    assert generator.calls == []


@pytest.mark.asyncio
async def test_interpreter_errored_condenses_resolved_question_before_scope_gate(db_session) -> None:
    """Live incident, 2026-08-24 (CHANGE_LOG.md): `session_id=768`, `log_id 2604/2605`. When the
    interpreter times out (`errored=True`), `resolved_question` falls back to the raw current
    utterance -- for a contentless follow-up ("Bạn hãy trả lời giúp tôi") that reaches ScopeGate
    as a standalone fragment with no topic signal and gets (correctly, in isolation) rejected
    OUT_OF_SCOPE, even though the conversation is clearly on-topic. Must be Tier 0/1-condensed
    against the conversation's anchor questions (same mechanism `_begin_turn`'s legacy path
    already uses) before it ever reaches `ScopeGate`.

    Amended 2026-08-27 (decision 2a): the condensation property is unchanged and still asserted --
    it operates on `scope_text`, before and independently of the interpreter call -- but the turn
    now ENDS in a safe re-ask instead of being answered as a knowledge question. See
    `test_chat_conversation_boundary.py::test_degraded_interpretation_stops_before_retrieval` for
    the contract itself."""
    user = await _user(db_session, "interpreter-errored@example.test")
    retriever = RecordingRetriever([_candidate()])
    # F5 audit 2026-08-30 (TopicState remediation): the topic anchor `condense()` prepends below
    # is now the turn's own grounded CLAIM text, not its resolved_question -- set turn 1's claim
    # text to the question it answers so this test still isolates condensation mechanics, not the
    # separate subject-vs-claim-text semantics that fix changed.
    generator = ScriptedGenerator(
        [_claim_result(text="Quy định về thiết bị công ty là gì?"), _claim_result()]
    )
    esg = ScriptedEvidenceGate(
        [
            EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False),
            EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False),
        ]
    )
    scope_gate = _RecordingScopeGate([True, True])
    interpreter = ScriptedTurnInterpreter(
        [_verdict(InterpreterRoute.KNOWLEDGE, "Quy định về thiết bị công ty là gì?")]
    )
    service = ChatService(
        db_session,
        retriever,
        generator,
        evidence_sufficiency_gate=esg,
        turn_interpreter=interpreter,
        scope_gate=scope_gate,
    )

    first = await service.ask(
        question="Quy định về thiết bị công ty là gì?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )
    assert first.fallback is False
    assert scope_gate.calls[-1] == "Quy định về thiết bị công ty là gì?"

    # Turn 2: interpreter times out -- same shape `TurnInterpreter.interpret`'s except-branch
    # returns: `resolved_question` is the raw, unresolved current utterance.
    interpreter._verdicts.append(
        InterpreterVerdict(
            scope=InterpreterScope.IN_SCOPE,
            route=InterpreterRoute.KNOWLEDGE,
            resolved_question="Bạn hãy trả lời giúp tôi",
            presentation=PresentationOverlay(),
            errored=True,
        )
    )

    second = await service.ask(
        question="Bạn hãy trả lời giúp tôi",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=first.conversation_id,
    )

    assert scope_gate.calls[-1] == (
        "Quy định về thiết bị công ty là gì? Bạn hãy trả lời giúp tôi"
    )
    # Decision 2a (2026-08-27, RC-1): the turn no longer proceeds as a KNOWLEDGE question. The
    # condensation above still matters -- it is what keeps the guardrail from rejecting an on-topic
    # conversation on a contentless fragment -- but a verdict the interpreter never produced is no
    # longer treated as one. `system_error` because an LLM dependency failed, never a knowledge-gap
    # reason (invariant 8), and no retrieval is attempted.
    assert second.fallback is True
    assert second.fallback_reason == "system_error"
    assert second.error_code == "interpretation_degraded"
    assert len(retriever.calls) == 1  # turn 1 only
    assert len(generator.calls) == 1


@pytest.mark.asyncio
async def test_interpreter_echoed_action_followup_is_condensed_before_scope_gate(db_session) -> None:
    """Regression for the 2026-08-26 production probe.

    The interpreter correctly chose fresh KNOWLEDGE retrieval for a request that asks for
    missing command details, but echoed the raw follow-up as ``resolved_question``.  A successful
    interpreter call must not make ScopeGate lose the conversation topic.
    """
    user = await _user(db_session, "interpreter-echoed-followup@example.test")
    membership = await _project_membership(db_session, user)
    retriever = RecordingRetriever([_candidate()])
    esg = ScriptedEvidenceGate(
        [
            EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False),
            EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False),
        ]
    )
    scope_gate = _RecordingScopeGate([True, True])
    first_question = "Dự án này dùng công nghệ gì và làm thế nào để chạy trên máy local?"
    followup = "Hãy ghi cụ thể từng lệnh tôi cần chạy, theo đúng thứ tự."
    interpreter = ScriptedTurnInterpreter(
        [
            _verdict(InterpreterRoute.KNOWLEDGE, first_question),
            _verdict(InterpreterRoute.KNOWLEDGE, followup),
        ]
    )
    # F5 audit 2026-08-30 (TopicState remediation): the topic anchor `condense()` prepends below
    # is now the turn's own grounded CLAIM text, not its resolved_question -- set turn 1's claim
    # text to `first_question` so this test still isolates condensation mechanics.
    generator = ScriptedGenerator([_claim_result(text=first_question), _claim_result()])
    service = ChatService(
        db_session,
        retriever,
        generator,
        evidence_sufficiency_gate=esg,
        turn_interpreter=interpreter,
        scope_gate=scope_gate,
    )

    first = await service.ask(
        question=first_question,
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )
    assert first.fallback is False

    second = await service.ask(
        question=followup,
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
        conversation_id=first.conversation_id,
    )

    assert scope_gate.calls[-1] == f"{first_question} {followup}"
    assert second.fallback is False


@pytest.mark.asyncio
async def test_first_turn_procedure_expands_numbered_section_before_sufficiency_and_generation(
    db_session,
) -> None:
    user = await _user(db_session, "first-turn-procedure@example.test")
    membership = await _project_membership(db_session, user)
    ranked = [
        _candidate(11, "Local setup overview."),
        _candidate(14, "Copy the environment file."),
        _candidate(15, "Run the server."),
    ]
    ordered_steps = [
        _candidate(21, "Check Python."),
        _candidate(22, "Clone and create the virtual environment."),
        _candidate(23, "Install dependencies."),
        _candidate(24, "Copy the environment file."),
        _candidate(25, "Run the server."),
    ]
    for index, item in enumerate(ordered_steps, start=1):
        item.chunk.section_path = f"Local setup > {index}. Step {index}"
        item.chunk.heading = f"{index}. Step {index}"
    background = _candidate(30, "Tech stack: Python 3.11 and FastAPI.")
    background.chunk.section_path = "README"
    background.chunk.heading = "README"
    retriever = RecordingRetriever(ranked, section_expansion=[*ordered_steps, background])
    generator = ScriptedGenerator([_claim_result(21, "Check Python.")])
    gate = ScriptedEvidenceGate(
        [EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False)]
    )
    question = "Hãy liệt kê chính xác từng lệnh để chạy dự án này trên máy local."
    interpreter = ScriptedTurnInterpreter([_verdict(InterpreterRoute.KNOWLEDGE, question)])
    service, _sink = _service(
        db_session, retriever=retriever, generator=generator, interpreter=interpreter, gate=gate
    )

    result = await service.ask(
        question=question,
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )

    assert result.fallback is False
    assert retriever.section_expansion_calls == [[11, 14, 15]]
    # Completing a numbered section is a deterministic sufficiency signal: do not spend another
    # LLM call re-judging the same ordered evidence set.
    assert gate.calls == []
    assert generator.calls == []
    expected_steps = "\n\n".join(
        f"{item.chunk.heading}\n\n{item.chunk.content}" for item in ordered_steps
    )
    assert result.answer == f"{background.chunk.content}\n\n{expected_steps}"
    assert [item["chunk_id"] for item in result.citations] == [30, 21, 22, 23, 24, 25]


@pytest.mark.asyncio
async def test_test_focused_local_question_keeps_semantic_generator_after_section_expansion(
    db_session,
) -> None:
    user = await _user(db_session, "first-turn-local-tests@example.test")
    membership = await _project_membership(db_session, user)
    ordered_steps = [
        _candidate(21, "Check Python."),
        _candidate(22, "Create the virtual environment."),
        _candidate(23, "Install dependencies."),
        _candidate(24, "Run the server."),
        _candidate(25, "Run tests with `pytest -q`."),
    ]
    for index, item in enumerate(ordered_steps, start=1):
        item.chunk.section_path = f"Local setup > {index}. Step {index}"
        item.chunk.heading = f"{index}. Step {index}"
    ordered_steps[-1].chunk.section_path = "Local setup > 5. Run tests"
    ordered_steps[-1].chunk.heading = "5. Run tests"
    ranked = [ordered_steps[3], ordered_steps[4]]
    retriever = RecordingRetriever(ranked, section_expansion=ordered_steps)
    generator = ScriptedGenerator([_claim_result(25, "Run tests with `pytest -q`.")])
    gate = ScriptedEvidenceGate(
        [EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False)]
    )
    question = "Cách chạy test cho dự án Nasa trên máy local"
    interpreter = ScriptedTurnInterpreter([_verdict(InterpreterRoute.KNOWLEDGE, question)])
    service, _sink = _service(
        db_session, retriever=retriever, generator=generator, interpreter=interpreter, gate=gate
    )

    result = await service.ask(
        question=question,
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )

    assert result.fallback is False
    assert retriever.section_expansion_calls == []
    assert gate.calls == []
    assert generator.calls == []
    assert result.answer == "5. Run tests\n\nRun tests with `pytest -q`."
    assert [item["chunk_id"] for item in result.citations] == [25]


# ---------------------------------------------------------------------------------------------
# §3.5/§12.1: SUFFICIENT/PARTIAL with real evidence -- mixed and internal_only shapes.
# ---------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sufficient_general_allowed_produces_mixed_answer(db_session) -> None:
    user = await _user(db_session, "bgk-mixed@example.test")
    membership = await _project_membership(db_session, user)
    candidate = _candidate()
    retriever = RecordingRetriever([candidate])
    generator = ScriptedGenerator([_mixed_result()])
    gate = ScriptedEvidenceGate(
        [EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False)]
    )
    interpreter = ScriptedTurnInterpreter(
        [
            _verdict(
                InterpreterRoute.KNOWLEDGE,
                "how do I install the Python version this repo requires?",
                knowledge_policy=KnowledgePolicy.GENERAL_ALLOWED,
            )
        ]
    )
    service, sink = _service(
        db_session, retriever=retriever, generator=generator, interpreter=interpreter, gate=gate
    )

    result = await service.ask(
        question="how do I install the Python version this repo requires?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )

    assert result.fallback is False
    assert result.answer_shape == "mixed"
    assert len(result.claims) == 1
    assert len(result.general_guidance) == 1
    assert len(result.citations) == 1  # only the claim's citation -- guidance carries none
    assert generator.calls[0]["candidate_count"] == 1
    transcript = await service.transcript(
        user_id=user.user_id, conversation_id=result.conversation_id
    )
    assert transcript.turns[0].answer_shape == "mixed"
    assert transcript.turns[0].general_guidance == result.general_guidance
    details = sink.decision_details()
    assert details["guidance_evidence_state"] == "sufficient"


@pytest.mark.asyncio
async def test_partial_gated_on_allow_on_partial_false_forces_strict_internal_generation(db_session) -> None:
    """§12.1: PARTIAL + GENERAL_ALLOWED is gated on `allow_on_partial`. When off, the generation
    call itself must receive STRICT_INTERNAL, even though the interpreter proposed GENERAL_ALLOWED."""
    user = await _user(db_session, "bgk-partial-off@example.test")
    membership = await _project_membership(db_session, user)
    candidate = _candidate()
    retriever = RecordingRetriever([candidate])
    generator = ScriptedGenerator([_claim_result()])
    gate = ScriptedEvidenceGate(
        [EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.PARTIAL, errored=False)]
    )
    interpreter = ScriptedTurnInterpreter(
        [_verdict(InterpreterRoute.KNOWLEDGE, "q", knowledge_policy=KnowledgePolicy.GENERAL_ALLOWED)]
    )
    service, _sink = _service(
        db_session,
        retriever=retriever,
        generator=generator,
        interpreter=interpreter,
        gate=gate,
        general_knowledge_config=GeneralKnowledgeConfig(enabled=True, allow_on_partial=False),
    )

    result = await service.ask(
        question="q",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )

    assert result.fallback is False
    assert generator.calls[0]["knowledge_policy"] is KnowledgePolicy.STRICT_INTERNAL


@pytest.mark.asyncio
async def test_partial_allow_on_partial_true_generation_receives_general_allowed(db_session) -> None:
    user = await _user(db_session, "bgk-partial-on@example.test")
    membership = await _project_membership(db_session, user)
    candidate = _candidate()
    retriever = RecordingRetriever([candidate])
    generator = ScriptedGenerator([_mixed_result()])
    gate = ScriptedEvidenceGate(
        [EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.PARTIAL, errored=False)]
    )
    interpreter = ScriptedTurnInterpreter(
        [_verdict(InterpreterRoute.KNOWLEDGE, "q", knowledge_policy=KnowledgePolicy.GENERAL_ALLOWED)]
    )
    service, _sink = _service(
        db_session,
        retriever=retriever,
        generator=generator,
        interpreter=interpreter,
        gate=gate,
        general_knowledge_config=GeneralKnowledgeConfig(enabled=True, allow_on_partial=True),
    )

    result = await service.ask(
        question="q",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )

    assert result.fallback is False
    assert generator.calls[0]["knowledge_policy"] is KnowledgePolicy.GENERAL_ALLOWED
    assert result.answer_shape == "mixed"


# ---------------------------------------------------------------------------------------------
# §6.2 narrowing: POLICY domain, REUSE route, sensitive markers -- all force STRICT_INTERNAL.
# ---------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_policy_domain_forces_strict_internal_even_when_interpreter_says_general_allowed(db_session) -> None:
    user = await _user(db_session, "bgk-policy-domain@example.test")
    retriever = RecordingRetriever([])
    generator = ScriptedGenerator([])
    interpreter = ScriptedTurnInterpreter(
        [_verdict(InterpreterRoute.KNOWLEDGE, "how do I install Python?", knowledge_policy=KnowledgePolicy.GENERAL_ALLOWED)]
    )
    service, sink = _service(db_session, retriever=retriever, generator=generator, interpreter=interpreter)

    result = await service.ask(
        question="how do I install Python?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    assert result.fallback is True
    # F5 audit 2026-08-29, POLICY fallback UX: the STRICT_INTERNAL/FORCED_DOMAIN narrowing itself
    # is unchanged (still asserted below) -- only the fallback COPY changed, from the generic
    # `no_evidence` ("I looked and found nothing") to `general_knowledge_not_available` (states
    # the real reason: POLICY chat does not draw on outside knowledge, so this was never looked up
    # at all). `general_knowledge_blocked_by_domain` is exactly this: `policy_source ==
    # FORCED_DOMAIN` AND the interpreter's raw verdict was GENERAL_ALLOWED.
    assert result.fallback_reason == "general_knowledge_not_available"
    assert generator.calls == []
    assert sink.decision_details()["knowledge_policy_source"] == "forced_domain"


@pytest.mark.asyncio
async def test_policy_general_knowledge_question_gets_domain_explanation_not_insufficient_evidence(
    db_session,
) -> None:
    """F5 live-test audit 2026-08-29: "SOC 2 là gì?" in POLICY chat retrieved candidates (ESG ran
    and said INSUFFICIENT), so it took the `insufficient_evidence` branch, not the empty-
    RelevanceGate `no_evidence` one pinned above -- both must get the same, honest reason. Reads
    as "I looked and found nothing" when Ralion in fact never looks outside company policy for a
    POLICY question, by design (`FORCED_DOMAIN`, unchanged) -- misleading about WHY, not about
    whether an answer exists."""
    user = await _user(db_session, "bgk-policy-soc2@example.test")
    candidate = _candidate()
    retriever = RecordingRetriever([candidate])
    generator = ScriptedGenerator([])
    gate = ScriptedEvidenceGate(
        [EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.INSUFFICIENT, errored=False)]
    )
    interpreter = ScriptedTurnInterpreter(
        [_verdict(InterpreterRoute.KNOWLEDGE, "SOC 2 là gì?", knowledge_policy=KnowledgePolicy.GENERAL_ALLOWED)]
    )
    service, sink = _service(
        db_session, retriever=retriever, generator=generator, interpreter=interpreter, gate=gate
    )

    result = await service.ask(
        question="SOC 2 là gì?", user_id=user.user_id, knowledge_domain=DocumentDomain.POLICY
    )

    assert result.fallback is True
    assert result.fallback_reason == "general_knowledge_not_available"
    assert result.answer.startswith(FALLBACKS["general_knowledge_not_available"])
    assert generator.calls == []
    assert sink.decision_details()["knowledge_policy_source"] == "forced_domain"


@pytest.mark.asyncio
async def test_policy_general_security_question_gets_domain_explanation_not_insufficient_evidence(
    db_session,
) -> None:
    """Same root cause, second confirmed live-test case: a general (not company-specific)
    security question asked inside POLICY chat -- "why are access badges considered a security
    risk generally?" -- must get the same domain-policy explanation, not the generic knowledge-gap
    copy."""
    user = await _user(db_session, "bgk-policy-badge@example.test")
    candidate = _candidate()
    retriever = RecordingRetriever([candidate])
    generator = ScriptedGenerator([])
    gate = ScriptedEvidenceGate(
        [EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.INSUFFICIENT, errored=False)]
    )
    interpreter = ScriptedTurnInterpreter(
        [
            _verdict(
                InterpreterRoute.KNOWLEDGE,
                "why are access badges considered a security risk generally?",
                knowledge_policy=KnowledgePolicy.GENERAL_ALLOWED,
            )
        ]
    )
    service, sink = _service(
        db_session, retriever=retriever, generator=generator, interpreter=interpreter, gate=gate
    )

    result = await service.ask(
        question="why are access badges considered a security risk generally?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    assert result.fallback is True
    assert result.fallback_reason == "general_knowledge_not_available"
    assert generator.calls == []
    assert sink.decision_details()["knowledge_policy_source"] == "forced_domain"


@pytest.mark.asyncio
async def test_policy_ordinary_internal_gap_keeps_insufficient_evidence(db_session) -> None:
    """The negative case, pinned in the same place: an ORDINARY internal POLICY question the
    interpreter itself judged STRICT_INTERNAL (not general-knowledge-shaped) must keep the plain
    `insufficient_evidence` copy -- `general_knowledge_not_available` is never a blanket
    replacement for a genuine POLICY knowledge gap, only for the specific case where the
    interpreter's own verdict was GENERAL_ALLOWED and the domain overrode it."""
    user = await _user(db_session, "bgk-policy-ordinary-gap@example.test")
    candidate = _candidate()
    retriever = RecordingRetriever([candidate])
    generator = ScriptedGenerator([])
    gate = ScriptedEvidenceGate(
        [EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.INSUFFICIENT, errored=False)]
    )
    interpreter = ScriptedTurnInterpreter(
        [
            _verdict(
                InterpreterRoute.KNOWLEDGE,
                "công ty có tuân thủ SOC 2 không?",
                knowledge_policy=KnowledgePolicy.STRICT_INTERNAL,
            )
        ]
    )
    service, sink = _service(
        db_session, retriever=retriever, generator=generator, interpreter=interpreter, gate=gate
    )

    result = await service.ask(
        question="công ty có tuân thủ SOC 2 không?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    assert result.fallback is True
    assert result.fallback_reason == "insufficient_evidence"
    assert sink.decision_details()["knowledge_policy_source"] == "forced_domain"


@pytest.mark.asyncio
async def test_sensitive_marker_forces_strict_internal_on_project_domain(db_session) -> None:
    user = await _user(db_session, "bgk-sensitive@example.test")
    membership = await _project_membership(db_session, user)
    retriever = RecordingRetriever([])
    generator = ScriptedGenerator([])
    interpreter = ScriptedTurnInterpreter(
        [
            _verdict(
                InterpreterRoute.KNOWLEDGE,
                "how do I get VPN access for this project?",
                knowledge_policy=KnowledgePolicy.GENERAL_ALLOWED,
            )
        ]
    )
    service, sink = _service(db_session, retriever=retriever, generator=generator, interpreter=interpreter)

    result = await service.ask(
        question="how do I get VPN access for this project?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )

    assert result.fallback is True
    assert result.fallback_reason == "no_evidence"
    assert generator.calls == []
    assert sink.decision_details()["knowledge_policy_source"] == "forced_sensitive"


# ---------------------------------------------------------------------------------------------
# §10.3: nothing usable survives -> original fallback reason, never a new one.
# ---------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generation_totally_empty_on_no_evidence_branch_falls_back_to_no_evidence(db_session) -> None:
    user = await _user(db_session, "bgk-empty-fail@example.test")
    membership = await _project_membership(db_session, user)
    retriever = RecordingRetriever([])
    generator = ScriptedGenerator([GenerationFailure(reason="validator_fail", retry_count=1)])
    interpreter = ScriptedTurnInterpreter(
        [_verdict(InterpreterRoute.KNOWLEDGE, "q", knowledge_policy=KnowledgePolicy.GENERAL_ALLOWED)]
    )
    service, sink = _service(db_session, retriever=retriever, generator=generator, interpreter=interpreter)

    result = await service.ask(
        question="q",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )

    assert result.fallback is True
    assert result.fallback_reason == "no_evidence"  # never a new "bgk_*" reason (§10.4)
    assert sink.decision_details()["bgk_guidance_empty"] is True


@pytest.mark.asyncio
async def test_generation_totally_empty_on_insufficient_branch_falls_back_to_insufficient_evidence(db_session) -> None:
    user = await _user(db_session, "bgk-insufficient-fail@example.test")
    membership = await _project_membership(db_session, user)
    candidate = _candidate()
    retriever = RecordingRetriever([candidate])
    generator = ScriptedGenerator([GenerationFailure(reason="validator_fail", retry_count=1)])
    gate = ScriptedEvidenceGate(
        [EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.INSUFFICIENT, errored=False)]
    )
    interpreter = ScriptedTurnInterpreter(
        [_verdict(InterpreterRoute.KNOWLEDGE, "q", knowledge_policy=KnowledgePolicy.GENERAL_ALLOWED)]
    )
    service, sink = _service(
        db_session, retriever=retriever, generator=generator, interpreter=interpreter, gate=gate
    )

    result = await service.ask(
        question="q",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )

    assert result.fallback is True
    assert result.fallback_reason == "insufficient_evidence"
    assert len(result.citations) == 1  # the dropped evidence is still shown on the fallback
    assert sink.decision_details()["bgk_guidance_empty"] is True


@pytest.mark.asyncio
async def test_strict_internal_validator_fail_is_never_relabeled(db_session) -> None:
    """Guard against the remap logic firing on a plain STRICT_INTERNAL turn: `validator_fail`
    must stay `validator_fail`, and `bgk_guidance_empty` must never be annotated on a turn BGK
    was not involved in at all."""
    user = await _user(db_session, "bgk-strict-validator-fail@example.test")
    membership = await _project_membership(db_session, user)
    candidate = _candidate()
    retriever = RecordingRetriever([candidate])
    generator = ScriptedGenerator([GenerationFailure(reason="validator_fail", retry_count=1)])
    gate = ScriptedEvidenceGate(
        [EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False)]
    )
    interpreter = ScriptedTurnInterpreter(
        [_verdict(InterpreterRoute.KNOWLEDGE, "q", knowledge_policy=KnowledgePolicy.STRICT_INTERNAL)]
    )
    service, sink = _service(
        db_session, retriever=retriever, generator=generator, interpreter=interpreter, gate=gate
    )

    result = await service.ask(
        question="q",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )

    assert result.fallback is True
    assert result.fallback_reason == "validator_fail"
    assert "bgk_guidance_empty" not in sink.decision_details()


# ---------------------------------------------------------------------------------------------
# REUSE route (§12.2): guidance always disabled, forced via FORCED_ROUTE.
# ---------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reuse_route_forces_strict_internal_even_when_interpreter_says_general_allowed(db_session) -> None:
    user = await _user(db_session, "bgk-reuse@example.test")
    membership = await _project_membership(db_session, user)
    candidate = _candidate()
    retriever = RecordingRetriever([candidate])
    generator = ScriptedGenerator([_claim_result(), _claim_result()])
    gate = ScriptedEvidenceGate(
        [
            EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False),
            EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False),
        ]
    )
    interpreter = ScriptedTurnInterpreter(
        [
            _verdict(InterpreterRoute.KNOWLEDGE, "what does this repo require?", knowledge_policy=KnowledgePolicy.STRICT_INTERNAL),
            _verdict(InterpreterRoute.REUSE, "what does this repo require?", knowledge_policy=KnowledgePolicy.GENERAL_ALLOWED),
        ]
    )
    service, _sink = _service(
        db_session, retriever=retriever, generator=generator, interpreter=interpreter, gate=gate
    )

    first = await service.ask(
        question="what does this repo require?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )
    assert first.fallback is False

    second = await service.ask(
        question="explain that in more detail",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
        conversation_id=first.conversation_id,
    )

    assert second.fallback is False
    assert generator.calls[-1]["knowledge_policy"] is KnowledgePolicy.STRICT_INTERNAL


@pytest.mark.asyncio
async def test_reuse_degrade_to_knowledge_recomputes_policy_for_knowledge_route(db_session) -> None:
    """Live-observed bug, 2026-08-23 (see CHANGE_LOG.md): a guidance_only turn (§10.1) persists
    zero citations by design, so a REUSE follow-up finds nothing to reuse and R4 degrades to a
    fresh KNOWLEDGE turn. `narrow_policy` had already forced STRICT_INTERNAL for the ORIGINAL
    route=REUSE classification (§12.2 FORCED_ROUTE) -- that value must NOT be carried into the
    degraded KNOWLEDGE call, which needs its own policy computed against route=KNOWLEDGE, or BGK
    silently stops working on every follow-up after a guidance_only answer.
    """
    user = await _user(db_session, "bgk-reuse-degrade@example.test")
    membership = await _project_membership(db_session, user)
    retriever = RecordingRetriever([])  # Thanos-style corpus: no evidence for this generic topic
    generator = ScriptedGenerator([_guidance_only_result(), _guidance_only_result("Step 2 detail.")])
    interpreter = ScriptedTurnInterpreter(
        [
            _verdict(
                InterpreterRoute.KNOWLEDGE,
                "Hướng dẫn cài đặt Python 3.11",
                knowledge_policy=KnowledgePolicy.GENERAL_ALLOWED,
            ),
            _verdict(
                InterpreterRoute.REUSE,
                "Hướng dẫn cài đặt Python 3.11",
                knowledge_policy=KnowledgePolicy.GENERAL_ALLOWED,
            ),
        ]
    )
    service, sink = _service(db_session, retriever=retriever, generator=generator, interpreter=interpreter)

    first = await service.ask(
        question="hướng dẫn cài python 3.11",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )
    assert first.fallback is False
    assert first.answer_shape == "guidance_only"

    second = await service.ask(
        question="chi tiết từng bước",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
        conversation_id=first.conversation_id,
    )

    assert second.fallback is False
    assert second.answer_shape == "guidance_only"
    assert generator.calls[-1]["knowledge_policy"] is KnowledgePolicy.GENERAL_ALLOWED
    details = sink.decision_details()
    assert details["reuse_degraded_to_knowledge"] is True
    assert details["knowledge_policy_source"] == "interpreter"


# ---------------------------------------------------------------------------------------------
# F5 audit 2026-08-29, failure 3: a salvaged non-procedural partial answer must disclose, IN THE
# ANSWER TEXT ITSELF, that completeness relative to the original (possibly exhaustive) request is
# unconfirmed -- `answer_status="partially_verified"` alone is backend metadata a user never sees.
# ---------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_incomplete_answer_carries_a_visible_disclosure(db_session) -> None:
    user = await _user(db_session, "task-incomplete@example.test")
    membership = await _project_membership(db_session, user)
    retriever = RecordingRetriever([_candidate()])
    citation = VerifiedCitation(
        chunk_id=11,
        quote="This repo requires Python 3.11.",
        relevance_score=0.9,
        knowledge_domain=DocumentDomain.PROJECT,
    )
    salvaged = GenerationSuccess(
        claims=(VerifiedClaim("Sidecar backs up data.", ClaimSupport.DIRECT, (citation,)),),
        retry_count=1,
        answer_status="partially_verified",
        validator_outcome="degraded",
        task_incomplete=True,
    )
    generator = ScriptedGenerator([salvaged])
    interpreter = ScriptedTurnInterpreter(
        [_verdict(InterpreterRoute.KNOWLEDGE, "Liệt kê đầy đủ các thành phần của dự án")]
    )
    gate = ScriptedEvidenceGate(
        [EvidenceSufficiencyResult(EvidenceSufficiencyVerdict.SUFFICIENT, errored=False)]
    )
    service, _sink = _service(
        db_session, retriever=retriever, generator=generator, interpreter=interpreter, gate=gate
    )

    result = await service.ask(
        question="Liệt kê đầy đủ các thành phần của dự án",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )

    assert result.fallback is False
    assert result.task_incomplete is True
    assert result.answer.startswith("Sidecar backs up data.")
    assert "chưa thể xác nhận đây đã là danh sách đầy đủ" in result.answer
