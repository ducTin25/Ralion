from __future__ import annotations

import importlib
import uuid

import pytest

from src.model.enums import DocumentDomain, UserStatus
from src.model.user import User
from src.modules.chat.application.chat_budget_guard import ChatBudgetExceededError
from src.modules.chat.application.chat_service import ChatResult
from src.services.session_service import SESSION_COOKIE_NAME, issue_token

_CONVERSATION_ID = uuid.uuid4()


@pytest.mark.asyncio
async def test_chat_api_uses_authenticated_cookie_identity_not_client_supplied_user(db_client, db_session, monkeypatch) -> None:
    user = User(email="chat-cookie@example.test", display_name="Cookie user", status=UserStatus.ACTIVE)
    db_session.add(user)
    await db_session.commit()
    captured: dict[str, object] = {}

    class RecordingChatService:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def ask(self, **kwargs) -> ChatResult:
            captured.update(kwargs)
            return ChatResult(
                "Grounded policy answer",
                (),
                False,
                None,
                str(kwargs["trace_id"]),
                _CONVERSATION_ID,
            )

    chat_router_module = importlib.import_module("src.api.routers.chat_router")
    monkeypatch.setattr(chat_router_module, "ChatService", RecordingChatService)
    db_client.cookies.set(SESSION_COOKIE_NAME, issue_token(user.user_id))

    response = await db_client.post(
        "/api/v1/chat",
        headers={"X-User-Id": "999999"},
        json={"question": "What is the leave policy?", "mode": "POLICY"},
    )

    assert response.status_code == 200
    assert response.json()["conversation_id"] == str(_CONVERSATION_ID)
    assert response.json()["answer_status"] == "verified"
    assert response.json()["validator_outcome"] is None
    assert response.json()["trace_id"] == response.headers["X-Trace-Id"]
    assert captured["user_id"] == user.user_id
    assert captured["knowledge_domain"] is DocumentDomain.POLICY
    assert captured["membership_id"] is None
    assert captured["conversation_id"] is None


@pytest.mark.asyncio
async def test_unexpected_chat_error_returns_same_trace_in_body_and_header(
    db_client, db_session, monkeypatch
) -> None:
    user = User(
        email="chat-error@example.test",
        display_name="Error user",
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    await db_session.commit()

    class FailingChatService:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def ask(self, **_kwargs):
            raise RuntimeError("provider response must not reach the client")

    chat_router_module = importlib.import_module("src.api.routers.chat_router")
    monkeypatch.setattr(chat_router_module, "ChatService", FailingChatService)
    db_client.cookies.set(SESSION_COOKIE_NAME, issue_token(user.user_id))

    response = await db_client.post(
        "/api/v1/chat",
        json={"question": "What is the leave policy?", "mode": "POLICY"},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"
    assert response.json()["trace_id"] == response.headers["X-Trace-Id"]
    assert "provider response" not in response.text


@pytest.mark.asyncio
async def test_chat_api_serializes_controlled_retrieval_failure_as_fallback(
    db_client, db_session, monkeypatch
) -> None:
    """The known datastore failure exits ChatService as a normal fallback result, never raw 500."""
    user = User(
        email="chat-retrieval-failure@example.test",
        display_name="Retrieval failure user",
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    await db_session.commit()

    class ControlledRetrievalFailureService:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def ask(self, **kwargs) -> ChatResult:
            return ChatResult(
                "I could not retrieve evidence right now.",
                (),
                True,
                "system_error",
                str(kwargs["trace_id"]),
                _CONVERSATION_ID,
                answer_status="fallback",
            )

    chat_router_module = importlib.import_module("src.api.routers.chat_router")
    monkeypatch.setattr(chat_router_module, "ChatService", ControlledRetrievalFailureService)
    db_client.cookies.set(SESSION_COOKIE_NAME, issue_token(user.user_id))

    response = await db_client.post(
        "/api/v1/chat",
        json={"question": "What is the leave policy?", "mode": "POLICY"},
    )

    assert response.status_code == 200
    assert response.json()["fallback_reason"] == "system_error"


@pytest.mark.asyncio
async def test_chat_api_maps_budget_exceeded_to_429(db_client, db_session, monkeypatch) -> None:
    """F-22: a caller over the chat budget gets 429, not a 500 or a silently degraded answer."""
    user = User(
        email="chat-budget@example.test",
        display_name="Budget user",
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    await db_session.commit()

    class BudgetExceededChatService:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def ask(self, **_kwargs):
            raise ChatBudgetExceededError("rate_limit", "Too many chat requests in a short period.")

    chat_router_module = importlib.import_module("src.api.routers.chat_router")
    monkeypatch.setattr(chat_router_module, "ChatService", BudgetExceededChatService)
    db_client.cookies.set(SESSION_COOKIE_NAME, issue_token(user.user_id))

    response = await db_client.post(
        "/api/v1/chat",
        json={"question": "What is the leave policy?", "mode": "POLICY"},
    )

    assert response.status_code == 429
    assert "Too many chat requests" in response.json()["detail"]
