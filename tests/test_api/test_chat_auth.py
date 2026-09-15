from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import src.api.dependencies as dependencies
from src.api.dependencies import get_session_user, get_session_user_id
from src.config import DEFAULT_SESSION_SECRET, Settings
from src.model.enums import UserStatus
from src.services.session_service import issue_token


@pytest.mark.asyncio
async def test_chat_rejects_user_id_header_even_when_legacy_dev_fallback_is_enabled(client, monkeypatch) -> None:
    monkeypatch.setattr(
        dependencies,
        "get_settings",
        lambda: SimpleNamespace(allow_header_user_context=True),
    )

    response = await client.post(
        "/api/v1/chat",
        headers={"X-User-Id": "7"},
        json={"question": "What is the leave policy?", "mode": "POLICY"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "NO_SESSION"


@pytest.mark.asyncio
async def test_session_user_id_accepts_only_a_valid_signed_cookie() -> None:
    token = issue_token(7)
    assert await get_session_user_id(token) == 7

    with pytest.raises(HTTPException) as exc_info:
        await get_session_user_id("7.0.9999999999.invalid-signature")
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["code"] == "INVALID_SIGNATURE"


@pytest.mark.asyncio
async def test_session_user_rejects_an_inactive_account() -> None:
    inactive_user = SimpleNamespace(status=UserStatus.INACTIVE)

    class Session:
        async def get(self, _model, _user_id):
            return inactive_user

    with pytest.raises(HTTPException) as exc_info:
        await get_session_user(7, Session())
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "ACCOUNT_INACTIVE"


def test_production_rejects_header_identity_fallback() -> None:
    with pytest.raises(ValueError, match="ALLOW_HEADER_USER_CONTEXT"):
        Settings(
            app_env="production",
            session_secret="production-only-secret",
            allow_header_user_context=True,
        )


def test_production_rejects_default_session_secret() -> None:
    with pytest.raises(ValueError, match="SESSION_SECRET"):
        Settings(app_env="production", session_secret=DEFAULT_SESSION_SECRET)
