"""Test Phase 2 — TemplateTask: CRUD chỉ cho phép khi version DRAFT, hard-delete thật, reorder
validate đúng/đủ tập task_id (SoT §11.22)."""

import uuid

import pytest


def _unique_key() -> str:
    return f"TEST{uuid.uuid4().hex[:8].upper()}"


async def _create_project_with_versions(client, test_data) -> tuple[int, int]:
    """Trả về (draft_version_id, approved_version_id) — draft có sẵn task fork từ GLOBAL."""
    response = await client.post(
        "/api/v1/projects/pm",
        json={"key": _unique_key(), "name": "Task Test Project", "created_by_admin_id": 19},
    )
    assert response.status_code == 201
    project_id = response.json()["project_id"]
    test_data.project_ids.append(project_id)

    template_id = (
        await client.get(f"/api/v1/onboarding-templates/pm/by-project/{project_id}")
    ).json()["template_id"]
    v1_id = (
        await client.get(f"/api/v1/template-versions/pm/by-template/{template_id}")
    ).json()[0]["version_id"]
    return project_id, v1_id


@pytest.mark.asyncio
async def test_create_and_list_task(client, test_data):
    _, v1_id = await _create_project_with_versions(client, test_data)

    response = await client.post(
        "/api/v1/template-tasks/pm",
        json={
            "version_id": v1_id,
            "category": "ORIENTATION",
            "title_pattern": "Test task mới",
            "objective": "Test objective",
            "instruction_template": "Test instruction",
            "mandatory": True,
            "estimated_minutes": 30,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title_pattern"] == "Test task mới"
    assert data["display_order"] > 0

    tasks = (await client.get(f"/api/v1/template-tasks/pm/by-version/{v1_id}")).json()
    assert data["template_task_id"] in [t["template_task_id"] for t in tasks]
    # Task mới phải nối vào cuối, không trùng display_order với task nào có sẵn (unique constraint)
    assert data["display_order"] == max(t["display_order"] for t in tasks)


@pytest.mark.asyncio
async def test_update_task(client, test_data):
    _, v1_id = await _create_project_with_versions(client, test_data)
    tasks = (await client.get(f"/api/v1/template-tasks/pm/by-version/{v1_id}")).json()
    task_id = tasks[0]["template_task_id"]

    response = await client.patch(f"/api/v1/template-tasks/pm/{task_id}", json={"title_pattern": "Đã sửa"})
    assert response.status_code == 200
    assert response.json()["title_pattern"] == "Đã sửa"


@pytest.mark.asyncio
async def test_delete_task_is_hard_delete(client, test_data):
    _, v1_id = await _create_project_with_versions(client, test_data)
    tasks = (await client.get(f"/api/v1/template-tasks/pm/by-version/{v1_id}")).json()
    task_id = tasks[0]["template_task_id"]

    response = await client.delete(f"/api/v1/template-tasks/pm/{task_id}")
    assert response.status_code == 204

    remaining = (await client.get(f"/api/v1/template-tasks/pm/by-version/{v1_id}")).json()
    assert task_id not in [t["template_task_id"] for t in remaining]


@pytest.mark.asyncio
async def test_cannot_modify_task_when_version_not_draft(client, test_data):
    _, v1_id = await _create_project_with_versions(client, test_data)
    tasks = (await client.get(f"/api/v1/template-tasks/pm/by-version/{v1_id}")).json()
    task_id = tasks[0]["template_task_id"]

    approve = await client.patch(f"/api/v1/template-versions/pm/{v1_id}/approve")
    assert approve.status_code == 200

    update_response = await client.patch(f"/api/v1/template-tasks/pm/{task_id}", json={"title_pattern": "x"})
    assert update_response.status_code == 409

    delete_response = await client.delete(f"/api/v1/template-tasks/pm/{task_id}")
    assert delete_response.status_code == 409

    create_response = await client.post(
        "/api/v1/template-tasks/pm",
        json={
            "version_id": v1_id,
            "category": "ORIENTATION",
            "title_pattern": "x",
            "objective": "x",
            "instruction_template": "x",
            "estimated_minutes": 10,
        },
    )
    assert create_response.status_code == 409


@pytest.mark.asyncio
async def test_reorder_tasks(client, test_data):
    _, v1_id = await _create_project_with_versions(client, test_data)
    tasks = (await client.get(f"/api/v1/template-tasks/pm/by-version/{v1_id}")).json()
    task_ids = [t["template_task_id"] for t in tasks]
    reversed_ids = list(reversed(task_ids))

    response = await client.patch(
        "/api/v1/template-tasks/pm/reorder",
        json={"version_id": v1_id, "ordered_template_task_ids": reversed_ids},
    )
    assert response.status_code == 200
    reordered = response.json()
    reordered_sorted = sorted(reordered, key=lambda t: t["display_order"])
    assert [t["template_task_id"] for t in reordered_sorted] == reversed_ids


@pytest.mark.asyncio
async def test_reorder_rejects_incomplete_task_set(client, test_data):
    _, v1_id = await _create_project_with_versions(client, test_data)
    tasks = (await client.get(f"/api/v1/template-tasks/pm/by-version/{v1_id}")).json()
    task_ids = [t["template_task_id"] for t in tasks][:-1]  # thiếu 1 task

    response = await client.patch(
        "/api/v1/template-tasks/pm/reorder",
        json={"version_id": v1_id, "ordered_template_task_ids": task_ids},
    )
    assert response.status_code == 422
