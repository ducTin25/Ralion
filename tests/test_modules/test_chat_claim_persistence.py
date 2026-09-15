from types import SimpleNamespace

import pytest
from sqlalchemy import select

from src.ai.orchestration.answer_generator import AnswerGenerator
from src.ai.retrieval_engine.retrieval_engine import RetrievalFilters, RetrievalResult
from src.model.answer_claim import AnswerClaim
from src.model.chat_message import ChatMessage
from src.model.citation import Citation
from src.model.enums import DocumentDomain, UserStatus
from src.model.user import User
from src.modules.chat.application.chat_service import ChatService


class Provider:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = 0

    async def complete(self, _messages, _budget, _operation):
        self.calls += 1
        return SimpleNamespace(content=self.response)


class Retriever:
    def __init__(self, evidence: list[RetrievalResult]) -> None:
        self.evidence = evidence
        self.retrieve_calls = 0
        self.load_calls: list[tuple[tuple[int, ...], RetrievalFilters]] = []

    async def retrieve(self, _query: str, *, filters: RetrievalFilters, budget) -> list[RetrievalResult]:
        self.retrieve_calls += 1
        return self.evidence

    async def load_scoped_chunks(
        self, chunk_ids, *, filters: RetrievalFilters
    ) -> list[RetrievalResult]:
        self.load_calls.append((tuple(chunk_ids), filters))
        allowed = set(chunk_ids)
        return [item for item in self.evidence if item.chunk.chunk_id in allowed]


def _evidence(content: str) -> RetrievalResult:
    return RetrievalResult(
        chunk=SimpleNamespace(
            chunk_id=11,
            content=content,
            section_path="Testing",
            heading="Testing",
            anchor="testing",
            lexical_identifiers="",
        ),
        knowledge_domain=DocumentDomain.POLICY,
        document_id=1,
        version_id=1,
        document_title="Engineering handbook",
        source_url=None,
        dense_score=0.99,
        hybrid_score=0.5,
    )


async def _user(db_session, email: str) -> User:
    user = User(email=email, display_name=email, status=UserStatus.ACTIVE)
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_multi_claims_and_multiple_anchors_persist_and_rehydrate(db_session) -> None:
    user = await _user(db_session, "claim-persistence@example.test")
    evidence = _evidence("Run cargo test. Submit the pull request.")
    provider = Provider(
        '{"claims":[{"text":"Run cargo test.","support":"direct","citations":[{"chunk_id":11,"quote":"Run cargo test."}]},{"text":"Submit the pull request.","support":"direct","citations":[{"chunk_id":11,"quote":"Run cargo test."},{"chunk_id":11,"quote":"Submit the pull request."}]}],"conflict":null}'
    )
    retriever = Retriever([evidence])
    service = ChatService(db_session, retriever, AnswerGenerator(provider))

    result = await service.ask(
        question="What is the workflow?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )

    claims = list(
        (await db_session.scalars(select(AnswerClaim).order_by(AnswerClaim.claim_index))).all()
    )
    citations = list(
        (await db_session.scalars(select(Citation).order_by(Citation.citation_id))).all()
    )
    message = await db_session.scalar(
        select(ChatMessage).where(ChatMessage.message_id == claims[0].message_id)
    )

    assert result.answer == "Run cargo test.\n\nSubmit the pull request."
    assert [claim.claim_index for claim in claims] == [0, 1]
    assert [claim.text for claim in claims] == ["Run cargo test.", "Submit the pull request."]
    assert [citation.claim_id for citation in citations] == [
        claims[0].claim_id,
        claims[1].claim_id,
        claims[1].claim_id,
    ]
    assert all(citation.quote in evidence.chunk.content for citation in citations)
    assert message is not None
    assert message.answer_status == "verified"
    assert message.validator_outcome == "passed"
    assert message.confidence == 0.99

    transcript = await service.transcript(
        user_id=user.user_id, conversation_id=result.conversation_id
    )
    turn = transcript.turns[0]
    assert [claim["claim_index"] for claim in turn.claims] == [0, 1]
    assert [len(claim["citations"]) for claim in turn.claims] == [1, 2]
    assert turn.claims[1]["citations"][1]["quote"] == "Submit the pull request."
    assert turn.answer_status == "verified"


@pytest.mark.asyncio
async def test_degraded_path_persists_only_redacted_surviving_claim(db_session) -> None:
    user = await _user(db_session, "claim-degraded@example.test")
    secret = "token=supersecretvalue"
    evidence = _evidence(f"Use {secret}. Run cargo test.")
    provider = Provider(
        '{"claims":[{"text":"Use token=supersecretvalue.","support":"direct","citations":[{"chunk_id":11,"quote":"token=supersecretvalue."}]},{"text":"Use version 99.","support":"direct","citations":[{"chunk_id":99,"quote":"fabricated"}]}]}'
    )
    service = ChatService(db_session, Retriever([evidence]), AnswerGenerator(provider))

    result = await service.ask(
        question="What should I use?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )
    claims = list((await db_session.scalars(select(AnswerClaim))).all())
    citations = list((await db_session.scalars(select(Citation))).all())

    assert provider.calls == 1
    assert service.retrieval_engine.retrieve_calls == 1
    assert result.answer_status == "partially_verified"
    assert result.validator_outcome == "degraded"
    assert len(claims) == 1
    assert len(citations) == 1
    assert citations[0].chunk_id == 11
    assert claims[0].redacted is True
    assert secret not in result.answer
    assert secret not in claims[0].text
    assert secret not in citations[0].quote
    assert secret not in result.claims[0]["citations"][0]["source_content"]
    assert "version 99" not in result.answer


@pytest.mark.asyncio
async def test_conflict_metadata_is_persisted_with_claims(db_session) -> None:
    user = await _user(db_session, "claim-conflict@example.test")
    evidence = _evidence("Source dates differ.")
    provider = Provider(
        '{"claims":[{"text":"Source dates differ.","support":"direct","citations":[{"chunk_id":11,"quote":"Source dates differ."}]}],"conflict":"Sources have different effective dates."}'
    )
    service = ChatService(db_session, Retriever([evidence]), AnswerGenerator(provider))

    result = await service.ask(
        question="Do the sources conflict?",
        user_id=user.user_id,
        knowledge_domain=DocumentDomain.POLICY,
    )
    message = await db_session.scalar(
        select(ChatMessage).where(ChatMessage.trace_id == result.trace_id, ChatMessage.grounded)
    )

    assert result.answer_status == "conflict"
    assert result.conflict == "Sources have different effective dates."
    assert message is not None
    assert message.answer_status == "conflict"
    assert message.conflict == result.conflict
