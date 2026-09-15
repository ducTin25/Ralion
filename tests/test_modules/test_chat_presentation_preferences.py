from __future__ import annotations

import pytest
from sqlalchemy import select

from src.ai.orchestration.evidence_sufficiency_gate import (
    EvidenceSufficiencyResult,
    EvidenceSufficiencyVerdict,
)
from src.ai.orchestration.personalization import AnswerLanguage
from src.ai.orchestration.social_reply import SocialIntent
from src.ai.orchestration.turn_interpreter import (
    ConversationControl,
    ConversationControlApplication,
    ConversationControlKind,
    InterpreterRoute,
    InterpreterScope,
    InterpreterVerdict,
    PresentationOverlay,
)
from src.model.chat_session import ChatSession
from src.model.enums import DocumentDomain, ResponseLength
from src.modules.chat.application.chat_service import (
    _effective_answer_language,
    _effective_response_length,
)
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
    _verdict,
)


def _control(language: str) -> InterpreterVerdict:
    return InterpreterVerdict(
        scope=InterpreterScope.IN_SCOPE,
        route=InterpreterRoute.SOCIAL,
        resolved_question="Update the conversation presentation preference",
        presentation=PresentationOverlay(language=language),
        conversation_control=ConversationControl(
            kind=ConversationControlKind.UPDATE_PRESENTATION,
            presentation=PresentationOverlay(language=language),
        ),
        social_intent=SocialIntent.LANGUAGE_PREFERENCE,
    )


def _knowledge(question: str, *, spurious_language: str | None = None) -> InterpreterVerdict:
    return InterpreterVerdict(
        scope=InterpreterScope.IN_SCOPE,
        route=InterpreterRoute.KNOWLEDGE,
        resolved_question=question,
        # Models have populated this from the current script in production. It must not outrank
        # an explicit conversation control.
        presentation=PresentationOverlay(language=spurious_language),
    )


def _detail_control(detail: str) -> InterpreterVerdict:
    return InterpreterVerdict(
        scope=InterpreterScope.IN_SCOPE,
        route=InterpreterRoute.SOCIAL,
        resolved_question="Update response detail preference",
        presentation=PresentationOverlay(detail=detail),
        conversation_control=ConversationControl(
            kind=ConversationControlKind.UPDATE_PRESENTATION,
            presentation=PresentationOverlay(detail=detail),
        ),
        social_intent=SocialIntent.OTHER,
    )


def _service_for(db_session, verdicts, scope_verdicts):
    service, _ = _service(
        db_session,
        retriever=RecordingRetriever([]),
        generator=ScriptedGenerator([]),
        interpreter=ScriptedTurnInterpreter(list(verdicts)),
    )
    service.scope_gate = _RecordingScopeGate(list(scope_verdicts))
    return service


@pytest.mark.asyncio
async def test_set_vietnamese_then_english_question_still_uses_vietnamese(db_session) -> None:
    user = await _user(db_session, "pref-vi-english-question@example.test")
    service = _service_for(
        db_session,
        [_control("vi"), _knowledge("What is Sidecar?", spurious_language="en")],
        [True, True],
    )

    control = await service.ask(
        question="Từ giờ hãy dùng tiếng Việt để trả lời",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )
    answer = await service.ask(
        question="What is Sidecar?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=control.conversation_id,
    )

    assert answer.fallback_reason == "no_evidence"
    assert answer.answer.startswith("Tôi không tìm thấy")


@pytest.mark.asyncio
async def test_set_english_then_vietnamese_question_still_uses_english(db_session) -> None:
    user = await _user(db_session, "pref-en-vietnamese-question@example.test")
    service = _service_for(
        db_session,
        [_control("en"), _knowledge("Sidecar là gì?", spurious_language="vi")],
        [True, True],
    )

    control = await service.ask(
        question="From now on, reply in English",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )
    answer = await service.ask(
        question="Sidecar là gì?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=control.conversation_id,
    )

    assert answer.fallback_reason == "no_evidence"
    assert answer.answer.startswith("I couldn't find")


