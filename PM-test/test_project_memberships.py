import uuid

import pytest


def _unique_key() -> str:
    return f"TEST{uuid.uuid4().hex[:8].upper()}"


async def _create_project(client, test_data, admin_id: int) -> int:
    response = await client.post(
        "/api/v1/projects/pm",
        json={"key": _unique_key(), "name": "Membership Test Project", "created_by_admin_id": admin_id},
    )
    assert response.status_code == 201
    project_id = response.json()["project_id"]
    test_data.project_ids.append(project_id)
    return project_id


async def _create_member_user(client, test_data, admin_id: int) -> int:
    """User dùng để test membership PHẢI có system_role=None — theo INV1 (trigger DB), user có
    system_role (ADMIN/HR) không được phép có ProjectMembership."""
    email = f"test-member-{uuid.uuid4().hex[:8]}@onboarding.dev"
    response = await client.post(
        "/api/v1/users",
        headers={"X-User-Id": str(admin_id)},
        json={"email": email, "display_name": "Test Member", "created_by_admin_id": admin_id},
    )
    assert response.status_code == 201
    user_id = response.json()["user_id"]
    test_data.user_ids.append(user_id)
    return user_id


@pytest.mark.asyncio
async def test_create_membership(client, test_data, admin_id):
    project_id = await _create_project(client, test_data, admin_id)
    user_id = await _create_member_user(client, test_data, admin_id)

    response = await client.post(
        "/api/v1/project-memberships/pm",
        json={"user_id": user_id, "project_id": project_id, "project_role": "PM", "assigned_by_admin_id": admin_id},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == user_id
    assert data["project_id"] == project_id
    assert data["project_role"] == "PM"
    assert data["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_create_membership_duplicate(client, test_data, admin_id):
    project_id = await _create_project(client, test_data, admin_id)
    user_id = await _create_member_user(client, test_data, admin_id)
    payload = {"user_id": user_id, "project_id": project_id, "project_role": "PM", "assigned_by_admin_id": admin_id}

    first = await client.post("/api/v1/project-memberships/pm", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/project-memberships/pm", json=payload)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_create_membership_rejects_system_role_user(client, test_data, admin_id):
    """INV1 (trigger DB, xem migration a1b2c3d4e5f6): user có system_role (vd admin seed)
    không được phép có membership — API phải trả lỗi rõ ràng (409), không phải 201 giả
    hay crash không rõ nguyên nhân."""
    project_id = await _create_project(client, test_data, admin_id)

    response = await client.post(
        "/api/v1/project-memberships/pm",
        json={"user_id": admin_id, "project_id": project_id, "project_role": "PM", "assigned_by_admin_id": admin_id},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_list_memberships_by_project(client, test_data, admin_id):
    project_id = await _create_project(client, test_data, admin_id)
    user_id = await _create_member_user(client, test_data, admin_id)
    created = await client.post(
        "/api/v1/project-memberships/pm",
        json={"user_id": user_id, "project_id": project_id, "project_role": "PM", "assigned_by_admin_id": admin_id},
    )
    membership_id = created.json()["membership_id"]

    response = await client.get("/api/v1/project-memberships/pm", params={"project_id": project_id})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["membership_id"] == membership_id
    # Endpoint join sẵn thông tin user (email/display_name)
    assert data[0]["user_id"] == user_id
    assert "display_name" in data[0]


@pytest.mark.asyncio
async def test_update_membership_role(client, test_data, admin_id):
    project_id = await _create_project(client, test_data, admin_id)
    user_id = await _create_member_user(client, test_data, admin_id)
    created = await client.post(
        "/api/v1/project-memberships/pm",
        json={"user_id": user_id, "project_id": project_id, "project_role": "PM", "assigned_by_admin_id": admin_id},
    )
    membership_id = created.json()["membership_id"]

    response = await client.patch(f"/api/v1/project-memberships/pm/{membership_id}", json={"project_role": "ENGINEER"})
    assert response.status_code == 200
    assert response.json()["project_role"] == "ENGINEER"


@pytest.mark.asyncio
async def test_deactivate_membership(client, test_data, admin_id):
    project_id = await _create_project(client, test_data, admin_id)
    user_id = await _create_member_user(client, test_data, admin_id)
    created = await client.post(
        "/api/v1/project-memberships/pm",
        json={"user_id": user_id, "project_id": project_id, "project_role": "PM", "assigned_by_admin_id": admin_id},
    )
    membership_id = created.json()["membership_id"]

    response = await client.delete(f"/api/v1/project-memberships/pm/{membership_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "INACTIVE"


@pytest.mark.asyncio
async def test_list_memberships_by_user(client, test_data, admin_id):
    project_id = await _create_project(client, test_data, admin_id)
    user_id = await _create_member_user(client, test_data, admin_id)
    await client.post(
        "/api/v1/project-memberships/pm",
        json={"user_id": user_id, "project_id": project_id, "project_role": "PM", "assigned_by_admin_id": admin_id},
    )

    response = await client.get(f"/api/v1/project-memberships/pm/by-user/{user_id}")
    assert response.status_code == 200
    project_ids = [m["project_id"] for m in response.json()]
    assert project_id in project_ids
