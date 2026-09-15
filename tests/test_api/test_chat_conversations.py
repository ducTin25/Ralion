"""API-level tests for conversation continuation and rehydration after a reload."""

from __future__ import annotations

import importlib
import uuid
from types import SimpleNamespace

import pytest

from src.ai.orchestration.answer_generator import ClaimSupport, GenerationSuccess, VerifiedClaim
from src.ai.orchestration.evidence_sufficiency_gate import (
    EvidenceSufficiencyResult,
    EvidenceSufficiencyVerdict,
)
from src.ai.orchestration.turn_interpreter import (
    InterpreterRoute,
    InterpreterScope,
    InterpreterVerdict,
    KnowledgePolicy,
    PresentationOverlay,
    TurnInterpreterConfig,
)
from src.ai.retrieval_engine.retrieval_engine import RetrievalResult
from src.model.enums import DocumentDomain, UserStatus
from src.model.user import User
from src.services.session_service import SESSION_COOKIE_NAME, issue_token


def _candidate() -> RetrievalResult:
    return RetrievalResult(
        chunk=SimpleNamespace(
            chunk_id=11,
            content="Employees receive 12 leave days.",
            section_path="Leave",
            heading="Leave",
            anchor=None,
            lexical_identifiers="",
        ),
        knowledge_domain=DocumentDomain.POLICY,
        document_id=1,
        version_id=1,
        dense_score=0.99,
        hybrid_score=0.5,
    )


class _StubRetrievalEngine:
    def __init__(self, _db, _query_embedding) -> None:
        pass

    async def retrieve(self, _query, *, filters, budget):
        return [_candidate()]

    async def load_scoped_chunks(self, _chunk_ids, *, filters):
        return []