@pytest.mark.asyncio
async def test_preference_survives_multiple_turns(db_session) -> None:
    user = await _user(db_session, "pref-multiple-turns@example.test")
    service = _service_for(
        db_session,
        [_control("vi"), _knowledge("First question", spurious_language="en"), _knowledge("Second question", spurious_language="en")],
        [True, True, True],
    )
    first = await service.ask(
        question="Luôn trả lời bằng tiếng Việt",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    for question in ("First question", "Second question"):
        result = await service.ask(
            question=question,
            user_id=user.user_id,
            knowledge_domain=DocumentDomain.POLICY,
            conversation_id=first.conversation_id,
        )
        assert result.answer.startswith("Tôi không tìm thấy")


@pytest.mark.asyncio
async def test_preference_reminder_is_control_ack_not_out_of_scope(db_session) -> None:
    user = await _user(db_session, "pref-reminder@example.test")
    service = _service_for(db_session, [_control("vi"), _control("vi")], [True, False])
    first = await service.ask(
        question="Từ giờ dùng tiếng Việt",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    reminder = await service.ask(
        question="I already told you that you have to use Vietnamese",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=first.conversation_id,
    )

    assert reminder.fallback is False
    assert reminder.fallback_reason is None
    assert "Việt" in reminder.answer


@pytest.mark.asyncio
async def test_guardrail_rejected_language_control_is_persisted_without_retrieval(db_session) -> None:
    user = await _user(db_session, "pref-guardrail-rejected@example.test")
    service = _service_for(db_session, [_control("vi")], [False])

    result = await service.ask(
        question="Từ giờ dùng tiếng Việt",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    # Presentation state is independent from corpus access: the explicit, healthy control is
    # persisted, while the rejected raw utterance still cannot reach retrieval.
    session = (
        await db_session.execute(
            select(ChatSession).where(ChatSession.public_id == result.conversation_id)
        )
    ).scalar_one()
    assert session.preferred_language == "vi"
    assert service.retrieval_engine.calls == []


@pytest.mark.asyncio
async def test_latest_explicit_preference_wins(db_session) -> None:
    user = await _user(db_session, "pref-latest-wins@example.test")
    service = _service_for(
        db_session,
        [_control("vi"), _control("en"), _knowledge("Sidecar là gì?", spurious_language="vi")],
        [True, True, True],
    )
    first = await service.ask(
        question="Dùng tiếng Việt từ giờ",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )
    await service.ask(
        question="Switch to English from now on",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=first.conversation_id,
    )
    result = await service.ask(
        question="Sidecar là gì?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=first.conversation_id,
    )

    assert result.answer.startswith("I couldn't find")
    session = (
        await db_session.execute(
            select(ChatSession).where(ChatSession.public_id == first.conversation_id)
        )
    ).scalar_one()
    assert session.preferred_language == "en"


@pytest.mark.parametrize(
    ("question", "expected_language"),
    [("What is Sidecar?", AnswerLanguage.EN), ("Sidecar là gì?", AnswerLanguage.VI)],
)
def test_language_detection_is_used_without_explicit_preference(
    question: str, expected_language: AnswerLanguage
) -> None:
    assert _effective_answer_language(None, None, None, question) is expected_language


@pytest.mark.asyncio
async def test_existing_detail_overlay_uses_the_same_persistent_control_contract(db_session) -> None:
    user = await _user(db_session, "pref-detail@example.test")
    service = _service_for(
        db_session,
        [_detail_control("concise"), _knowledge("What is Sidecar?")],
        [True, True],
    )
    first = await service.ask(
        question="Keep your replies concise from now on",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )
    await service.ask(
        question="What is Sidecar?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=first.conversation_id,
    )

    session = (
        await db_session.execute(
            select(ChatSession).where(ChatSession.public_id == first.conversation_id)
        )
    ).scalar_one()
    assert session.preferred_response_detail == "concise"
    assert service.turn_interpreter.calls[1].presentation_preferences.detail == "concise"
    assert (
        _effective_response_length(None, "concise", "detailed", ResponseLength.STANDARD)
        is ResponseLength.CONCISE
    )


# ---------------------------------------------------------------------------------------------
# F5 audit 2026-08-29, failure 1: language/presentation control case A/B/C
# (`ConversationControlApplication`). These reproduce the live regression directly: a REUSE
# verdict with no separable subject trips the REUSE echo-guard (`sanitized=True`) and gets
# demoted to `route=KNOWLEDGE`, which used to lose the presentation control entirely because only
# `route is SOCIAL` was ever trusted as "pure control ack". `application` now settles this
# deterministically instead.
# ---------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sanitized_future_turns_control_still_acks_with_zero_retrieval(db_session) -> None:
    """Case B, exact live bug: the model's own `route` ends up KNOWLEDGE (echo-guard demotion,
    `sanitized=True`) on a pure standing-preference turn, but `application=FUTURE_TURNS` alone is
    enough to route this to a deterministic ack -- never retrieval, never an insufficient-evidence
    fallback."""
    user = await _user(db_session, "pref-sanitized-future@example.test")
    retriever = RecordingRetriever([])
    verdict = InterpreterVerdict(
        scope=InterpreterScope.IN_SCOPE,
        route=InterpreterRoute.KNOWLEDGE,  # echo-guard already demoted this from REUSE
        resolved_question="từ giờ bạn hãy dùng tiếng việt để trả lời nhé",  # echoed, unusable
        presentation=PresentationOverlay(),
        conversation_control=ConversationControl(
            kind=ConversationControlKind.UPDATE_PRESENTATION,
            presentation=PresentationOverlay(language="vi"),
            application=ConversationControlApplication.FUTURE_TURNS,
        ),
        sanitized=True,
    )
    service, _sink = _service(
        db_session,
        retriever=retriever,
        generator=ScriptedGenerator([]),
        interpreter=ScriptedTurnInterpreter([verdict]),
    )
    service.scope_gate = _RecordingScopeGate([True])

    result = await service.ask(
        question="từ giờ bạn hãy dùng tiếng việt để trả lời nhé",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    assert result.fallback is False
    assert result.fallback_reason is None
    assert retriever.calls == []
    session = (
        await db_session.execute(
            select(ChatSession).where(ChatSession.public_id == result.conversation_id)
        )
    ).scalar_one()
    assert session.preferred_language == "vi"


@pytest.mark.asyncio
async def test_sanitized_both_control_reanswers_using_topic_state_subject(db_session) -> None:
    """Case C with a failed subject resolution: `application=BOTH` states the previous answer
    must be re-rendered even though the model's own `resolved_question`/`route` cannot be trusted
    (sanitized). The dispatcher forces REUSE and falls back to the trusted `topic_state.subject`
    anchor -- never the raw, subject-less current utterance -- to judge reused-evidence
    sufficiency."""
    user = await _user(db_session, "pref-sanitized-both@example.test")
    membership = await _project_membership(db_session, user)
    evidence = _candidate(11, "Sidecar đảm nhiệm việc sao lưu dữ liệu lên object storage.")
    retriever = RecordingRetriever([evidence])
    setup_subject = "Các thành phần chính của dự án Thanos"
    # F5 audit 2026-08-30 (TopicState remediation): `_update_topic_state` now sets `subject` from
    # the turn's own grounded CLAIM text, not the resolved_question -- so the setup turn's claim
    # text must equal `setup_subject` here for this test to still isolate what it's actually
    # testing (that a sanitized BOTH control falls back to `topic_state.subject`), rather than
    # conflating that with the separate subject-vs-claim-text semantics this fix changed.
    generator = ScriptedGenerator(
        [
            _claim_result(11, setup_subject),
            _claim_result(11, "Sidecar handles backing up data to object storage."),
        ]
    )
    interpreter = ScriptedTurnInterpreter(
        [
            _verdict(InterpreterRoute.KNOWLEDGE, setup_subject),
            InterpreterVerdict(
                scope=InterpreterScope.IN_SCOPE,
                route=InterpreterRoute.SOCIAL,  # model's own route guess is wrong/irrelevant
                resolved_question="answer that in English and keep using English afterwards",
                presentation=PresentationOverlay(),
                conversation_control=ConversationControl(
                    kind=ConversationControlKind.UPDATE_PRESENTATION,
                    presentation=PresentationOverlay(language="en"),
                    application=ConversationControlApplication.BOTH,
                ),
                sanitized=True,
            ),
        ]
    )
    gate = ScriptedEvidenceGate(
        [
            EvidenceSufficiencyResult(EvidenceSufficiencyVerdict.SUFFICIENT, errored=False),
            EvidenceSufficiencyResult(EvidenceSufficiencyVerdict.SUFFICIENT, errored=False),
        ]
    )
    service, _sink = _service(
        db_session, retriever=retriever, generator=generator, interpreter=interpreter, gate=gate
    )
    service.scope_gate = _RecordingScopeGate([True, True])

    setup = await service.ask(
        question="Dự án Thanos có các thành phần chính nào?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )
    result = await service.ask(
        question="answer that in English and keep using English afterwards",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
        conversation_id=setup.conversation_id,
    )

    assert result.answer.startswith("Sidecar handles backing up data")
    assert gate.calls[-1][0] == setup_subject
    session = (
        await db_session.execute(
            select(ChatSession).where(ChatSession.public_id == setup.conversation_id)
        )
    ).scalar_one()
    assert session.preferred_language == "en"


# ---------------------------------------------------------------------------------------------
# F5 audit 2026-08-30, live-test failure 1 (end-to-end confirmation): "từ giờ hãy trả lời bằng
# tiếng Việt nhé" asked right after a real grounded answer must ACK + persist only -- never
# re-render that previous answer. `chat_service.py` already gates re-render behind an explicit
# `apply_now=True` (`wants_previous_reanswer`); this pins the observable end-to-end behaviour
# against a REAL prior grounded turn, not just the dispatcher's internal booleans.
# ---------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_standing_preference_after_grounded_answer_acks_without_repeating_it(db_session) -> None:
    user = await _user(db_session, "pref-standing-after-grounded@example.test")
    membership = await _project_membership(db_session, user)
    evidence = _candidate(11, "Bạn nên bắt đầu đọc codebase từ cmd/thanos/.")
    retriever = RecordingRetriever([evidence])
    generator = ScriptedGenerator([_claim_result(11, "Bạn nên bắt đầu đọc codebase từ cmd/thanos/.")])
    gate = ScriptedEvidenceGate(
        [EvidenceSufficiencyResult(EvidenceSufficiencyVerdict.SUFFICIENT, errored=False)]
    )
    interpreter = ScriptedTurnInterpreter(
        [
            _verdict(InterpreterRoute.KNOWLEDGE, "Tôi nên bắt đầu đọc codebase từ đâu?"),
            _control("vi"),
        ]
    )
    service, _sink = _service(
        db_session, retriever=retriever, generator=generator, interpreter=interpreter, gate=gate
    )
    service.scope_gate = _RecordingScopeGate([True, True])

    setup = await service.ask(
        question="Tôi nên bắt đầu đọc codebase từ đâu?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )
    assert setup.answer.startswith("Bạn nên bắt đầu đọc codebase từ cmd/thanos/.")

    ack = await service.ask(
        question="từ giờ hãy trả lời bằng tiếng Việt nhé",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
        conversation_id=setup.conversation_id,
    )

    # The whole point: a pure standing-preference turn must never reproduce the prior answer.
    assert "cmd/thanos" not in ack.answer
    assert ack.answer != setup.answer
    assert ack.fallback is False
    # Zero-retrieval ack: only the first turn ever reached retrieval/generation/ESG.
    assert len(retriever.calls) == 1
    assert len(generator.calls) == 1
    assert gate.calls == [("Tôi nên bắt đầu đọc codebase từ đâu?", 1)]
    session = (
        await db_session.execute(
            select(ChatSession).where(ChatSession.public_id == setup.conversation_id)
        )
    ).scalar_one()
    assert session.preferred_language == "vi"


# ---------------------------------------------------------------------------------------------
# F5 audit 2026-08-30, observability remediation: the dispatcher must record the post-default,
# post-override decision fields (`control_application_effective`, `wants_previous_reanswer`,
# `pure_presentation_control`, `route_effective`, `resolved_question_effective`) needed to tell,
# from a live trace alone, whether a standing-preference turn like "từ giờ hãy trả lời bằng
# tiếng Việt nhé" took the ACK-only path or a re-render -- without re-running the request.
# ---------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_standing_preference_after_grounded_answer_records_decision_trace_fields(
    db_session,
) -> None:
    user = await _user(db_session, "pref-standing-trace-fields@example.test")
    membership = await _project_membership(db_session, user)
    evidence = _candidate(11, "Bạn nên bắt đầu đọc codebase từ cmd/thanos/.")
    retriever = RecordingRetriever([evidence])
    generator = ScriptedGenerator([_claim_result(11, "Bạn nên bắt đầu đọc codebase từ cmd/thanos/.")])
    gate = ScriptedEvidenceGate(
        [EvidenceSufficiencyResult(EvidenceSufficiencyVerdict.SUFFICIENT, errored=False)]
    )
    interpreter = ScriptedTurnInterpreter(
        [
            _verdict(InterpreterRoute.KNOWLEDGE, "Tôi nên bắt đầu đọc codebase từ đâu?"),
            _control("vi"),
        ]
    )
    service, sink = _service(
        db_session, retriever=retriever, generator=generator, interpreter=interpreter, gate=gate
    )
    service.scope_gate = _RecordingScopeGate([True, True])

    setup = await service.ask(
        question="Tôi nên bắt đầu đọc codebase từ đâu?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
    )
    await service.ask(
        question="từ giờ hãy trả lời bằng tiếng Việt nhé",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.PROJECT,
        membership_id=membership.membership_id,
        conversation_id=setup.conversation_id,
    )

    details = sink.decision_details(index=-1)
    assert details["control_application_effective"] == "FUTURE_TURNS"
    assert details["wants_previous_reanswer"] is False
    assert details["pure_presentation_control"] is True
    assert details["route_effective"] == "SOCIAL"
    assert details["resolved_question_effective"] == "Update the conversation presentation preference"
