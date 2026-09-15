import importlib
from unittest.mock import AsyncMock

import pytest

from src.dto.response.member_onboarding_response_dto import (
    MemberProfileResponseDTO,
    MemberProjectsResponseDTO,
)
from src.model.enums import UserStatus
from src.model.user import User
from src.services.session_service import SESSION_COOKIE_NAME, issue_token

member_onboarding_router = importlib.import_module("src.api.routers.member_onboarding_router")


@pytest.mark.asyncio
async def test_member_projects_requires_authenticated_identity(client):
    response = await client.get("/api/v1/member/projects")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "UNAUTHENTICATED"


@pytest.mark.asyncio
async def test_pm_project_documents_require_authenticated_identity(client):
    response = await client.get("/api/v1/knowledge-documents/pm/projects/1")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "UNAUTHENTICATED"


@pytest.mark.asyncio
async def test_member_projects_uses_signed_in_user(db_client, db_session, monkeypatch):
    member = User(
        user_id=42,
        email="engineer.session@onboarding.dev",
        password_hash=None,
        display_name="Session Engineer",
        system_role=None,
        status=UserStatus.ACTIVE,
    )
    db_session.add(member)
    await db_session.commit()

    response_dto = MemberProjectsResponseDTO(
        member=MemberProfileResponseDTO(
            user_id=member.user_id,
            email=member.email,
            display_name=member.display_name,
        ),
        projects=[],
    )
    list_projects = AsyncMock(return_value=response_dto)
    monkeypatch.setattr(member_onboarding_router.member_onboarding_service, "list_projects", list_projects)

    response = await db_client.get(
        "/api/v1/member/projects",
        headers={"Cookie": f"{SESSION_COOKIE_NAME}={issue_token(member.user_id)}"},
    )

    assert response.status_code == 200
    assert response.json()["member"]["user_id"] == member.user_id
    authenticated_member = list_projects.await_args.args[1]
    assert authenticated_member.user_id == member.user_id