class _StubGenerator:
    def __init__(self, _llm, **_kwargs) -> None:
        pass

    async def generate(
        self,
        question,
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
        return GenerationSuccess(
            claims=(VerifiedClaim(f"Answer to: {question}", ClaimSupport.DIRECT, ()),),
            retry_count=0,
        )


class _StubEvidenceSufficiencyGate:
    """The real gate makes a real LLM judge call against `_StubRetrievalEngine`'s fixed fake
    candidate -- whose content only says "12 leave days", nothing about e.g. an effective date a
    coreference follow-up ("cái đó áp dụng từ khi nào?") might ask about. Real judge quality
    against a deliberately thin fake candidate isn't what these reload/persistence tests are
    about; stubbed deterministically SUFFICIENT, same rationale as `_StubRetrievalEngine`/
    `_StubGenerator` already replacing the other real collaborators here."""

    def __init__(self, _llm, _config=None) -> None:
        pass

    async def check(self, _question, _accepted, _budget):
        return EvidenceSufficiencyResult(verdict=EvidenceSufficiencyVerdict.SUFFICIENT, errored=False)


class _StubTurnInterpreter:
    def __init__(self, _llm, _config=None) -> None:
        self.config = _config or TurnInterpreterConfig(enabled=True, shadow=False)

    async def interpret(self, context, _budget):
        return InterpreterVerdict(
            scope=InterpreterScope.IN_SCOPE,
            route=InterpreterRoute.KNOWLEDGE,
            resolved_question=context.current_utterance,
            presentation=PresentationOverlay(),
            knowledge_policy=KnowledgePolicy.STRICT_INTERNAL,
        )


@pytest.fixture
def stub_chat(monkeypatch):
    """Replace AI collaborators while keeping the real service and repository.

    Conversation persistence is the subject here; routing and provider integration have their
    own suites and must not make this API test depend on external credentials.
    """
    module = importlib.import_module("src.api.routers.chat_router")
    monkeypatch.setattr(module, "RetrievalEngine", _StubRetrievalEngine)
    monkeypatch.setattr(module, "AnswerGenerator", _StubGenerator)
    monkeypatch.setattr(module, "EvidenceSufficiencyGate", _StubEvidenceSufficiencyGate)
    monkeypatch.setattr(module, "TurnInterpreter", _StubTurnInterpreter)
    return module


async def _signed_in(db_client, db_session, email: str) -> User:
    user = User(email=email, display_name=email, status=UserStatus.ACTIVE)
    db_session.add(user)
    await db_session.commit()
    db_client.cookies.set(SESSION_COOKIE_NAME, issue_token(user.user_id))
    return user


async def _ask(db_client, question: str, conversation_id: str | None = None):
    payload: dict[str, object] = {"question": question, "mode": "POLICY"}
    if conversation_id is not None:
        payload["conversation_id"] = conversation_id
    response = await db_client.post("/api/v1/chat", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
async def test_reload_recovers_the_conversation_from_the_server(db_client, db_session, stub_chat) -> None:
    await _signed_in(db_client, db_session, "conv-reload@example.test")

    first = await _ask(db_client, "How many leave days do employees receive each year?")
    assert first["claims"][0]["text"].startswith("Answer to:")
    await _ask(db_client, "cái đó áp dụng từ khi nào?", first["conversation_id"])

    # A reload has no client state beyond the conversation id.
    reloaded = await db_client.get(f"/api/v1/chat/conversations/{first['conversation_id']}")

    assert reloaded.status_code == 200
    body = reloaded.json()
    assert body["conversation_id"] == first["conversation_id"]
    assert body["mode"] == "POLICY"
    assert [turn["turn_index"] for turn in body["turns"]] == [0, 1]
    assert body["turns"][0]["question"] == "How many leave days do employees receive each year?"
    assert body["turns"][1]["answer"].startswith("Answer to: cái đó")
    assert body["turns"][1]["fallback"] is False
    assert body["turns"][1]["answer_status"] == "verified"
    assert body["turns"][1]["validator_outcome"] == "passed"
    assert body["turns"][1]["claims"][0]["text"].startswith("Answer to:")


@pytest.mark.asyncio
async def test_new_conversation_starts_when_no_id_is_sent(db_client, db_session, stub_chat) -> None:
    await _signed_in(db_client, db_session, "conv-new@example.test")

    first = await _ask(db_client, "How many leave days do employees receive each year?")
    second = await _ask(db_client, "Which national holidays does the company observe?")

    assert first["conversation_id"] != second["conversation_id"]


@pytest.mark.asyncio
async def test_unknown_conversation_id_is_not_found_on_both_verbs(db_client, db_session, stub_chat) -> None:
    await _signed_in(db_client, db_session, "conv-unknown@example.test")
    unknown = str(uuid.uuid4())

    posted = await db_client.post(
        "/api/v1/chat",
        json={"question": "What is the leave policy?", "mode": "POLICY", "conversation_id": unknown},
    )
    fetched = await db_client.get(f"/api/v1/chat/conversations/{unknown}")

    assert posted.status_code == 404
    assert fetched.status_code == 404
    assert posted.json()["detail"] == fetched.json()["detail"]


@pytest.mark.asyncio
async def test_another_users_conversation_is_indistinguishable_from_a_missing_one(
    db_client, db_session, stub_chat
) -> None:
    await _signed_in(db_client, db_session, "conv-owner@example.test")
    owned = await _ask(db_client, "How many leave days do employees receive each year?")

    await _signed_in(db_client, db_session, "conv-intruder@example.test")
    hijacked = await db_client.get(f"/api/v1/chat/conversations/{owned['conversation_id']}")
    missing = await db_client.get(f"/api/v1/chat/conversations/{uuid.uuid4()}")

    assert hijacked.status_code == 404
    assert hijacked.json()["detail"] == missing.json()["detail"]


@pytest.mark.asyncio
async def test_conversation_read_requires_a_session(db_client, db_session, stub_chat) -> None:
    await _signed_in(db_client, db_session, "conv-anon@example.test")
    owned = await _ask(db_client, "How many leave days do employees receive each year?")

    db_client.cookies.clear()
    response = await db_client.get(
        f"/api/v1/chat/conversations/{owned['conversation_id']}",
        headers={"X-User-Id": "1"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "NO_SESSION"
