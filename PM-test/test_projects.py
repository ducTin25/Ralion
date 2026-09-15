import uuid

import pytest


def _unique_key() -> str:
    return f"TEST{uuid.uuid4().hex[:8].upper()}"


@pytest.mark.asyncio
async def test_create_project(client, test_data, admin_id):
    key = _unique_key()
    response = await client.post(
        "/api/v1/projects/pm",
        json={"key": key, "name": "Test Project", "created_by_admin_id": admin_id},
    )
    assert response.status_code == 201
    data = response.json()
    test_data.project_ids.append(data["project_id"])
    assert data["key"] == key
    assert data["name"] == "Test Project"
    assert data["status"] == "ACTIVE"
    assert data["created_by_admin_id"] == admin_id
    # Field mới từ nhánh develop (migration a1b2c3d4e5f6) — xác nhận default đúng
    assert data["sync_status"] == "NOT_STARTED"
    assert data["last_synced_at"] is None


@pytest.mark.asyncio
async def test_create_project_duplicate_key(client, test_data, admin_id):
    key = _unique_key()
    payload = {"key": key, "name": "Dup Project", "created_by_admin_id": admin_id}
    first = await client.post("/api/v1/projects/pm", json=payload)
    assert first.status_code == 201
    test_data.project_ids.append(first.json()["project_id"])

    second = await client.post("/api/v1/projects/pm", json=payload)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_list_projects(client, test_data, admin_id):
    key = _unique_key()
    created = await client.post(
        "/api/v1/projects/pm",
        json={"key": key, "name": "List Project", "created_by_admin_id": admin_id},
    )
    created_id = created.json()["project_id"]
    test_data.project_ids.append(created_id)

    response = await client.get("/api/v1/projects/pm", params={"limit": 200})
    assert response.status_code == 200
    ids = [p["project_id"] for p in response.json()]
    assert created_id in ids


@pytest.mark.asyncio
async def test_get_project_not_found(client):
    response = await client.get("/api/v1/projects/pm/999999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_project(client, test_data, admin_id):
    key = _unique_key()
    created = await client.post(
        "/api/v1/projects/pm",
        json={"key": key, "name": "Old Name", "created_by_admin_id": admin_id},
    )
    project_id = created.json()["project_id"]
    test_data.project_ids.append(project_id)

    response = await client.patch(f"/api/v1/projects/pm/{project_id}", json={"name": "New Name"})
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_archive_project(client, test_data, admin_id):
    key = _unique_key()
    created = await client.post(
        "/api/v1/projects/pm",
        json={"key": key, "name": "To Archive", "created_by_admin_id": admin_id},
    )
    project_id = created.json()["project_id"]
    test_data.project_ids.append(project_id)

    response = await client.delete(f"/api/v1/projects/pm/{project_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "ARCHIVED"
