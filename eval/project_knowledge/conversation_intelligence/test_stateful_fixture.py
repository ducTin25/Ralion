"""F5 Conversation Intelligence implementation spec §14 Phase 0 -- the stateful eval fixture that
gates every later phase (§15's matrix). Every case asserts EXECUTION PATH, not just final-answer
text: `answer_mode`/`resolved_intent`, `retrieval_called`, `reuse_attempted`, `evidence_source`,
`fallback_reason`, `sufficiency_verdict`, and LLM-call counts, read back from the trace snapshot
`ChatService.ask` submits via `_CapturingTelemetrySink` below (the same `decision_details`
telemetry key production observability already reads).

**Scope and an honest measurement caveat (CLAUDE.md's "đo trước khi tuyên bố đã sửa" discipline
-- distinguish "đã đo" from "suy ra"):** this module has NO live LLM and NO live retrieval/DB --
`RetrievalEngine`/`AnswerGenerator`/`EvidenceSufficiencyGate`/`ScopeGate` are all deterministic
fakes returning scripted results, exactly like `tests/test_modules/test_chat_end_to_end.py`. That
makes it a strong, CI-runnable proof of ROUTING and DISPATCH correctness -- the deterministic
regex classifiers (`classify_social`/`_matches_catalog`/`classify_elaboration`) and the
`chat_service.py` branch logic that consumes a gate verdict -- which is most of what §15's
gating rule for Phases 1/2 actually requires (zero false-positive SOCIAL/CATALOG routing, zero
wasted reuse attempts on a topic switch).

It is explicitly NOT a measurement of `EvidenceSufficiencyGate`'s real judge PRECISION on
PARTIAL/AMBIGUOUS evidence (§14 Phase 3's gating rule) -- that requires a live LLM against the
real golden fixture (`eval/project_knowledge/ragas/`'s pattern, `--live`), which this
implementation pass did not have available. `ambiguous_verdict_enabled` stays `false` in
`config/chunking_params.yaml` until that live sweep exists; the AMBIGUOUS-category cases below
construct a scripted judge response to prove the DISPATCH code path is correct, not that a real
judge renders AMBIGUOUS sanely on real evidence.
"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from src.ai.orchestration.answer_generator import (
    ClaimSupport,
    GenerationSuccess,
    VerifiedCitation,
    VerifiedClaim,
)
from src.ai.orchestration.evidence_sufficiency_gate import (
    EvidenceSufficiencyResult,
    EvidenceSufficiencyVerdict,
)
from src.ai.orchestration.personalization import AnswerLanguage
from src.ai.orchestration.social_reply import SocialIntent
from src.ai.orchestration.turn_interpreter import (
    ConversationControl,
    ConversationControlKind,
    InterpreterContext,
    InterpreterRoute,
    InterpreterScope,
    InterpreterVerdict,
    PresentationOverlay,
    TurnInterpreterConfig,
)
from src.ai.retrieval_engine.retrieval_engine import RetrievalFilters, RetrievalResult
from src.core.telemetry import TelemetrySnapshot
from src.model.chat_session import ChatSession
from src.model.enums import DocumentDomain, MembershipStatus, ProjectRole, ResponseLength, UserStatus
from src.model.project import Project
from src.model.project_membership import ProjectMembership
from src.model.user import User
from src.modules.chat.application.chat_service import ChatService


class _CapturingTelemetrySink:
    """Records every `TelemetrySnapshot` `ChatService.ask` submits -- gives direct access to
    `decision_details` and every other trace attribute, without round-tripping through the DB
    row `ImmediateSessionTelemetrySink` writes (unnecessary for this fixture's assertions)."""

    def __init__(self) -> None:
        self.snapshots: list[TelemetrySnapshot] = []

    async def submit(self, snapshot: TelemetrySnapshot) -> None:
        self.snapshots.append(snapshot)

    @property
    def last(self) -> TelemetrySnapshot:
        return self.snapshots[-1]

    def decision_details(self, index: int = -1) -> dict[str, object]:
        return dict(self.snapshots[index].attributes.get("decision_details") or {})


class RecordingRetriever:
    def __init__(self, results: list[RetrievalResult] | None = None) -> None:
        self.results = results if results is not None else [_candidate()]
        self.calls: list[tuple[str, RetrievalFilters]] = []
        self.list_catalog_calls = 0
        self.catalog_groups: list = []

    async def retrieve(self, question: str, *, filters: RetrievalFilters, budget) -> list[RetrievalResult]:
        self.calls.append((question, filters))
        return self.results

    async def list_available_topics(self, filters: RetrievalFilters, *, limit: int = 3) -> list[str]:
        return []

    async def load_scoped_chunks(self, chunk_ids, *, filters: RetrievalFilters) -> list[RetrievalResult]:
        by_id = {item.chunk.chunk_id: item for item in self.results}
        return [by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in by_id]

    async def list_catalog(self, filters: RetrievalFilters, *, limit_per_group: int = 20):
        self.list_catalog_calls += 1
        return self.catalog_groups


class FixedGenerator:
    def __init__(self, text: str = "Grounded answer. [1]", *, chunk_id: int = 11) -> None:
        self.text = text
        self.chunk_id = chunk_id
        self.calls = 0

    async def generate(
        self,
        _question,
        _candidates,
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
        self.calls += 1
        # A real citation, not an empty tuple: `_reused_related_evidence` (spec §7.3 item 2) reuses
        # a successful turn's evidence via its persisted `Citation` rows, so a fake generator with
        # no citations would make every "reuse after success" case look like reuse never happened.
        citation = VerifiedCitation(
            chunk_id=self.chunk_id,
            quote=self.text,
            relevance_score=0.9,
            knowledge_domain=DocumentDomain.POLICY,
        )
        return GenerationSuccess(
            claims=(VerifiedClaim(self.text, ClaimSupport.DIRECT, (citation,)),), retry_count=0
        )


class ScriptedEvidenceGate:
    """One scripted verdict per call, in order -- lets a case drive a specific judge response
    without needing a live LLM (see module docstring's measurement caveat)."""

    def __init__(self, verdicts: list[EvidenceSufficiencyResult]) -> None:
        self._verdicts = list(verdicts)
        self.calls: list[tuple[str, int]] = []

    async def check(self, question: str, accepted: list[RetrievalResult], _budget):
        self.calls.append((question, len(accepted)))
        return self._verdicts.pop(0)


class ScriptedTurnInterpreter:
    """Suite A fake for the F5 Semantic Turn Interpreter (rev. 2 §10 Suite A: "scripted
    interpreter, CI, no live LLM"). One scripted `InterpreterVerdict` per call, in order -- same
    shape as `ScriptedEvidenceGate` above. Proves the DISPATCH code honors and constrains the
    four-field contract; real interpreter PRECISION is Suite B's job (`--live`), not this one."""

    def __init__(
        self,
        verdicts: list[InterpreterVerdict],
        *,
        enabled: bool = True,
        shadow: bool = False,
        clarify_enabled: bool = False,
    ) -> None:
        self._verdicts = list(verdicts)
        self.config = TurnInterpreterConfig(enabled=enabled, shadow=shadow, clarify_enabled=clarify_enabled)
        self.calls: list[InterpreterContext] = []

    async def interpret(self, context: InterpreterContext, _budget) -> InterpreterVerdict:
        self.calls.append(context)
        return self._verdicts.pop(0)


def _verdict(
    route: InterpreterRoute,
    resolved_question: str,
    *,
    scope: InterpreterScope = InterpreterScope.IN_SCOPE,
    language: str | None = None,
    detail: str | None = None,
    malformed: bool = False,
    errored: bool = False,
    sanitized: bool = False,
    social_intent: SocialIntent | None = None,
    control: bool = False,
) -> InterpreterVerdict:
    return InterpreterVerdict(
        scope=scope,
        route=route,
        resolved_question=resolved_question,
        presentation=PresentationOverlay(language=language, detail=detail),
        conversation_control=(
            ConversationControl(
                kind=ConversationControlKind.UPDATE_PRESENTATION,
                presentation=PresentationOverlay(language=language, detail=detail),
            )
            if control
            else ConversationControl()
        ),
        malformed=malformed,
        errored=errored,
        sanitized=sanitized,
        social_intent=social_intent,
    )


def _candidate(chunk_id: int = 11, content: str = "Employees receive 12 leave days.") -> RetrievalResult:
    return RetrievalResult(
        chunk=SimpleNamespace(
            chunk_id=chunk_id,
            content=content,
            section_path="Leave",
            heading="Leave",
            lexical_identifiers="",
            anchor=None,
        ),
        knowledge_domain=DocumentDomain.POLICY,
        document_id=1,
        version_id=1,
        dense_score=0.99,
        hybrid_score=0.5,
        document_title="Leave Policy",
    )


async def _user(db_session, email: str) -> User:
    user = User(email=email, display_name=email, status=UserStatus.ACTIVE)
    db_session.add(user)
    await db_session.flush()
    return user


def _service(
    db_session, *, retriever=None, generator=None, gate=None, scope_gate=None, turn_interpreter=None
) -> tuple[ChatService, _CapturingTelemetrySink]:
    sink = _CapturingTelemetrySink()
    service = ChatService(
        db_session,
        retriever or RecordingRetriever(),
        generator or FixedGenerator(),
        evidence_sufficiency_gate=gate,
        scope_gate=scope_gate,
        turn_interpreter=turn_interpreter,
        telemetry_sink=sink,
    )
    return service, sink


# ---------------------------------------------------------------------------------------------
# Category 1: Social -- gratitude/greeting/farewell/acknowledgement/topic-change, plus the
# mixed-turn negative that must fall through to KNOWLEDGE.
# ---------------------------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question",
    [
        "cảm ơn bạn",
        "Xin chào",
        "tạm biệt",
        "ok",
        "hỏi cái khác được không",
        "thank you",
        # 2026-08-22 live-probe regression (CHANGE_LOG.md): the first-pass pattern set matched
        # "cảm ơn bạn" OR "cảm ơn nhiều" but not both modifiers together -- a live run against
        # real THANOS project data showed "cảm ơn bạn nhiều" falling through to KNOWLEDGE and
        # getting answered by the full retrieval pipeline instead of a template reply.
        "cảm ơn bạn nhiều",
        "cảm ơn rất nhiều",
        "oke cảm ơn bạn",
        "hello bạn",
        "bye bye",
        "ừ được rồi",
        "cho mình hỏi cái khác được không",
        "đổi sang chủ đề khác đi",
    ],
)
async def test_social_turn_answers_deterministically_with_zero_retrieval(db_session, question) -> None:
    """resolved_intent=SOCIAL, execution_path=SOCIAL, retrieval_called=false, llm_call_count=0."""
    user = await _user(db_session, f"social-{hash(question)}@example.test")
    retriever = RecordingRetriever()
    generator = FixedGenerator()
    service, sink = _service(db_session, retriever=retriever, generator=generator)

    result = await service.ask(
        question=question, user_id=user.user_id, knowledge_domain=DocumentDomain.POLICY
    )

    assert result.fallback is False
    assert result.answer_status == "verified"
    assert result.citations == ()
    assert len(retriever.calls) == 0  # retrieval_called=false
    assert generator.calls == 0  # llm_call_count=0
    assert sink.decision_details()["answer_mode"] == "SOCIAL"


@pytest.mark.asyncio
async def test_social_mixed_turn_negative_falls_through_to_knowledge(db_session) -> None:
    """Spec §6.1: a social phrase plus a real trailing question must NOT match SOCIAL --
    execution_path=KNOWLEDGE, not SOCIAL."""
    user = await _user(db_session, "social-negative@example.test")
    retriever = RecordingRetriever([_candidate()])
    service, sink = _service(db_session, retriever=retriever)

    result = await service.ask(
        question="cảm ơn, còn VPN thì sao?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    assert sink.decision_details()["answer_mode"] == "KNOWLEDGE"
    assert len(retriever.calls) == 1  # retrieval_called=true -- proves it did NOT short-circuit
    assert result.fallback is False


@pytest.mark.asyncio
async def test_social_phrase_embedded_mid_sentence_is_not_matched(db_session) -> None:
    """2026-08-22 live-probe regression: a top-level `|` inside one alternation string without
    an enclosing group anchors only the FIRST branch to `^` and only the LAST to `$` -- every
    branch in between is unanchored and can match anywhere in the string. Caught for
    TOPIC_CHANGE ("can we talk about something else" matching mid-sentence) before this
    fixture existed; pinned here so the same class of bug can't silently regress."""
    user = await _user(db_session, "social-embedded@example.test")
    retriever = RecordingRetriever([_candidate()])
    service, sink = _service(db_session, retriever=retriever)

    await service.ask(
        question="Trước khi trả lời, can we talk about something else trong project này?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    assert sink.decision_details()["answer_mode"] == "KNOWLEDGE"
    assert len(retriever.calls) == 1


# ---------------------------------------------------------------------------------------------
# Category 3/4: Elaboration (pure) must reuse; a topic-switch follow-up must NOT.
# ---------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pure_elaboration_after_successful_turn_reuses_evidence(db_session) -> None:
    """reuse_attempted=true, evidence_source=reused, zero second retrieval call."""
    user = await _user(db_session, "elaborate-success@example.test")
    candidate = _candidate()
    retriever = RecordingRetriever([candidate])
    gate = ScriptedEvidenceGate(
        [
            EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False),
            EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False),
        ]
    )
    service, sink = _service(db_session, retriever=retriever, gate=gate)

    first = await service.ask(
        question="Chính sách nghỉ phép của công ty là gì?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )
    assert first.fallback is False
    assert len(retriever.calls) == 1

    second = await service.ask(
        question="cho ví dụ",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=first.conversation_id,
    )

    assert second.fallback is False
    assert len(retriever.calls) == 1  # no second retrieval -- evidence_source=reused
    details = sink.decision_details()
    assert details["reuse_attempted"] is True
    assert details["related_evidence_reused"] is True


@pytest.mark.asyncio
async def test_language_switch_reformatting_request_reuses_evidence(db_session) -> None:
    """2026-08-22 live-probe finding: "trả lời bằng tiếng việt thật chi tiết" (a pure language-
    switch/re-presentation request, same category as "cho ví dụ") was NOT recognized by
    `classify_elaboration`, so it fell through to fresh retrieval on a query with no topical
    content of its own -- and the anti-dilution merge from the Tier-1 fix (also 2026-08-22)
    injected unrelated noise chunks that made `EvidenceSufficiencyGate` reject the whole turn as
    INSUFFICIENT, even though the correct evidence from turn 1 fully covered it. Fixed by
    widening `classify_elaboration`'s pattern set -- this pins that the reuse path is taken
    (zero fresh retrieval, so the dilution mechanism never gets a chance to fire at all)."""
    user = await _user(db_session, "language-switch@example.test")
    candidate = _candidate()
    retriever = RecordingRetriever([candidate])
    gate = ScriptedEvidenceGate(
        [
            EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False),
            EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False),
        ]
    )
    service, sink = _service(db_session, retriever=retriever, gate=gate)

    first = await service.ask(
        question="What are the rules for company devices?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )
    assert first.fallback is False
    assert len(retriever.calls) == 1

    second = await service.ask(
        question="trả lời bằng tiếng việt thật chi tiết",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=first.conversation_id,
    )

    assert second.fallback is False
    assert len(retriever.calls) == 1  # no fresh retrieval at all -- dilution never gets a chance
    details = sink.decision_details()
    assert details["reuse_attempted"] is True
    assert details["related_evidence_reused"] is True


@pytest.mark.asyncio
async def test_pure_elaboration_after_insufficient_evidence_reuses_evidence(db_session) -> None:
    """Same contract as above, but the prior turn ended `insufficient_evidence` (claim_id=NULL
    citations) -- spec §7.3 item 2's other trigger."""
    user = await _user(db_session, "elaborate-insufficient@example.test")
    candidate = _candidate()
    retriever = RecordingRetriever([candidate])
    gate = ScriptedEvidenceGate(
        [
            EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.INSUFFICIENT, errored=False),
            EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False),
        ]
    )
    service, sink = _service(db_session, retriever=retriever, gate=gate)

    first = await service.ask(
        question="What is the storage cost per GB?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )
    assert first.fallback_reason == "insufficient_evidence"

    second = await service.ask(
        question="giải thích rõ hơn",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=first.conversation_id,
    )

    assert second.fallback is False
    assert len(retriever.calls) == 1
    assert sink.decision_details()["reuse_attempted"] is True


@pytest.mark.asyncio
async def test_topic_switch_followup_never_attempts_reuse(db_session) -> None:
    """[REV2] core precision requirement: reuse_attempted=false, evidence_source=fresh, and the
    sufficiency gate fires exactly once (the fresh-retrieval call), never twice."""
    user = await _user(db_session, "topic-switch@example.test")
    candidate = _candidate()
    retriever = RecordingRetriever([candidate])
    gate = ScriptedEvidenceGate(
        [
            EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.INSUFFICIENT, errored=False),
            EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False),
        ]
    )
    service, sink = _service(db_session, retriever=retriever, gate=gate)

    first = await service.ask(
        question="What is the storage cost per GB?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )
    assert first.fallback_reason == "insufficient_evidence"
    assert len(gate.calls) == 1

    second = await service.ask(
        question="còn VPN thì sao?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=first.conversation_id,
    )

    details = sink.decision_details()
    assert details["reuse_attempted"] is False
    assert details["related_evidence_reused"] is False
    # A real second (fresh) retrieval happened: 1 (turn 1) + 2 for turn 2 -- the expanded query
    # plus the bare-question anti-dilution retrieve (2026-08-22 fix), since "còn VPN thì sao?" is
    # Tier-1-expanded. Still exactly one MORE sufficiency-gate call below, not a wasted extra one.
    assert len(retriever.calls) == 3
    assert len(gate.calls) == 2
    assert second.fallback is False


# ---------------------------------------------------------------------------------------------
# Category 5: Overview/catalog, plus the embedded-specific-fact negative.
# ---------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_catalog_question_answers_from_metadata_with_zero_retrieval(db_session) -> None:
    from src.ai.retrieval_engine.retrieval_engine import CatalogGroup

    user = await _user(db_session, "catalog@example.test")
    retriever = RecordingRetriever()
    retriever.catalog_groups = [
        CatalogGroup(category="LEAVE", titles=("Leave Policy",)),
        CatalogGroup(category="REMOTE_WORK", titles=("Remote Work Policy",)),
    ]
    generator = FixedGenerator()
    service, sink = _service(db_session, retriever=retriever, generator=generator)

    result = await service.ask(
        question="chính sách công ty gồm những gì",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    assert result.fallback is False
    assert result.citations == ()
    assert "Leave Policy" in result.answer and "Remote Work Policy" in result.answer
    assert len(retriever.calls) == 0  # retrieval_called=false
    assert generator.calls == 0  # llm_call_count=0
    assert retriever.list_catalog_calls == 1
    assert sink.decision_details()["answer_mode"] == "CATALOG"


@pytest.mark.asyncio
async def test_catalog_negative_with_embedded_specific_fact_routes_knowledge(db_session) -> None:
    """Spec §8.3: a trailing clause naming a specific fact breaks the anchor -- must fall through
    to KNOWLEDGE, handled by the evidence-sufficiency verdict, not the catalog path."""
    user = await _user(db_session, "catalog-negative@example.test")
    retriever = RecordingRetriever([_candidate()])
    service, sink = _service(db_session, retriever=retriever)

    result = await service.ask(
        question="chính sách công ty gồm những gì, đặc biệt là điều khoản nghỉ phép",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    assert sink.decision_details()["answer_mode"] == "KNOWLEDGE"
    assert retriever.list_catalog_calls == 0
    assert len(retriever.calls) == 1
    assert result.fallback is False


# ---------------------------------------------------------------------------------------------
# Category 6: Ambiguity (constructed; judge behaviour is scripted -- see module docstring's
# measurement caveat). Proves the DISPATCH code, not real judge precision.
# ---------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ambiguous_verdict_asks_for_clarification_when_enabled(db_session) -> None:
    user = await _user(db_session, "ambiguous@example.test")
    candidate = _candidate()
    retriever = RecordingRetriever([candidate])
    gate = ScriptedEvidenceGate(
        [EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.AMBIGUOUS, errored=False)]
    )
    service, sink = _service(db_session, retriever=retriever, gate=gate)

    result = await service.ask(
        question="What is the policy on leave?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    assert result.fallback is True
    assert result.fallback_reason == "ambiguous_question"
    assert "không tìm thấy nguồn" not in result.answer  # never worded like no_evidence
    assert "PM của project" not in result.answer  # POLICY domain -> HR referral, not PM
    assert "đội HR" in result.answer
    assert sink.decision_details()["evidence_sufficiency_gate_verdict"] == "AMBIGUOUS"


@pytest.mark.asyncio
async def test_ambiguous_verdict_coerced_to_insufficient_by_default_config(db_session) -> None:
    """The shipped default (`ambiguous_verdict_enabled=false`) must behave exactly as
    `insufficient_evidence` today -- proves the config-gated deferral end-to-end, not just at the
    gate-module level (already covered by `tests/test_ai/test_evidence_sufficiency_gate.py`)."""
    from src.ai.orchestration.evidence_sufficiency_gate import (
        EvidenceSufficiencyGate,
        EvidenceSufficiencyGateConfig,
    )

    class _AmbiguousProvider:
        async def complete(self, _messages, _budget, _operation):
            return SimpleNamespace(content='{"verdict": "AMBIGUOUS", "supporting_chunk_ids": []}')

    user = await _user(db_session, "ambiguous-default@example.test")
    retriever = RecordingRetriever([_candidate()])
    gate = EvidenceSufficiencyGate(_AmbiguousProvider(), EvidenceSufficiencyGateConfig.from_config())
    service, sink = _service(db_session, retriever=retriever, gate=gate)

    result = await service.ask(
        question="What is the policy on leave?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    assert result.fallback_reason == "insufficient_evidence"
    assert sink.decision_details()["evidence_sufficiency_gate_verdict"] == "INSUFFICIENT"


# ---------------------------------------------------------------------------------------------
# Category 7/8: Partial evidence / composite -- PARTIAL verdict, correctly-worded honesty note,
# answer_status="verified" (never "partially_verified" -- spec §9.4).
# ---------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_partial_verdict_appends_honesty_note_and_keeps_verified_status(db_session) -> None:
    user = await _user(db_session, "partial@example.test")
    candidate = _candidate()
    retriever = RecordingRetriever([candidate])
    generator = FixedGenerator("Employees receive 12 leave days. [1]")
    gate = ScriptedEvidenceGate(
        [EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.PARTIAL, errored=False)]
    )
    service, sink = _service(db_session, retriever=retriever, generator=generator, gate=gate)

    result = await service.ask(
        question="What is the leave and remote-work policy?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    assert result.fallback is False
    # partial_note_wording_family: "haven't found enough yet" framing, never "not documented".
    assert "chưa tìm đủ thông tin" in result.answer
    assert "chưa được tài liệu hoá" not in result.answer
    assert "not documented" not in result.answer.lower()
    assert "đội HR" in result.answer
    # answer_status_matches_claim_quality_only (§9.4): PARTIAL coverage never becomes
    # "partially_verified" -- that value means something else (claim-validation quality).
    assert result.answer_status == "verified"
    assert sink.decision_details()["evidence_sufficiency_gate_verdict"] == "PARTIAL"


# ---------------------------------------------------------------------------------------------
# Regression: a normal knowledge question and a normal coreference follow-up must be unaffected.
# ---------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_normal_knowledge_question_is_unaffected_by_the_new_routing(db_session) -> None:
    user = await _user(db_session, "regression-knowledge@example.test")
    retriever = RecordingRetriever([_candidate()])
    generator = FixedGenerator()
    service, sink = _service(db_session, retriever=retriever, generator=generator)

    result = await service.ask(
        question="What is the remote work policy?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    assert result.fallback is False
    assert generator.calls == 1
    assert len(retriever.calls) == 1
    assert sink.decision_details()["answer_mode"] == "KNOWLEDGE"


# ---------------------------------------------------------------------------------------------
# 2026-08-22 live-probe follow-up: two residual bugs found by testing against real
# Postgres/BGE-M3/OpenAI with the THANOS project fixture. Both fixed; pinned here with fakes so
# the fix holds without needing live infra to verify on every run.
# ---------------------------------------------------------------------------------------------


class SequencedTopicRetriever:
    """Returns one scripted candidate LIST per call, in order. Used to simulate the real
    embedding behavior observed live: an expanded (Tier-1) query dominated by the anchor's own
    richer text surfaces the PRIOR topic's document, while the bare follow-up question on its
    own surfaces the CORRECT, new-topic document."""

    def __init__(self, sequence: list[list[RetrievalResult]]) -> None:
        self._sequence = list(sequence)
        self.calls: list[str] = []

    async def retrieve(self, question: str, *, filters: RetrievalFilters, budget) -> list[RetrievalResult]:
        self.calls.append(question)
        return self._sequence.pop(0)

    async def list_available_topics(self, filters: RetrievalFilters, *, limit: int = 3) -> list[str]:
        return []

    async def load_scoped_chunks(self, chunk_ids, *, filters: RetrievalFilters) -> list[RetrievalResult]:
        return []


class EchoAllChunksGenerator:
    """Cites every candidate it receives -- lets a test prove which chunks actually reached
    generation (i.e. survived RelevanceGate), not just how many retrieval calls happened."""

    def __init__(self) -> None:
        self.calls = 0
        self.received_chunk_ids: list[list[int]] = []

    async def generate(
        self,
        _question,
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
        self.calls += 1
        self.received_chunk_ids.append([item.chunk.chunk_id for item in candidates])
        citations = tuple(
            VerifiedCitation(
                chunk_id=item.chunk.chunk_id,
                quote="quote",
                relevance_score=item.dense_score or 0.9,
                knowledge_domain=item.knowledge_domain,
            )
            for item in candidates
        )
        return GenerationSuccess(
            claims=(VerifiedClaim("answer", ClaimSupport.DIRECT, citations),), retry_count=0
        )


@pytest.mark.asyncio
async def test_topic_switch_anti_dilution_merges_standalone_retrieval(db_session) -> None:
    """Bug #1 root cause: Tier-1 expansion prepends the anchor question(s) before embedding, so
    a short topic-switch follow-up's own new topic can be diluted/outweighed by the anchor's
    longer text, and the WRONG document can pass RelevanceGate (scored against the ORIGINAL
    question, which may still be topically adjacent enough to pass). Fix: also retrieve on the
    bare question and merge -- proven here by a retriever that returns the OLD-topic chunk for
    the expanded query and the CORRECT chunk for the bare query; the final accepted/cited set
    must contain both, not just the anchor-biased one."""
    user = await _user(db_session, "anti-dilution@example.test")
    old_topic_chunk = replace(_candidate(chunk_id=11), dense_score=0.55, document_title="Coding Style Guide")
    new_topic_chunk = replace(_candidate(chunk_id=22), dense_score=0.85, document_title="Contributing")
    retriever = SequencedTopicRetriever(
        [
            [old_topic_chunk],  # turn 1: standalone retrieval
            [old_topic_chunk],  # turn 2: the EXPANDED-query retrieval (anchor-biased)
            [new_topic_chunk],  # turn 2: the bare-question retrieval (anti-dilution fix)
        ]
    )
    generator = EchoAllChunksGenerator()
    service, _sink = _service(db_session, retriever=retriever, generator=generator)

    first = await service.ask(
        question="Coding style guide của dự án này nói gì?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )
    assert first.fallback is False
    assert len(retriever.calls) == 1

    second = await service.ask(
        question="còn cách chạy test thì sao?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=first.conversation_id,
    )

    assert second.fallback is False
    assert len(retriever.calls) == 3  # 1 (turn1) + 2 (turn2: expanded + bare-question merge)
    # The bare question must be exactly the ORIGINAL follow-up, not further modified.
    assert retriever.calls[2] == "còn cách chạy test thì sao?"
    # The correct, new-topic chunk must have reached generation -- proves the merge, not just
    # that a second retrieval call happened.
    assert 22 in generator.received_chunk_ids[-1]
    assert any(c["chunk_id"] == 22 for c in second.citations)


@pytest.mark.asyncio
async def test_standalone_question_does_not_trigger_the_extra_retrieval(db_session) -> None:
    """The anti-dilution fix must only fire when Tier-1 expansion actually happened -- a
    first-turn (standalone) question must still cost exactly one retrieval call, unchanged."""
    user = await _user(db_session, "standalone-unaffected@example.test")
    retriever = RecordingRetriever([_candidate()])
    service, _sink = _service(db_session, retriever=retriever)

    result = await service.ask(
        question="What is the remote work policy?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    assert result.fallback is False
    assert len(retriever.calls) == 1


class _RecordingScopeGate:
    def __init__(self, *, in_scope: bool = True) -> None:
        self.calls: list[tuple[str, str | None, object | None]] = []
        self._in_scope = in_scope

    async def is_in_scope(
        self, condensed_query: str, _budget, *, subject_name: str | None = None, knowledge_domain=None
    ) -> bool:
        self.calls.append((condensed_query, subject_name, knowledge_domain))
        return self._in_scope


@pytest.mark.asyncio
async def test_scope_gate_receives_the_real_project_name_for_project_domain(db_session) -> None:
    """Bug #2 root cause: `ScopeGate`'s judge was never told the project's actual name, so a
    bare proper noun/document title in the question (e.g. the project's own name, or a real
    document title like "Convention #22") had nothing to anchor it to "this project" and the
    judge fell back to its own world-knowledge prior -- reproduced live and fixed by threading
    the real `Project.name` in as trusted context. This pins that the name is actually threaded
    through for a PROJECT-domain turn."""
    user = await _user(db_session, "scope-subject@example.test")
    project = Project(
        key="thanos-fixture",
        name="Thanos",
        created_by_admin_id=user.user_id,
        github_repo="thanos-io/thanos",
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

    retriever = RecordingRetriever([_candidate()])
    scope_gate = _RecordingScopeGate(in_scope=True)
    sink = _CapturingTelemetrySink()
    service = ChatService(
        db_session, retriever, FixedGenerator(), scope_gate=scope_gate, telemetry_sink=sink
    )

    result = await service.ask(
        question="Thanos là gì?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )

    assert result.fallback is False
    assert len(scope_gate.calls) == 1
    _condensed_query, subject_name, knowledge_domain = scope_gate.calls[0]
    assert subject_name == "Thanos"
    assert knowledge_domain is DocumentDomain.PROJECT


@pytest.mark.asyncio
async def test_scope_gate_gets_policy_domain_but_no_subject_name_for_policy_chats(db_session) -> None:
    """POLICY chats have no project/membership, so `subject_name` stays `None` -- but
    `knowledge_domain` IS threaded through (second live-probe finding: "how does annual leave
    work?" false-rejected without it -- see scope_gate.py's `_POLICY_CONTEXT`)."""
    user = await _user(db_session, "scope-subject-policy@example.test")
    retriever = RecordingRetriever([_candidate()])
    scope_gate = _RecordingScopeGate(in_scope=True)
    service = ChatService(db_session, retriever, FixedGenerator(), scope_gate=scope_gate)

    result = await service.ask(
        question="What is the leave policy?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    assert result.fallback is False
    assert len(scope_gate.calls) == 1
    _condensed_query, subject_name, knowledge_domain = scope_gate.calls[0]
    assert subject_name is None
    assert knowledge_domain is DocumentDomain.POLICY


# ---------------------------------------------------------------------------------------------
# F5 Semantic Turn Interpreter (F5_SEMANTIC_TURN_INTERPRETER_REVIEW.md rev. 2). §7.4 bug 1
# regression (legacy path, no interpreter involved), Phase 1 shadow mode, and Phase 2 Suite A
# dispatch cases -- scripted interpreter, no live LLM (see module docstring's measurement
# caveat: this proves DISPATCH correctness, not real interpreter precision -- that is Suite B,
# `--live`, gated behind rev. 2 §10's acceptance criteria).
# ---------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reuse_survives_an_intervening_social_turn(db_session) -> None:
    """§7.4 bug 1 fix / rev. 2 R2: `cảm ơn` persists a citation-less SOCIAL reply between the
    grounded turn and the elaboration request. `_find_reusable_evidence` must walk back PAST it
    to the turn that actually left evidence, not stop at strict turn_index-1 adjacency -- this is
    exactly Suite B case 8 (`cảm ơn` then `giải thích lại...`, two turns), and was broken in
    `main` before this fix (the sequence fell through to fresh retrieval on a bare elaboration
    phrase, which would `no_evidence`)."""
    user = await _user(db_session, "reuse-across-social@example.test")
    candidate = _candidate()
    retriever = RecordingRetriever([candidate])
    gate = ScriptedEvidenceGate(
        [
            EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False),
            EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False),
        ]
    )
    service, sink = _service(db_session, retriever=retriever, gate=gate)

    first = await service.ask(
        question="Chính sách nghỉ phép của công ty là gì?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )
    assert first.fallback is False

    social = await service.ask(
        question="cảm ơn bạn",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=first.conversation_id,
    )
    assert sink.decision_details()["answer_mode"] == "SOCIAL"
    assert social.citations == ()

    third = await service.ask(
        question="giải thích rõ hơn",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=first.conversation_id,
    )

    assert third.fallback is False
    assert len(retriever.calls) == 1  # no fresh retrieval -- reused turn 1's evidence
    details = sink.decision_details()
    assert details["reuse_attempted"] is True
    assert details["related_evidence_reused"] is True


@pytest.mark.asyncio
async def test_shadow_mode_runs_interpreter_and_logs_without_changing_behavior(db_session) -> None:
    """Phase 1 (rev. 2 §11): the interpreter runs and logs alongside the regex routing, and
    changes NOTHING -- proven here with a shadow verdict that strongly disagrees with the legacy
    route (CONVERSATION vs. the legacy KNOWLEDGE decision): the legacy answer must still win."""
    user = await _user(db_session, "shadow@example.test")
    retriever = RecordingRetriever([_candidate()])
    generator = FixedGenerator()
    gate = ScriptedEvidenceGate(
        [EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False)]
    )
    interpreter = ScriptedTurnInterpreter(
        [_verdict(InterpreterRoute.CONVERSATION, "irrelevant -- shadow mode never acts on this")],
        enabled=False,
        shadow=True,
    )
    service, sink = _service(
        db_session, retriever=retriever, generator=generator, gate=gate, turn_interpreter=interpreter
    )

    result = await service.ask(
        question="What is the remote work policy?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    assert result.fallback is False
    assert generator.calls == 1
    assert len(retriever.calls) == 1
    assert len(interpreter.calls) == 1  # it ran...
    details = sink.decision_details()
    assert details["answer_mode"] == "KNOWLEDGE"  # ...but never overrode the legacy route
    assert details["shadow_interpreter_route"] == "CONVERSATION"
    assert details["shadow_interpreter_agrees_with_legacy"] is False


@pytest.mark.asyncio
async def test_phase2_knowledge_route_retrieves_and_gates_on_resolved_question(db_session) -> None:
    """Phase 2 (§3 step 6 KNOWLEDGE branch): retrieval and RelevanceGate run on
    `resolved_question`, never the raw ambiguous follow-up -- the fix for the exact case rev. 2
    §2.2 names (three different representations of one utterance collapsing to one)."""
    user = await _user(db_session, "phase2-knowledge@example.test")
    retriever = RecordingRetriever([_candidate()])
    generator = FixedGenerator()
    gate = ScriptedEvidenceGate(
        [EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False)]
    )
    interpreter = ScriptedTurnInterpreter(
        [_verdict(InterpreterRoute.KNOWLEDGE, "Chính sách nghỉ phép của công ty")]
    )
    service, sink = _service(
        db_session, retriever=retriever, generator=generator, gate=gate, turn_interpreter=interpreter
    )

    result = await service.ask(
        question="còn nghỉ phép thì sao?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    assert result.fallback is False
    assert retriever.calls[0][0] == "Chính sách nghỉ phép của công ty"
    assert sink.decision_details()["interpreter_route"] == "KNOWLEDGE"


@pytest.mark.asyncio
async def test_phase2_reuse_route_generates_from_reused_evidence_when_sufficient(db_session) -> None:
    """Rev. 2 R1/R6: SUFFICIENT reused evidence -> generate from it directly, zero fresh
    retrieval, and grounding stays real (real citations, unchanged claim validation)."""
    user = await _user(db_session, "phase2-reuse@example.test")
    retriever = RecordingRetriever([_candidate()])
    generator = FixedGenerator()
    gate = ScriptedEvidenceGate(
        [
            EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False),
            EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False),
        ]
    )
    interpreter = ScriptedTurnInterpreter(
        [
            _verdict(InterpreterRoute.KNOWLEDGE, "Chính sách thiết bị công ty"),
            _verdict(InterpreterRoute.REUSE, "Chính sách thiết bị công ty"),
        ]
    )
    service, sink = _service(
        db_session, retriever=retriever, generator=generator, gate=gate, turn_interpreter=interpreter
    )

    first = await service.ask(
        question="Chính sách thiết bị công ty là gì?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )
    assert first.fallback is False
    assert len(retriever.calls) == 1

    second = await service.ask(
        question="giải thích kỹ hơn phần trên",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=first.conversation_id,
    )

    assert second.fallback is False
    assert len(retriever.calls) == 1  # no fresh retrieval -- reused
    details = sink.decision_details()
    assert details["evidence_source"] == "reused"
    assert second.citations != ()


class _ReuseRecoveryRetriever:
    """Serves two distinct needs of a REUSE recovery turn with different answers: `load_scoped_
    chunks` must still return the OLD cited chunk (what R2/R3 reloads), while `.retrieve()` (the
    R5 recovery call) must return a DIFFERENT, narrower-topic chunk -- proving the recovery ran
    a real fresh retrieval on `resolved_question`, not a replay of the stale evidence."""

    def __init__(self, *, standalone_result, scoped_result, recovery_result) -> None:
        self.standalone_result = standalone_result
        self.scoped_result = scoped_result
        self.recovery_result = recovery_result
        self.calls: list[str] = []

    async def retrieve(self, question, *, filters, budget):
        self.calls.append(question)
        return [self.standalone_result] if len(self.calls) == 1 else [self.recovery_result]

    async def load_scoped_chunks(self, chunk_ids, *, filters):
        by_id = {self.scoped_result.chunk.chunk_id: self.scoped_result}
        return [by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in by_id]

    async def list_available_topics(self, filters, *, limit: int = 3):
        return []

    async def list_catalog(self, filters, *, limit_per_group: int = 20):
        return []


@pytest.mark.asyncio
async def test_phase2_reuse_recovers_once_on_genuine_insufficient(db_session) -> None:
    """Rev. 2 R5: reused evidence judged INSUFFICIENT against `resolved_question` (errored=False)
    -> exactly one recovery retrieval on `resolved_question`, re-ESG, and generation proceeds if
    that recovery succeeds. Annotated `reuse_insufficient_recovered=True` (a required Suite B
    metric, §10)."""
    user = await _user(db_session, "phase2-reuse-recover@example.test")
    old_chunk = _candidate(chunk_id=11, content="Employees receive 12 leave days.")
    new_chunk = replace(_candidate(chunk_id=22), document_title="Remote Wipe Policy")
    retriever = _ReuseRecoveryRetriever(
        standalone_result=old_chunk, scoped_result=old_chunk, recovery_result=new_chunk
    )
    generator = EchoAllChunksGenerator()
    gate = ScriptedEvidenceGate(
        [
            EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False),
            EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.INSUFFICIENT, errored=False),
            EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False),
        ]
    )
    interpreter = ScriptedTurnInterpreter(
        [
            _verdict(InterpreterRoute.KNOWLEDGE, "Chính sách thiết bị công ty"),
            _verdict(InterpreterRoute.REUSE, "Quy định remote wipe với thiết bị công ty"),
        ]
    )
    service, sink = _service(
        db_session, retriever=retriever, generator=generator, gate=gate, turn_interpreter=interpreter
    )

    first = await service.ask(
        question="Chính sách thiết bị công ty là gì?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )
    assert first.fallback is False

    second = await service.ask(
        question="giải thích kỹ hơn phần remote wipe",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=first.conversation_id,
    )

    assert second.fallback is False
    assert len(retriever.calls) == 2  # turn 1's standalone retrieve + the ONE bounded recovery
    assert retriever.calls[1] == "Quy định remote wipe với thiết bị công ty"
    details = sink.decision_details()
    assert details["reuse_insufficient_recovered"] is True
    assert details["evidence_source"] == "reused_then_fresh"
    assert any(citation["chunk_id"] == 22 for citation in second.citations)


@pytest.mark.asyncio
async def test_phase2_reuse_second_insufficient_is_terminal(db_session) -> None:
    """Rev. 2 R5 bound: a SECOND INSUFFICIENT (after the one recovery) is terminal -- no further
    retry, `fallback_reason="insufficient_evidence"`."""
    user = await _user(db_session, "phase2-reuse-terminal@example.test")
    old_chunk = _candidate(chunk_id=11)
    new_chunk = replace(_candidate(chunk_id=22), document_title="Unrelated Topic")
    retriever = _ReuseRecoveryRetriever(
        standalone_result=old_chunk, scoped_result=old_chunk, recovery_result=new_chunk
    )
    generator = EchoAllChunksGenerator()
    gate = ScriptedEvidenceGate(
        [
            EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False),
            EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.INSUFFICIENT, errored=False),
            EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.INSUFFICIENT, errored=False),
        ]
    )
    interpreter = ScriptedTurnInterpreter(
        [
            _verdict(InterpreterRoute.KNOWLEDGE, "Chính sách thiết bị công ty"),
            _verdict(InterpreterRoute.REUSE, "Quy định remote wipe với thiết bị công ty"),
        ]
    )
    service, sink = _service(
        db_session, retriever=retriever, generator=generator, gate=gate, turn_interpreter=interpreter
    )

    first = await service.ask(
        question="Chính sách thiết bị công ty là gì?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )
    assert first.fallback is False

    second = await service.ask(
        question="giải thích kỹ hơn phần remote wipe",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=first.conversation_id,
    )

    assert second.fallback is True
    assert second.fallback_reason == "insufficient_evidence"
    assert sink.decision_details()["reuse_insufficient_recovered"] is True
    assert len(retriever.calls) == 2  # still exactly one recovery attempt, never a second


class _StaleReuseRetriever:
    """`load_scoped_chunks` always returns empty -- every originally-cited chunk has since gone
    out of scope (archived/re-categorised/ACL change), exercising R4's `reloaded == 0` branch."""

    def __init__(self, *, standalone_result, degraded_result) -> None:
        self.standalone_result = standalone_result
        self.degraded_result = degraded_result
        self.calls: list[str] = []

    async def retrieve(self, question, *, filters, budget):
        self.calls.append(question)
        return [self.standalone_result] if len(self.calls) == 1 else [self.degraded_result]

    async def load_scoped_chunks(self, chunk_ids, *, filters):
        return []

    async def list_available_topics(self, filters, *, limit: int = 3):
        return []

    async def list_catalog(self, filters, *, limit_per_group: int = 20):
        return []


@pytest.mark.asyncio
async def test_phase2_reuse_degrades_to_knowledge_using_previous_retrieval_query(db_session) -> None:
    """Rev. 2 R4: `reloaded == 0` -> degrade, don't fail -- rerun retrieval using the PREVIOUS
    turn's persisted `retrieval_query` (never `resolved_question`, per the flow diagram's
    explicit "no extra field" note -- `resolved_question` here is deliberately a poor, presentation-
    only string to prove the degrade path ignores it for retrieval text)."""
    user = await _user(db_session, "phase2-reuse-degrade@example.test")
    old_chunk = _candidate(chunk_id=11)
    fresh_chunk = replace(_candidate(chunk_id=33), document_title="Fresh Doc")
    retriever = _StaleReuseRetriever(standalone_result=old_chunk, degraded_result=fresh_chunk)
    generator = EchoAllChunksGenerator()
    gate = ScriptedEvidenceGate(
        [
            EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False),
            EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False),
        ]
    )
    interpreter = ScriptedTurnInterpreter(
        [
            _verdict(InterpreterRoute.KNOWLEDGE, "Chính sách thiết bị công ty"),
            _verdict(InterpreterRoute.REUSE, "giải thích kỹ hơn"),
        ]
    )
    service, sink = _service(
        db_session, retriever=retriever, generator=generator, gate=gate, turn_interpreter=interpreter
    )

    first = await service.ask(
        question="Chính sách thiết bị công ty là gì?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )
    assert first.fallback is False

    second = await service.ask(
        question="giải thích kỹ hơn",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=first.conversation_id,
    )

    assert second.fallback is False
    assert len(retriever.calls) == 2
    # R4: the PREVIOUS turn's persisted retrieval_query, not the (poorly-resolved) resolved_question.
    assert retriever.calls[1] == "Chính sách thiết bị công ty"
    assert sink.decision_details()["reuse_stale"] is True


@pytest.mark.asyncio
async def test_phase2_conversation_route_rejected_on_first_turn(db_session) -> None:
    """Rev. 2 §8 "No conversation context (turn 1)": a structural check -- REUSE/CONVERSATION
    are rejected by the dispatcher on turn 1 regardless of what the model says."""
    user = await _user(db_session, "phase2-conv-turn1@example.test")
    retriever = RecordingRetriever([_candidate()])
    generator = FixedGenerator()
    gate = ScriptedEvidenceGate(
        [EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False)]
    )
    interpreter = ScriptedTurnInterpreter(
        [_verdict(InterpreterRoute.CONVERSATION, "tôi đã hỏi gì đầu tiên")]
    )
    service, sink = _service(
        db_session, retriever=retriever, generator=generator, gate=gate, turn_interpreter=interpreter
    )

    result = await service.ask(
        question="tôi đã hỏi gì đầu tiên?", user_id=user.user_id, knowledge_domain=DocumentDomain.POLICY
    )

    assert result.fallback is False
    assert generator.calls == 1  # demoted to KNOWLEDGE, not answered from empty/no history
    assert sink.decision_details()["interpreter_route"] == "CONVERSATION"


@pytest.mark.asyncio
async def test_phase2_catalog_route_answers_from_metadata_with_zero_retrieval(db_session) -> None:
    from src.ai.retrieval_engine.retrieval_engine import CatalogGroup

    user = await _user(db_session, "phase2-catalog@example.test")
    retriever = RecordingRetriever()
    retriever.catalog_groups = [CatalogGroup(category="LEAVE", titles=("Leave Policy",))]
    interpreter = ScriptedTurnInterpreter([_verdict(InterpreterRoute.CATALOG, "danh sách tài liệu")])
    service, sink = _service(db_session, retriever=retriever, turn_interpreter=interpreter)

    result = await service.ask(
        question="có những tài liệu nào", user_id=user.user_id, knowledge_domain=DocumentDomain.POLICY
    )

    assert result.fallback is False
    assert "Leave Policy" in result.answer
    assert retriever.list_catalog_calls == 1
    assert len(retriever.calls) == 0


@pytest.mark.asyncio
async def test_phase2_unresolved_social_claim_is_demoted_to_knowledge(db_session) -> None:
    """Defense-in-depth edge case only, post 2026-08-23 fix (CHANGE_LOG.md): a SOCIAL verdict
    with NEITHER a `classify_social` fast-path match NOR a `verdict.social_intent` (which real
    `TurnInterpreter._parse` output never leaves unset for route=SOCIAL -- it fail-safes to
    `SocialIntent.OTHER`) still has to demote to KNOWLEDGE rather than crash on
    `_answer_social_mode`'s assertion. Only a hand-built `ScriptedTurnInterpreter` verdict (as
    here) can produce this shape; see `test_phase2_interpreter_social_intent_renders_natural_reply`
    for the realistic case this test used to (incorrectly) stand in for."""
    user = await _user(db_session, "phase2-social-demote@example.test")
    retriever = RecordingRetriever([_candidate()])
    generator = FixedGenerator()
    gate = ScriptedEvidenceGate(
        [EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False)]
    )
    # Does not match `classify_social`'s closed whole-utterance template set, and `social_intent`
    # is left unset -- the shape a real interpreter verdict for route=SOCIAL cannot produce.
    question = "you're an absolute lifesaver, thank you so much for all of this"
    interpreter = ScriptedTurnInterpreter([_verdict(InterpreterRoute.SOCIAL, question)])
    service, sink = _service(
        db_session, retriever=retriever, generator=generator, gate=gate, turn_interpreter=interpreter
    )

    result = await service.ask(
        question=question, user_id=user.user_id, knowledge_domain=DocumentDomain.POLICY
    )

    assert result.fallback is False
    assert generator.calls == 1


@pytest.mark.asyncio
async def test_phase2_interpreter_social_intent_renders_natural_reply(db_session) -> None:
    """Root-cause regression (CHANGE_LOG.md 2026-08-23): "I'm really happy"/"I'm just sharing my
    feeling" don't match `classify_social`'s closed 5-subtype dictionary, but the interpreter
    correctly judges them SOCIAL (pure small talk, no info request) with `social_intent=OTHER`.
    Before the fix, `chat_service._ask_with_interpreter` unconditionally demoted every
    interpreter-only SOCIAL claim to KNOWLEDGE, so this fell through to retrieval/generation
    instead of a natural reply. Must now terminate as SOCIAL: zero retrieval, zero generation."""
    user = await _user(db_session, "phase2-social-intent@example.test")
    retriever = RecordingRetriever([_candidate()])
    generator = FixedGenerator()
    question = "I'm really happy"
    interpreter = ScriptedTurnInterpreter(
        [_verdict(InterpreterRoute.SOCIAL, question, social_intent=SocialIntent.OTHER)]
    )
    service, sink = _service(
        db_session, retriever=retriever, generator=generator, turn_interpreter=interpreter
    )

    result = await service.ask(
        question=question, user_id=user.user_id, knowledge_domain=DocumentDomain.POLICY
    )

    assert result.fallback is False
    assert len(retriever.calls) == 0
    assert generator.calls == 0
    assert sink.decision_details()["answer_mode"] == "SOCIAL"
    assert sink.decision_details()["social_intent"] == "OTHER"


@pytest.mark.asyncio
async def test_phase2_language_switch_after_a_social_turn_routes_social_not_out_of_scope(
    db_session,
) -> None:
    """Second root-cause regression (CHANGE_LOG.md, reported live after the first SOCIAL fix):
    turn 1 "oke" -> SOCIAL/ACKNOWLEDGEMENT (fast-path `classify_social`, no interpreter call --
    the widened regex from the first fix). Turn 2 "bạn nói tiếng việt đi, mình không hiểu tiếng
    anh" (please just speak Vietnamese) has nothing to REUSE -- the only previous turn was itself
    pure small talk with zero evidence -- so per the `_SYSTEM_INSTRUCTIONS` REUSE-exclusion rule
    added for this fix, a real interpreter must route this SOCIAL, never REUSE. Before the fix,
    REUSE would fire, `_find_reusable_evidence` would find nothing, R4 would degrade to a bare
    KNOWLEDGE turn with no real subject, and `ScopeGate` would correctly (but unhelpfully) reject
    it as out_of_scope -- exactly the live symptom first reported.

    Subtype is LANGUAGE_PREFERENCE, not OTHER (third root-cause regression, reported live again
    after the SOCIAL/REUSE fix landed): a bare OTHER reply is generic filler ("thanks for
    sharing") that ignores the actual request, so this also pins that the response CONFIRMS the
    switch in Vietnamese, using `presentation.language` as the target -- not `_question_language`
    guessed from the request's own (Vietnamese) phrasing, which would happen to look right here
    but is the wrong mechanism (breaks for an English-phrased switch-to-Vietnamese request).

    This pins the DISPATCH side once the interpreter returns the correct verdict (scripted here,
    since no live LLM is available in this suite -- see module docstring's measurement caveat):
    zero retrieval, zero generation, zero `ScopeGate` calls, terminal SOCIAL answer."""
    user = await _user(db_session, "social-then-language-switch@example.test")
    retriever = RecordingRetriever([_candidate()])
    generator = FixedGenerator()
    scope_gate = _RecordingScopeGate(in_scope=True)
    turn2_question = "bạn nói tiếng việt đi, mình không hiểu tiếng anh"
    interpreter = ScriptedTurnInterpreter(
        [
            _verdict(
                InterpreterRoute.SOCIAL,
                turn2_question,
                social_intent=SocialIntent.LANGUAGE_PREFERENCE,
                language="vi",
                control=True,
            )
        ]
    )
    service, sink = _service(
        db_session,
        retriever=retriever,
        generator=generator,
        scope_gate=scope_gate,
        turn_interpreter=interpreter,
    )

    first = await service.ask(question="oke", user_id=user.user_id, knowledge_domain=DocumentDomain.POLICY)
    assert first.fallback is False
    assert sink.decision_details()["answer_mode"] == "SOCIAL"
    assert len(interpreter.calls) == 0  # fast-path `classify_social` handled turn 1 alone

    second = await service.ask(
        question=turn2_question,
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=first.conversation_id,
    )

    assert second.fallback is False
    assert len(retriever.calls) == 0
    assert generator.calls == 0
    assert len(scope_gate.calls) == 1
    assert sink.decision_details()["answer_mode"] == "SOCIAL"
    assert sink.decision_details()["conversation_control"] == "UPDATE_PRESENTATION"
    assert "Việt" in second.answer
    assert "chia sẻ" not in second.answer  # the old OTHER filler reply must not leak through


@pytest.mark.asyncio
async def test_dispatcher_does_not_treat_a_bare_presentation_overlay_as_a_control(
    db_session,
) -> None:
    """A model can populate `presentation.language` from the message's script. Without the new
    discriminator this ambiguous side channel used to become a durable state mutation. It must
    remain a turn overlay and must not be promoted to a conversation control."""
    user = await _user(db_session, "dispatch-override-language@example.test")
    retriever = RecordingRetriever([_candidate()])
    generator = FixedGenerator()
    question = "bạn trả lời tiếng việt đi"
    interpreter = ScriptedTurnInterpreter(
        [_verdict(InterpreterRoute.SOCIAL, question, social_intent=SocialIntent.OTHER, language="vi")]
    )
    service, sink = _service(
        db_session, retriever=retriever, generator=generator, turn_interpreter=interpreter
    )

    result = await service.ask(question=question, user_id=user.user_id, knowledge_domain=DocumentDomain.POLICY)

    assert result.fallback is False
    assert len(retriever.calls) == 0
    assert generator.calls == 0
    assert sink.decision_details()["social_intent"] == "OTHER"
    assert "chia sẻ" in result.answer
    session = (
        await db_session.execute(
            select(ChatSession).where(ChatSession.public_id == result.conversation_id)
        )
    ).scalar_one()
    assert session.preferred_language is None


@pytest.mark.asyncio
async def test_dispatcher_does_not_override_a_fast_path_confirmed_subtype(db_session) -> None:
    """Control for the override above: it must only apply when the SUBTYPE itself came from the
    interpreter (`classify_social` returned None). A `classify_social` fast-path match short-
    circuits before the interpreter is ever called (`_ask_with_interpreter`'s "ONE surviving
    regex" check), so this is really pinning that the override site is unreachable for a fast-
    path turn -- exercised via "oke", which the widened ACKNOWLEDGEMENT regex matches."""
    user = await _user(db_session, "dispatch-no-override-fastpath@example.test")
    retriever = RecordingRetriever([_candidate()])
    generator = FixedGenerator()
    # Never consulted: `classify_social("oke")` matches before the interpreter would run.
    interpreter = ScriptedTurnInterpreter([])
    service, sink = _service(
        db_session, retriever=retriever, generator=generator, turn_interpreter=interpreter
    )

    result = await service.ask(question="oke", user_id=user.user_id, knowledge_domain=DocumentDomain.POLICY)

    assert result.fallback is False
    assert sink.decision_details()["social_intent"] == "ACKNOWLEDGEMENT"
    assert len(interpreter.calls) == 0


@pytest.mark.asyncio
async def test_live_reproduction_language_preference_persists_across_subsequent_turns(
    db_session,
) -> None:
    """Full reproduction of the 2026-08-23 stateful diagnostic's reported conversation (turns 0-4
    of the 6-turn transcript pulled from real `llm_call_logs`/`chat_messages` on the running
    instance, `session_id=763` -- turn 5's malformed-interpreter-output issue is a separate,
    explicitly deferred item and not covered here). Verdicts for turns 0/2/4 (the ones that reach
    the interpreter) are scripted with the EXACT `route`/`resolved_question`/`social_intent`/
    `presentation.language` values captured live, not idealized ones -- this is a regression test
    against the actual observed bug shape, not a hypothetical.

    Asserts the fix end-to-end:
    - turn 2 ("bạn trả lời tiếng việt đi") renders the LANGUAGE_PREFERENCE Vietnamese confirmation
      despite the scripted `social_intent=OTHER` (the dispatcher override), and persists
      `ChatSession.preferred_language="vi"`.
    - turn 3 ("okay", fast-path ACKNOWLEDGEMENT, no interpreter call) now answers in VIETNAMESE
      -- before this fix it answered in English ("Got it!...") because nothing carried the
      preference forward. This is the item 2 regression from the diagnostic report.
    - turn 4 (asking again) still works and does not regress the persisted preference.
    """
    user = await _user(db_session, "live-repro-language-state@example.test")
    retriever = RecordingRetriever([_candidate()])
    generator = FixedGenerator()
    interpreter = ScriptedTurnInterpreter(
        [
            # Turn 0: "không có gì" -- real live verdict, no presentation.language at all.
            _verdict(
                InterpreterRoute.SOCIAL,
                "Không có nội dung yêu cầu thông tin.",
                social_intent=SocialIntent.OTHER,
            ),
            # Turn 2: "bạn trả lời tiếng việt đi" -- real live verdict: OTHER + language="vi".
            _verdict(
                InterpreterRoute.SOCIAL,
                "Yêu cầu trả lời bằng tiếng Việt",
                social_intent=SocialIntent.OTHER,
                language="vi",
                control=True,
            ),
            # Turn 4: "bạn nói tiếng việt đi" -- same shape as turn 2, live verdict repeated.
            _verdict(
                InterpreterRoute.SOCIAL,
                "Yêu cầu trả lời bằng tiếng Việt",
                social_intent=SocialIntent.OTHER,
                language="vi",
                control=True,
            ),
        ]
    )
    service, sink = _service(
        db_session, retriever=retriever, generator=generator, turn_interpreter=interpreter
    )

    turn0 = await service.ask(
        question="không có gì", user_id=user.user_id, knowledge_domain=DocumentDomain.POLICY
    )
    assert turn0.fallback is False
    assert sink.decision_details()["social_intent"] == "OTHER"  # unaffected: no presentation.language

    turn1 = await service.ask(
        question="hi", user_id=user.user_id, knowledge_domain=DocumentDomain.POLICY,
        conversation_id=turn0.conversation_id,
    )
    assert sink.decision_details()["social_intent"] == "GREETING"
    assert "Hi!" in turn1.answer

    turn2 = await service.ask(
        question="bạn trả lời tiếng việt đi",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=turn0.conversation_id,
    )
    assert sink.decision_details()["conversation_control"] == "UPDATE_PRESENTATION"
    assert "Việt" in turn2.answer

    session_row = (
        await db_session.execute(select(ChatSession).where(ChatSession.public_id == turn2.conversation_id))
    ).scalar_one()
    assert session_row.preferred_language == "vi"

    turn3 = await service.ask(
        question="okay",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=turn0.conversation_id,
    )
    assert sink.decision_details()["social_intent"] == "ACKNOWLEDGEMENT"
    assert len(interpreter.calls) == 2  # turn 3 was fast-path "okay" -- interpreter not called again
    assert "Vâng" in turn3.answer  # Vietnamese ACKNOWLEDGEMENT template, not English

    turn4 = await service.ask(
        question="bạn nói tiếng việt đi",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=turn0.conversation_id,
    )
    assert sink.decision_details()["conversation_control"] == "UPDATE_PRESENTATION"
    assert "Việt" in turn4.answer
    assert len(retriever.calls) == 0
    assert generator.calls == 0


class _RejectingScopeGate:
    async def is_in_scope(self, _resolved_question, _budget, *, subject_name=None, knowledge_domain=None):
        return False


@pytest.mark.asyncio
async def test_phase2_out_of_scope_short_circuits_before_route(db_session) -> None:
    """Rev. 2 §7.3: `scope` (via the separate `ScopeGate` call in Phase 2) is checked BEFORE
    dispatching on `route` -- an OUT_OF_SCOPE turn never reaches retrieval regardless of what
    route the interpreter proposed."""
    user = await _user(db_session, "phase2-oos@example.test")
    retriever = RecordingRetriever([_candidate()])
    interpreter = ScriptedTurnInterpreter([_verdict(InterpreterRoute.KNOWLEDGE, "off-topic question")])
    service, sink = _service(
        db_session, retriever=retriever, scope_gate=_RejectingScopeGate(), turn_interpreter=interpreter
    )

    result = await service.ask(
        question="what's a good diet plan?", user_id=user.user_id, knowledge_domain=DocumentDomain.POLICY
    )

    assert result.fallback_reason == "out_of_scope"
    assert len(retriever.calls) == 0


@pytest.mark.asyncio
async def test_phase2_malformed_interpreter_output_stops_before_knowledge(db_session) -> None:
    """A malformed parser result is marked degraded and never becomes a raw-text query."""
    user = await _user(db_session, "phase2-malformed@example.test")
    retriever = RecordingRetriever([_candidate()])
    generator = FixedGenerator()
    gate = ScriptedEvidenceGate(
        [EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False)]
    )
    interpreter = ScriptedTurnInterpreter(
        [_verdict(InterpreterRoute.KNOWLEDGE, "còn VPN thì sao?", malformed=True)]
    )
    service, sink = _service(
        db_session, retriever=retriever, generator=generator, gate=gate, turn_interpreter=interpreter
    )

    result = await service.ask(
        question="còn VPN thì sao?", user_id=user.user_id, knowledge_domain=DocumentDomain.POLICY
    )

    assert result.fallback is True
    assert result.fallback_reason == "system_error"
    assert result.error_code == "interpretation_degraded"
    details = sink.decision_details()
    assert details["interpreter_malformed"] is True
    assert details["knowledge_policy_degraded"] is True
    assert retriever.calls == []
    assert generator.calls == 0


@pytest.mark.asyncio
async def test_phase2_presentation_overlay_reaches_generator_as_turn_local(db_session) -> None:
    """Rev. 2 §7.2(a): a turn-local `presentation` override wins for this turn's generation call
    and is tagged with source="turn" -- distinct from the persisted `user.response_length`
    default (source="user"). No code path on this route ever writes to `User` (§7.2(a): "no write
    to `User` ever happens on this path" -- structurally true here since `_generate_and_persist`
    never touches the `User`/`user_service` module at all)."""
    user = await _user(db_session, "phase2-presentation@example.test")
    retriever = RecordingRetriever([_candidate()])

    class _CapturingGenerator:
        def __init__(self) -> None:
            self.calls: list[tuple] = []

        async def generate(
            self,
            _question,
            _candidates,
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
                (response_length, answer_language, response_length_source, answer_language_source)
            )
            citation = VerifiedCitation(
                chunk_id=11, quote="q", relevance_score=0.9, knowledge_domain=DocumentDomain.POLICY
            )
            return GenerationSuccess(
                claims=(VerifiedClaim("a", ClaimSupport.DIRECT, (citation,)),), retry_count=0
            )

    generator = _CapturingGenerator()
    gate = ScriptedEvidenceGate(
        [EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False)]
    )
    interpreter = ScriptedTurnInterpreter(
        [
            _verdict(
                InterpreterRoute.KNOWLEDGE,
                "Chính sách thiết bị công ty",
                language="en",
                detail="detailed",
            )
        ]
    )
    service, sink = _service(
        db_session, retriever=retriever, generator=generator, gate=gate, turn_interpreter=interpreter
    )

    result = await service.ask(
        question="trả lời chi tiết bằng tiếng anh",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    assert result.fallback is False
    response_length, answer_language, length_source, language_source = generator.calls[0]
    assert response_length == ResponseLength.DETAILED
    assert answer_language == AnswerLanguage.EN
    assert length_source == "turn"
    assert language_source == "turn"


# ---------------------------------------------------------------------------------------------
# 2026-08-27 conversation/orchestration boundary pass. Same execution-path discipline as the rest
# of this fixture (assert the PATH, not answer text): each case below pins that a guardrail
# degrades exactly the capability it guards. Unit-level coverage lives in
# `tests/test_modules/test_chat_conversation_boundary.py`; these are the stateful, multi-turn
# shapes that only a conversation-scoped fixture can express.
# ---------------------------------------------------------------------------------------------


class _SequencedScopeGate:
    """One scripted in/out-of-scope answer per call, in order -- the shape needed to express
    "turn 1 passed the topical gate, turn 2 (a meta question about turn 1) did not"."""

    def __init__(self, answers: list[bool]) -> None:
        self._answers = list(answers)
        self.calls: list[str] = []

    async def is_in_scope(self, condensed_query, _budget, *, subject_name=None, knowledge_domain=None):
        self.calls.append(condensed_query)
        return self._answers.pop(0)

@pytest.mark.asyncio
async def test_meta_turn_about_a_prior_answer_survives_the_topical_scope_gate(db_session) -> None:
    """Failure 1 in the 2026-08-27 report, at the stateful level: turn 1 is answered, turn 2 asks
    about THAT REPLY. `ScopeGate` judges the raw utterance with no project subject in it and
    rejects; the context-aware interpreter reads it as CONVERSATION. Execution path asserted:
    the turn is NOT declined, retrieval is NOT called a second time, and the recovery is
    attributed in telemetry (`scope_recovered_by="conversation"`)."""
    from src.ai.orchestration.conversation_answer import ConversationAnswerGenerator

    class _Provider:
        def __init__(self) -> None:
            self.prompts: list[str] = []

        async def complete(self, messages, _budget, _operation):
            self.prompts.append("\n".join(content for _role, content in messages))
            return SimpleNamespace(content="Ở lượt trước Ralion đã trả lời dựa trên tài liệu nội bộ.")

    user = await _user(db_session, "eval-meta-recovery@example.test")
    retriever = RecordingRetriever([_candidate()])
    gate = ScriptedEvidenceGate(
        [EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False)]
    )
    scope_gate = _SequencedScopeGate([True, False])
    interpreter = ScriptedTurnInterpreter(
        [
            _verdict(InterpreterRoute.KNOWLEDGE, "Chính sách nghỉ phép của công ty"),
            _verdict(InterpreterRoute.CONVERSATION, "vì sao câu trả lời trước lại như vậy"),
        ]
    )
    provider = _Provider()
    service, sink = _service(
        db_session, retriever=retriever, gate=gate, scope_gate=scope_gate, turn_interpreter=interpreter
    )
    service.conversation_answer_generator = ConversationAnswerGenerator(provider)

    first = await service.ask(
        question="Chính sách nghỉ phép của công ty là gì?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )
    assert first.fallback is False
    retrieval_calls_after_turn1 = len(retriever.calls)

    second = await service.ask(
        question="tại sao bạn lại trả lời như vậy?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=first.conversation_id,
    )

    assert second.fallback is False
    assert second.fallback_reason is None
    assert len(retriever.calls) == retrieval_calls_after_turn1  # CONVERSATION reads no corpus
    assert sink.decision_details()["scope_recovered_by"] == "conversation"
    # Provenance travels with the transcript: the prior turn's server-derived outcome is present,
    # so the reply explains the real outcome instead of guessing one.
    assert "OUTCOME of the assistant turn above:" in provider.prompts[-1]

@pytest.mark.asyncio
async def test_language_preference_persists_even_on_a_turn_the_scope_gate_rejects(db_session) -> None:
    """Failure 3 in the report, at the stateful level: the presentation control is trusted state,
    not a reward for passing the topical gate. The turn is still declined (the control is applied,
    NOT the route -- persisting a preference must never authorize retrieval), but the preference
    survives, so the NEXT turn is already Vietnamese."""
    user = await _user(db_session, "eval-lang-through-rejection@example.test")
    retriever = RecordingRetriever([_candidate()])
    generator = FixedGenerator()
    scope_gate = _SequencedScopeGate([False])
    interpreter = ScriptedTurnInterpreter(
        [
            _verdict(
                InterpreterRoute.KNOWLEDGE,
                "yêu cầu trả lời bằng tiếng Việt kèm một câu hỏi ngoài phạm vi",
                language="vi",
                control=True,
            )
        ]
    )
    service, sink = _service(
        db_session,
        retriever=retriever,
        generator=generator,
        scope_gate=scope_gate,
        turn_interpreter=interpreter,
    )

    result = await service.ask(
        question="trả lời tiếng Việt nhé. <off-topic request>",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    assert result.fallback_reason == "out_of_scope"
    assert len(retriever.calls) == 0
    assert generator.calls == 0
    session_row = (
        await db_session.execute(
            select(ChatSession).where(ChatSession.public_id == result.conversation_id)
        )
    ).scalar_one()
    await db_session.refresh(session_row)
    assert session_row.preferred_language == "vi"
    # The rejection itself is unchanged: no recovery was granted to this KNOWLEDGE turn.
    assert "scope_recovered_by" not in sink.decision_details()

@pytest.mark.asyncio
async def test_degraded_interpretation_discloses_itself_without_a_new_fallback_reason(
    db_session,
) -> None:
    """Concern 4 at the stateful level: a timeout stops before retrieval and asks for a rephrase.

    The reason stays inside the existing taxonomy (`system_error`), while telemetry names the
    interpreter stage and its degraded fallback explicitly.
    """
    user = await _user(db_session, "eval-degraded-interpretation@example.test")
    retriever = RecordingRetriever([])
    generator = FixedGenerator()
    interpreter = ScriptedTurnInterpreter(
        [_verdict(InterpreterRoute.KNOWLEDGE, "sao lại không có nguồn?", errored=True)]
    )
    service, sink = _service(
        db_session,
        retriever=retriever,
        generator=generator,
        scope_gate=_SequencedScopeGate([True]),
        turn_interpreter=interpreter,
    )

    result = await service.ask(
        question="sao lại không có nguồn?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    assert result.fallback_reason == "system_error"  # existing reason; no new vocabulary
    assert result.error_code == "interpretation_degraded"
    assert len(retriever.calls) == 0
    assert generator.calls == 0
    assert "Ralion chưa đọc được câu này" in result.answer
    details = sink.decision_details()
    assert details["interpretation_degraded_fallback"] == "system_error"
    assert details["degraded_reask_note"] is True
    assert sink.snapshots[-1].attributes["error_stage"] == "turn_interpreter"
