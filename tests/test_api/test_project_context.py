import importlib
from unittest.mock import AsyncMock

import pytest

from src.dto.response.membership_context_response_dto import (
    ActiveMembershipResponseDTO,
    MembershipCardDTO,
    MembershipPlanDTO,
)
from src.model.enums import (
    MembershipStatus,
    PlanStatus,
    ProjectRole,
    ProjectStatus,
    SyncStatus,
    UserStatus,
)
from src.model.project import Project
from src.model.project_membership import ProjectMembership
from src.model.user import User
from src.services import project_membership_service
from src.services.session_service import SESSION_COOKIE_NAME, issue_token

project_membership_router = importlib.import_module("src.api.routers.project_membership_router")


@pytest.mark.asyncio
async def test_list_memberships_requires_user_context(client):
    response = await client.get("/api/v1/me/memberships")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "UNAUTHENTICATED"


@pytest.mark.asyncio
async def test_list_memberships_returns_camel_case_contract(client, monkeypatch):
    list_mock = AsyncMock(
        return_value=[
            MembershipCardDTO(
                membership_id=9,
                project_id=1,
                project_name="PhoneShop API",
                project_key="PHONESHOP",
                project_status=ProjectStatus.ACTIVE,
                project_role=ProjectRole.PM,
                joined_at="2026-08-12T08:00:00",
                sync_status=SyncStatus.SUCCESS,
                last_synced_at="2026-08-12T08:00:00",
                plan=MembershipPlanDTO(
                    status=PlanStatus.ACTIVE,
                    revision=1,
                    required_done=5,
                    required_total=12,
                    open_blockers=0,
                ),
            )
        ]
    )
    monkeypatch.setattr(
        project_membership_router.project_membership_service,
        "list_selectable_memberships",
        list_mock,
    )

    response = await client.get(
        "/api/v1/me/memberships",
        headers={"Cookie": f"{SESSION_COOKIE_NAME}={issue_token(9)}"},
    )

    assert response.status_code == 200
    payload = response.json()[0]
    assert payload["membershipId"] == 9
    assert payload["projectRole"] == "PM"
    assert payload["plan"]["requiredDone"] == 5
    assert "membership_id" not in payload


@pytest.mark.asyncio
async def test_establish_membership_revalidates_through_service(client, monkeypatch):
    establish_mock = AsyncMock(
        return_value=ActiveMembershipResponseDTO(
            membership_id=9,
            project_id=1,
            project_name="PhoneShop API",
            project_key="PHONESHOP",
            project_role=ProjectRole.PM,
            redirect_path="/product-manager?project=1",
        )
    )
    monkeypatch.setattr(
        project_membership_router.project_membership_service,
        "establish_active_membership",
        establish_mock,
    )

    response = await client.post(
        "/api/v1/me/active-membership",
        headers={"Cookie": f"{SESSION_COOKIE_NAME}={issue_token(9)}"},
        json={"membership_id": 9},
    )

    assert response.status_code == 200
    assert response.json()["redirectPath"] == "/product-manager?project=1"
    establish_mock.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("project_role", "expected_path"),
    [
        (ProjectRole.PM, "/product-manager?project=21"),
        (ProjectRole.ENGINEER, "/user?project=21"),
    ],
)
async def test_establish_membership_routes_each_project_role(db_session, project_role, expected_path):
    admin = User(
        user_id=10,
        email="admin.routing@onboarding.dev",
        password_hash=None,
        display_name="Routing Admin",
        system_role=None,
        status=UserStatus.ACTIVE,
    )
    member = User(
        user_id=11,
        email="member.routing@onboarding.dev",
        password_hash=None,
        display_name="Routing Member",
        system_role=None,
        status=UserStatus.ACTIVE,
    )
    project = Project(
        project_id=21,
        key="ROUTING",
        name="Routing Project",
        github_repo="example/routing",
        default_branch="main",
        created_by_admin_id=admin.user_id,
        status=ProjectStatus.ACTIVE,
        sync_status=SyncStatus.NOT_STARTED,
    )
    membership = ProjectMembership(
        membership_id=31,
        user_id=member.user_id,
        project_id=project.project_id,
        project_role=project_role,
        status=MembershipStatus.ACTIVE,
        assigned_by_admin_id=admin.user_id,
    )
    db_session.add_all([admin, member, project, membership])
    await db_session.commit()

    result = await project_membership_service.establish_active_membership(
        db_session, member.user_id, membership.membership_id
    )

    assert result.redirect_path == expected_path
