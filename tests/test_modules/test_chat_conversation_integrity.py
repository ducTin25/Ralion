"""Multi-turn integrity: B-04 (history verification) and B-05 (user assertions) at the service.

Scope note, so these are not read as more than they are: the routing DECISION belongs to a real
`TurnInterpreter` against a real model, and no test with a scripted verdict can prove the model
routes anything correctly -- that is live-eval work (`eval/project_knowledge/`). What these pin is
everything downstream of the verdict: which branch runs, what string retrieval and the guardrail
are handed on the NEXT turn, and what is written to the transcript.
"""

from __future__ import annotations

import pytest

from src.ai.orchestration.conversation_answer import ConversationAnswerGenerator
from src.ai.orchestration.evidence_sufficiency_gate import (
    EvidenceSufficiencyResult,
    EvidenceSufficiencyVerdict,
)
from src.ai.orchestration.social_reply import _REPLIES
from src.ai.orchestration.turn_interpreter import (
    InterpreterRoute,
    InterpreterScope,
    InterpreterVerdict,
    PresentationOverlay,
)
from src.model.enums import DocumentDomain
from src.modules.chat.application.chat_service import ChatResult
from tests.test_modules.test_chat_conversation_intent import ConversationProvider
from tests.test_modules.test_chat_general_knowledge import (
    RecordingRetriever,
    ScriptedEvidenceGate,
    ScriptedGenerator,
    ScriptedTurnInterpreter,
    _candidate,
    _claim_result,
    _project_membership,
    _RecordingScopeGate,
    _service,
    _user,
)


def _verdict(
    route: InterpreterRoute, resolved_question: str, *, errored: bool = False
) -> InterpreterVerdict:
    return InterpreterVerdict(
        scope=InterpreterScope.IN_SCOPE,
        route=route,
        resolved_question=resolved_question,
        presentation=PresentationOverlay(),
        errored=errored,
    )


def _sufficient(count: int) -> ScriptedEvidenceGate:
    return ScriptedEvidenceGate(
        [
            EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False)
            for _ in range(count)
        ]
    )


@pytest.mark.asyncio
async def test_b05_a_user_assertion_never_becomes_the_next_turns_topic(db_session) -> None:
    """The transcript: T1 answered the database question correctly; T2 was the bare assertion
    "Thanos dùng MongoDB nhé"; from T3 on, the answers drifted and then lost the subject entirely.

    Two independent things had to hold for that to stop, and this exercises both:
      * the interpreter resolves an assertion to the corresponding QUESTION (contract, v5 prompt
        -- scripted here, since a scripted verdict is the only way to isolate the plumbing);
      * `build_window` anchors on the SERVER-COMPOSED query persisted for that turn, so what
        reaches the guardrail and the recovery path on T3 carries no trace of the assertion.
    """
    user = await _user(db_session, "integrity-assertion@example.test")
    membership = await _project_membership(db_session, user)
    retriever = RecordingRetriever([_candidate()])
    scope_gate = _RecordingScopeGate([True, True, True])
    interpreter = ScriptedTurnInterpreter(
        [
            _verdict(InterpreterRoute.KNOWLEDGE, "Dự án dùng cơ sở dữ liệu gì?"),
            # The v5 contract: an assertion resolves to the question behind it, never to itself.
            _verdict(InterpreterRoute.KNOWLEDGE, "Thanos dùng cơ sở dữ liệu gì?"),
            # T3 times out. `resolved_question` degrades to the raw utterance and is condensed
            # against the anchors -- the exact path a polluted anchor would leak through.
            _verdict(InterpreterRoute.KNOWLEDGE, "đó là cơ sở dữ liệu gì?", errored=True),
        ]
    )
    service, _sink = _service(
        db_session,
        retriever=retriever,
        generator=ScriptedGenerator([_claim_result(), _claim_result(), _claim_result()]),
        interpreter=interpreter,
        gate=_sufficient(3),
    )
    service.scope_gate = scope_gate

    first = await service.ask(
        question="project này dùng database gì",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )
    await service.ask(
        question="Thanos dùng MongoDB nhé.",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
        conversation_id=first.conversation_id,
    )
    await service.ask(
        question="đó là cơ sở dữ liệu gì?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
        conversation_id=first.conversation_id,
    )

    assert "MongoDB" not in scope_gate.calls[-1]
    assert "MongoDB" not in retriever.calls[-1][0]
    # And the anchor did carry the real subject forward, so this is not "clean because empty".
    assert "cơ sở dữ liệu" in retriever.calls[-1][0]


@pytest.mark.asyncio
async def test_b04_a_history_verification_turn_is_answered_from_the_transcript(db_session) -> None:
    """Live: "Tôi đã nói ở trên rằng team dùng Redis đúng không?" was answered "Được rồi! Bạn còn
    câu hỏi nào khác không?" -- an agreement template for a premise that was never in the
    conversation. Routed CONVERSATION (v5 contract), it is answered from the transcript instead,
    with no retrieval and no template."""
    user = await _user(db_session, "integrity-verification@example.test")
    membership = await _project_membership(db_session, user)
    retriever = RecordingRetriever([_candidate()])
    provider = ConversationProvider(
        ["Trong hội thoại này bạn chưa nhắc tới Redis."]
    )
    interpreter = ScriptedTurnInterpreter(
        [
            _verdict(InterpreterRoute.KNOWLEDGE, "Dự án dùng cơ sở dữ liệu gì?"),
            _verdict(
                InterpreterRoute.CONVERSATION,
                "Người dùng đã nhắc tới Redis trong hội thoại này chưa?",
            ),
        ]
    )
    service, _sink = _service(
        db_session,
        retriever=retriever,
        generator=ScriptedGenerator([_claim_result()]),
        interpreter=interpreter,
        gate=_sufficient(1),
    )
    service.scope_gate = _RecordingScopeGate([True, True])
    service.conversation_answer_generator = ConversationAnswerGenerator(provider)

    first = await service.ask(
        question="project này dùng database gì",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )
    second: ChatResult = await service.ask(
        question="Tôi đã nói ở trên rằng team dùng Redis đúng không?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
        conversation_id=first.conversation_id,
    )

    assert second.fallback is False
    assert "chưa nhắc tới Redis" in second.answer
    # No social template, in any language, for any subtype.
    rendered = {text for templates in _REPLIES.values() for text in templates.values()}
    assert second.answer not in rendered
    # The verification turn ran no retrieval of its own.
    assert len(retriever.calls) == 1
