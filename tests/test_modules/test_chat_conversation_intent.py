"""Weakness #4 (CHANGE_LOG.md 2026-08-21) regression tests: conversation-meta questions must
answer from this conversation's own persisted history (AnswerMode.CONVERSATION), never through
knowledge retrieval, and normal domain questions/follow-ups must keep going through
AnswerMode.KNOWLEDGE exactly as before (F-01 unchanged)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.ai.orchestration.answer_generator import ClaimSupport, GenerationSuccess, VerifiedClaim
from src.ai.orchestration.conversation_answer import ConversationAnswerGenerator
from src.ai.retrieval_engine.retrieval_engine import RetrievalFilters, RetrievalResult
from src.model.enums import DocumentDomain, UserStatus
from src.model.user import User
from src.modules.chat.application.chat_service import ChatService


class RecordingRetriever:
    def __init__(self, results: list[RetrievalResult]) -> None:
        self.results = results
        self.calls: list[tuple[str, RetrievalFilters]] = []

    async def retrieve(self, question: str, *, filters: RetrievalFilters, budget) -> list[RetrievalResult]:
        self.calls.append((question, filters))
        return self.results

    async def list_available_topics(self, filters: RetrievalFilters, *, limit: int = 3) -> list[str]:
        return []


class FixedGenerator:
    def __init__(self, result: GenerationSuccess) -> None:
        self.result = result
        self.calls = 0

    async def generate(
        self, _question, _candidates, *, history=(), budget=None, response_length=None, response_tone=None
    ):
        self.calls += 1
        return self.result


class ConversationProvider:
    """Records every prompt it receives and returns scripted content, one call at a time."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = iter(responses)
        self.messages: list[list[tuple[str, str]]] = []

    async def complete(self, messages, _budget, _operation):
        self.messages.append(list(messages))
        return SimpleNamespace(content=next(self.responses))

    def last_prompt(self) -> str:
        return "\n".join(content for _role, content in self.messages[-1])


def _candidate() -> RetrievalResult:
    return RetrievalResult(
        chunk=SimpleNamespace(
            chunk_id=11,
            content="Remote work is allowed up to 3 days per week.",
            section_path="Remote Work",
            heading="Remote Work",
            lexical_identifiers="",
        ),
        knowledge_domain=DocumentDomain.POLICY,
        document_id=1,
        version_id=1,
        dense_score=0.99,
        hybrid_score=0.5,
    )


def _generation(text: str) -> GenerationSuccess:
    return GenerationSuccess(claims=(VerifiedClaim(text, ClaimSupport.DIRECT, ()),), retry_count=0)


async def _user(db_session, email: str) -> User:
    user = User(email=email, display_name=email, status=UserStatus.ACTIVE)
    db_session.add(user)
    await db_session.flush()
    return user


def _service(db_session, *, retriever=None, generator=None, conversation_provider=None) -> tuple[ChatService, ConversationProvider]:
    provider = conversation_provider or ConversationProvider(["(no scripted response)"] * 10)
    service = ChatService(
        db_session,
        retriever or RecordingRetriever([_candidate()]),
        generator or FixedGenerator(_generation("Remote work is allowed up to 3 days per week. [1]")),
        conversation_answer_generator=ConversationAnswerGenerator(provider),
    )
    return service, provider


