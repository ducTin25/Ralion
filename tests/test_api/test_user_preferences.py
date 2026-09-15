"""HTTP-level tests for self-service chat personalization (PATCH /auth/me/preferences).

Uses `db_client`/`db_session` (SQLite in-memory, real ORM round trip via `Base.metadata.
create_all` — see tests/conftest.py) instead of `FakeSession`, so these tests exercise the
real `update_preferences` service function and the real `User.response_length`/
`response_tone` enum columns, not a stand-in.
"""

import pytest

from src.model.enums import ResponseLength, ResponseTone, UserStatus
from src.model.user import User
from src.services.session_service import SESSION_COOKIE_NAME, issue_token


async def _create_user(db_session, *, email: str) -> User:
    user = User(email=email, display_name="Test User", status=UserStatus.ACTIVE)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _session_cookie(user_id: int) -> dict[str, str]:
    return {"Cookie": f"{SESSION_COOKIE_NAME}={issue_token(user_id)}"}


@pytest.mark.asyncio
async def test_new_user_defaults_are_standard_neutral(db_client, db_session):
    """PERSONALIZE_CHATBOT_SPEC.md §1.2: a user who never touches the feature must read STANDARD/NEUTRAL."""
    user = await _create_user(db_session, email="default@onboarding.dev")

    response = await db_client.get("/api/v1/auth/me", headers=_session_cookie(user.user_id))

    assert response.status_code == 200
    body = response.json()
    assert body["response_length"] == "STANDARD"
    assert body["response_tone"] == "NEUTRAL"


@pytest.mark.asyncio
async def test_update_preferences_persists_and_reflects_in_response(db_client, db_session):
    user = await _create_user(db_session, email="persist@onboarding.dev")

    response = await db_client.patch(
        "/api/v1/auth/me/preferences",
        json={"response_length": "CONCISE", "response_tone": "MENTOR"},
        headers=_session_cookie(user.user_id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["response_length"] == "CONCISE"
    assert body["response_tone"] == "MENTOR"
    assert user.response_length == ResponseLength.CONCISE
    assert user.response_tone == ResponseTone.MENTOR


@pytest.mark.asyncio
async def test_update_preferences_is_a_partial_update(db_client, db_session):
    """Sending only one field must not reset the other back to its default."""
    user = await _create_user(db_session, email="partial@onboarding.dev")
    first = await db_client.patch(
        "/api/v1/auth/me/preferences",
        json={"response_length": "DETAILED", "response_tone": "BUDDY"},
        headers=_session_cookie(user.user_id),
    )
    assert first.status_code == 200

    second = await db_client.patch(
        "/api/v1/auth/me/preferences",
        json={"response_length": "CONCISE"},
        headers=_session_cookie(user.user_id),
    )

    assert second.status_code == 200
    body = second.json()
    assert body["response_length"] == "CONCISE"
    assert body["response_tone"] == "BUDDY"  # untouched by the partial update


@pytest.mark.asyncio
async def test_update_preferences_rejects_invalid_enum_value(db_client, db_session):
    user = await _create_user(db_session, email="invalid@onboarding.dev")

    response = await db_client.patch(
        "/api/v1/auth/me/preferences",
        json={"response_length": "SUPER_LONG"},
        headers=_session_cookie(user.user_id),
    )

    assert response.status_code == 422
    await db_session.refresh(user)
    assert user.response_length == ResponseLength.STANDARD


@pytest.mark.asyncio
async def test_update_preferences_requires_authentication(db_client):
    response = await db_client.patch(
        "/api/v1/auth/me/preferences", json={"response_length": "CONCISE"}
    )
    assert response.status_code == 401
