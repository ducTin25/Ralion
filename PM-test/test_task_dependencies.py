"""Test Phase 2 — TaskDependency: validate cùng-version, không tự tham chiếu, phát hiện cycle
(SoT §17.2 mục 3.5 plan)."""

import uuid

import pytest


def _unique_key() -> str:
    return f"TEST{uuid.uuid4().hex[:8].upper()}"


async def _create_project_with_two_versions(client, test_data) -> tuple[int, int]:
    """Trả về (v1_id, v2_id) — 2 version DRAFT KHÁC NHAU cùng project, mỗi bản đều có task riêng
    (dùng để test guard 'phải cùng version')."""
    response = await client.post(
        "/api/v1/projects/pm",
        json={"key": _unique_key(), "name": "Dependency Test Project", "created_by_admin_id": 19},
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

    v2_response = await client.post("/api/v1/template-versions/pm", json={"template_id": template_id})
    v2_id = v2_response.json()["version_id"]
    await client.post(
        "/api/v1/template-tasks/pm",
        json={
            "version_id": v2_id,
            "category": "ORIENTATION",
            "title_pattern": "v2 task",
            "objective": "x",
            "instruction_template": "x",
            "estimated_minutes": 10,
        },
    )
    return v1_id, v2_id


@pytest.mark.asyncio
async def test_create_and_list_dependency(client, test_data):
    v1_id, _ = await _create_project_with_two_versions(client, test_data)
    tasks = (await client.get(f"/api/v1/template-tasks/pm/by-version/{v1_id}")).json()
    task_a, task_b = tasks[0], tasks[1]

    # Xoá dependency có sẵn giữa 2 task này (fork từ GLOBAL đã có chuỗi tuần tự) để test tạo mới sạch.
    existing = (await client.get(f"/api/v1/task-dependencies/pm/by-version/{v1_id}")).json()
    for dep in existing:
        await client.delete(f"/api/v1/task-dependencies/pm/{dep['dependency_id']}")

    response = await client.post(
        "/api/v1/task-dependencies/pm",
        json={"predecessor_task_id": task_a["template_task_id"], "successor_task_id": task_b["template_task_id"]},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["predecessor_task_id"] == task_a["template_task_id"]
    assert data["successor_task_id"] == task_b["template_task_id"]

    listed = (await client.get(f"/api/v1/task-dependencies/pm/by-version/{v1_id}")).json()
    assert data["dependency_id"] in [d["dependency_id"] for d in listed]


@pytest.mark.asyncio
async def test_create_dependency_rejects_self_reference(client, test_data):
    v1_id, _ = await _create_project_with_two_versions(client, test_data)
    tasks = (await client.get(f"/api/v1/template-tasks/pm/by-version/{v1_id}")).json()
    task_id = tasks[0]["template_task_id"]

    response = await client.post(
        "/api/v1/task-dependencies/pm",
        json={"predecessor_task_id": task_id, "successor_task_id": task_id},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_dependency_rejects_cross_version(client, test_data):
    v1_id, v2_id = await _create_project_with_two_versions(client, test_data)
    v1_task = (await client.get(f"/api/v1/template-tasks/pm/by-version/{v1_id}")).json()[0]
    v2_task = (await client.get(f"/api/v1/template-tasks/pm/by-version/{v2_id}")).json()[0]

    response = await client.post(
        "/api/v1/task-dependencies/pm",
        json={
            "predecessor_task_id": v1_task["template_task_id"],
            "successor_task_id": v2_task["template_task_id"],
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_dependency_rejects_cycle(client, test_data):
    v1_id, _ = await _create_project_with_two_versions(client, test_data)
    tasks = (await client.get(f"/api/v1/template-tasks/pm/by-version/{v1_id}")).json()
    task_a, task_b = tasks[0], tasks[1]

    existing = (await client.get(f"/api/v1/task-dependencies/pm/by-version/{v1_id}")).json()
    for dep in existing:
        await client.delete(f"/api/v1/task-dependencies/pm/{dep['dependency_id']}")

    forward = await client.post(
        "/api/v1/task-dependencies/pm",
        json={"predecessor_task_id": task_a["template_task_id"], "successor_task_id": task_b["template_task_id"]},
    )
    assert forward.status_code == 201

    backward = await client.post(
        "/api/v1/task-dependencies/pm",
        json={"predecessor_task_id": task_b["template_task_id"], "successor_task_id": task_a["template_task_id"]},
    )
    assert backward.status_code == 422


@pytest.mark.asyncio
async def test_create_dependency_rejects_duplicate(client, test_data):
    v1_id, _ = await _create_project_with_two_versions(client, test_data)
    existing = (await client.get(f"/api/v1/task-dependencies/pm/by-version/{v1_id}")).json()
    assert existing, "Global template fork phải có sẵn ít nhất 1 dependency"
    dep = existing[0]

    response = await client.post(
        "/api/v1/task-dependencies/pm",
        json={"predecessor_task_id": dep["predecessor_task_id"], "successor_task_id": dep["successor_task_id"]},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_delete_dependency(client, test_data):
    v1_id, _ = await _create_project_with_two_versions(client, test_data)
    existing = (await client.get(f"/api/v1/task-dependencies/pm/by-version/{v1_id}")).json()
    dep_id = existing[0]["dependency_id"]

    response = await client.delete(f"/api/v1/task-dependencies/pm/{dep_id}")
    assert response.status_code == 204

    remaining = (await client.get(f"/api/v1/task-dependencies/pm/by-version/{v1_id}")).json()
    assert dep_id not in [d["dependency_id"] for d in remaining]