@pytest.mark.asyncio
async def test_four_turn_flow_meta_question_answers_from_history_not_limited_evidence(db_session) -> None:
    """Regression for the exact reported failure: turn 4 must answer from conversation history,
    never `Limited evidence`/`insufficient_evidence`/`no_evidence`, and must not call retrieval."""
    user = await _user(db_session, "meta-flow@example.test")
    retriever = RecordingRetriever([_candidate()])
    provider = ConversationProvider(["Bạn đã hỏi về chính sách làm việc từ xa (remote work)."])
    service, _ = _service(db_session, retriever=retriever, conversation_provider=provider)

    turn1 = await service.ask(
        question="Chính sách làm việc từ xa của công ty là gì?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )
    turn2 = await service.ask(
        question="dịch câu trả lời trên sang tiếng anh",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=turn1.conversation_id,
    )
    turn3 = await service.ask(
        question="nếu vi phạm thì sao?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=turn1.conversation_id,
    )
    assert turn1.fallback is False and turn2.fallback is False and turn3.fallback is False
    # turns 2/3 are short follow-ups, so Tier-1 expansion fires and each also retrieves on the
    # bare question (2026-08-22 anti-dilution fix) -- the exact count isn't this test's point;
    # what matters is turn4 (below) adds NONE.
    calls_after_three_turns = len(retriever.calls)
    assert calls_after_three_turns > 0

    turn4 = await service.ask(
        question="câu đầu tiên tôi hỏi về gì?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=turn1.conversation_id,
    )

    assert turn4.fallback is False
    assert turn4.fallback_reason is None
    assert turn4.answer_status == "verified"
    assert turn4.citations == ()
    # Retrieval must not have been called for the meta-question turn.
    assert len(retriever.calls) == calls_after_three_turns
    # The real first question must have reached the conversation-answer prompt.
    assert "Chính sách làm việc từ xa của công ty là gì?" in provider.last_prompt()
    assert "remote work" in turn4.answer.lower() or "remote" in turn4.answer.lower()


@pytest.mark.asyncio
async def test_summarize_conversation_uses_the_full_transcript_not_just_recent_window(db_session) -> None:
    """`max_turn_pairs` (default 3) must not silently cap what "summarize this conversation" can
    see -- a 4th earlier turn that a KNOWLEDGE-mode window would have dropped must still appear."""
    user = await _user(db_session, "summarize@example.test")
    retriever = RecordingRetriever([_candidate()])
    provider = ConversationProvider(["Tóm tắt: bạn đã hỏi về A, B, C và D."])
    service, _ = _service(db_session, retriever=retriever, conversation_provider=provider)

    conversation_id = None
    questions = ["Câu hỏi A?", "Câu hỏi B?", "Câu hỏi C?", "Câu hỏi D?"]
    for question in questions:
        result = await service.ask(
            question=question,
            user_id=user.user_id,
            knowledge_domain=DocumentDomain.POLICY,
            conversation_id=conversation_id,
        )
        conversation_id = result.conversation_id
    # B/C/D are short follow-ups, so Tier-1 expansion fires and each also retrieves on the bare
    # question (2026-08-22 anti-dilution fix) -- the exact count isn't this test's point; what
    # matters is the summarize turn below adds NONE.
    calls_after_four_turns = len(retriever.calls)
    assert calls_after_four_turns >= 4

    result = await service.ask(
        question="Tóm tắt cuộc trò chuyện này",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=conversation_id,
    )

    assert result.fallback is False
    assert len(retriever.calls) == calls_after_four_turns  # unchanged: no retrieval for the summarize turn
    prompt = provider.last_prompt()
    for question in questions:
        assert question in prompt


@pytest.mark.asyncio
async def test_synthesize_discussed_points_only_reflects_actual_conversation_content(db_session) -> None:
    user = await _user(db_session, "synthesize@example.test")
    retriever = RecordingRetriever([_candidate()])
    provider = ConversationProvider(["Các điểm đã trao đổi: chính sách nghỉ phép và giờ làm việc."])
    service, _ = _service(db_session, retriever=retriever, conversation_provider=provider)

    turn1 = await service.ask(
        question="Chính sách nghỉ phép của công ty là gì?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )
    result = await service.ask(
        question="Tổng hợp các kiến thức quan trọng đã trao đổi",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=turn1.conversation_id,
    )

    assert result.fallback is False
    assert len(retriever.calls) == 1  # only turn1's real knowledge question retrieved anything
    assert "Chính sách nghỉ phép của công ty là gì?" in provider.last_prompt()


@pytest.mark.asyncio
async def test_previous_turn_reference_question_answers_from_history(db_session) -> None:
    user = await _user(db_session, "prev-turn@example.test")
    retriever = RecordingRetriever([_candidate()])
    provider = ConversationProvider(["Câu hỏi trước của bạn là về chính sách nghỉ phép."])
    service, _ = _service(db_session, retriever=retriever, conversation_provider=provider)

    turn1 = await service.ask(
        question="Chính sách nghỉ phép của công ty là gì?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )
    result = await service.ask(
        question="Câu hỏi trước của tôi là gì?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=turn1.conversation_id,
    )

    assert result.fallback is False
    assert len(retriever.calls) == 1
    assert result.citations == ()


@pytest.mark.asyncio
async def test_conversation_ownership_is_isolated_from_other_users(db_session) -> None:
    """A forged/foreign conversation_id must not leak another user's history into a
    CONVERSATION-mode answer -- same ownership predicate as every other conversation lookup."""
    owner = await _user(db_session, "owner@example.test")
    intruder = await _user(db_session, "intruder@example.test")
    service, provider = _service(db_session)

    owned = await service.ask(
        question="Chính sách bảo mật của công ty là gì?",
        user_id=owner.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    from src.modules.chat.application.chat_service import ConversationNotFoundError

    with pytest.raises(ConversationNotFoundError):
        await service.ask(
            question="câu đầu tiên tôi hỏi về gì?",
            user_id=intruder.user_id,
            knowledge_domain=DocumentDomain.POLICY,
            conversation_id=owned.conversation_id,
        )
    # No conversation-answer call must have leaked the owner's history to the intruder.
    assert provider.messages == []


@pytest.mark.asyncio
async def test_normal_knowledge_question_still_uses_retrieval_and_citations(db_session) -> None:
    user = await _user(db_session, "knowledge@example.test")
    retriever = RecordingRetriever([_candidate()])
    generator = FixedGenerator(_generation("Remote work is allowed up to 3 days per week. [1]"))
    service, provider = _service(db_session, retriever=retriever, generator=generator)

    result = await service.ask(
        question="What is the remote work policy?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    assert result.fallback is False
    assert generator.calls == 1
    assert len(retriever.calls) == 1
    assert provider.messages == []  # the conversation-answer generator must never be called


@pytest.mark.asyncio
async def test_normal_coreference_followup_keeps_f01_query_expansion_behavior(db_session) -> None:
    """Regression: a real domain follow-up ("cái đó...") must still expand the retrieval query
    with the prior question, exactly as F-01 already does -- weakness #4 must not touch it."""
    user = await _user(db_session, "followup@example.test")
    retriever = RecordingRetriever([_candidate()])
    generator = FixedGenerator(_generation("Remote work is allowed up to 3 days per week. [1]"))
    service, provider = _service(db_session, retriever=retriever, generator=generator)

    turn1 = await service.ask(
        question="Chính sách làm việc từ xa của công ty là gì?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )
    await service.ask(
        question="cái đó áp dụng từ khi nào?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
        conversation_id=turn1.conversation_id,
    )

    # turn2 is Tier-1-expanded, so it retrieves twice: the expanded query (calls[1], asserted
    # below) and, since 2026-08-22's anti-dilution fix, the bare question too (calls[2]).
    assert len(retriever.calls) == 3
    expanded_query = retriever.calls[1][0]
    assert "cái đó áp dụng từ khi nào?" in expanded_query
    assert "Chính sách làm việc từ xa của công ty là gì?" in expanded_query
    standalone_query = retriever.calls[2][0]
    assert standalone_query == "cái đó áp dụng từ khi nào?"
    assert provider.messages == []  # still KNOWLEDGE mode, not routed to conversation-answer
