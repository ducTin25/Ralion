"""Test Phase 2 — TemplateVersion: tạo version (sao chép/trống), duyệt version (validate trước
duyệt + archive version cũ khi duyệt version mới), theo SoT §17.2/§24.1."""

import uuid

import pytest
from sqlalchemy import select

from src.model.session import AsyncSessionLocal
from src.model.task_dependency import TaskDependency
from src.model.template_task import TemplateTask


def _unique_key() -> str:
    return f"TEST{uuid.uuid4().hex[:8].upper()}"


async def _create_project_with_template(client, test_data) -> tuple[int, int, int]:
    """Trả về (project_id, template_id, v1_version_id) — v1 luôn DRAFT, đã có sẵn task fork từ GLOBAL."""
    response = await client.post(
        "/api/v1/projects/pm",
        json={"key": _unique_key(), "name": "Version Test Project", "created_by_admin_id": 19},
    )
    assert response.status_code == 201
    project_id = response.json()["project_id"]
    test_data.project_ids.append(project_id)

    template_response = await client.get(f"/api/v1/onboarding-templates/pm/by-project/{project_id}")
    template_id = template_response.json()["template_id"]

    versions_response = await client.get(f"/api/v1/template-versions/pm/by-template/{template_id}")
    v1_id = versions_response.json()[0]["version_id"]
    return project_id, template_id, v1_id


@pytest.mark.asyncio
async def test_create_version_clone_copies_tasks_and_dependencies(client, test_data):
    _, template_id, v1_id = await _create_project_with_template(client, test_data)

    v1_tasks = (await client.get(f"/api/v1/template-tasks/pm/by-version/{v1_id}")).json()
    v1_deps = (await client.get(f"/api/v1/task-dependencies/pm/by-version/{v1_id}")).json()
    assert len(v1_tasks) > 0
    assert len(v1_deps) > 0, "Global template có dependency chuỗi tuần tự — fork/clone phải giữ lại"

    response = await client.post(
        "/api/v1/template-versions/pm", json={"template_id": template_id, "clone_from_version_id": v1_id}
    )
    assert response.status_code == 201
    v2 = response.json()
    assert v2["version_no"] == 2
    assert v2["status"] == "DRAFT"

    v2_tasks = (await client.get(f"/api/v1/template-tasks/pm/by-version/{v2['version_id']}")).json()
    v2_deps = (await client.get(f"/api/v1/task-dependencies/pm/by-version/{v2['version_id']}")).json()
    assert len(v2_tasks) == len(v1_tasks)
    assert len(v2_deps) == len(v1_deps)
    # Task ID phải khác (bản sao thật, không phải tham chiếu lại v1)
    assert {t["template_task_id"] for t in v2_tasks}.isdisjoint({t["template_task_id"] for t in v1_tasks})


@pytest.mark.asyncio
async def test_create_version_empty(client, test_data):
    _, template_id, _ = await _create_project_with_template(client, test_data)

    response = await client.post("/api/v1/template-versions/pm", json={"template_id": template_id})
    assert response.status_code == 201
    assert response.json()["version_no"] == 2

    tasks = (await client.get(f"/api/v1/template-tasks/pm/by-version/{response.json()['version_id']}")).json()
    assert tasks == []


@pytest.mark.asyncio
async def test_approve_version_golden_path(client, test_data):
    project_id, template_id, v1_id = await _create_project_with_template(client, test_data)

    response = await client.patch(f"/api/v1/template-versions/pm/{v1_id}/approve")
    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"

    template = await client.get(f"/api/v1/onboarding-templates/pm/{template_id}")
    assert template.json()["status"] == "APPROVED"


@pytest.mark.asyncio
async def test_approve_version_archives_previous_approved(client, test_data):
    project_id, template_id, v1_id = await _create_project_with_template(client, test_data)
    await client.patch(f"/api/v1/template-versions/pm/{v1_id}/approve")

    v2_response = await client.post(
        "/api/v1/template-versions/pm", json={"template_id": template_id, "clone_from_version_id": v1_id}
    )
    v2_id = v2_response.json()["version_id"]

    approve_v2 = await client.patch(f"/api/v1/template-versions/pm/{v2_id}/approve")
    assert approve_v2.status_code == 200
    assert approve_v2.json()["status"] == "APPROVED"

    v1_after = await client.get(f"/api/v1/template-versions/pm/{v1_id}")
    assert v1_after.json()["status"] == "ARCHIVED"


@pytest.mark.asyncio
async def test_approve_archived_version_reactivates_it_in_place(client, test_data):
    """Duyệt lại 1 version đã ARCHIVED — chỉ đổi status về APPROVED, KHÔNG tạo version mới
    (quyết định sản phẩm: đơn giản hơn kiểu nhân bản-rồi-duyệt-bản-sao)."""
    _, template_id, v1_id = await _create_project_with_template(client, test_data)
    await client.patch(f"/api/v1/template-versions/pm/{v1_id}/approve")

    v2_response = await client.post(
        "/api/v1/template-versions/pm", json={"template_id": template_id, "clone_from_version_id": v1_id}
    )
    v2_id = v2_response.json()["version_id"]
    await client.patch(f"/api/v1/template-versions/pm/{v2_id}/approve")

    v1_before = await client.get(f"/api/v1/template-versions/pm/{v1_id}")
    assert v1_before.json()["status"] == "ARCHIVED"

    reactivate = await client.patch(f"/api/v1/template-versions/pm/{v1_id}/approve")
    assert reactivate.status_code == 200
    assert reactivate.json()["version_id"] == v1_id
    assert reactivate.json()["status"] == "APPROVED"

    v2_after = await client.get(f"/api/v1/template-versions/pm/{v2_id}")
    assert v2_after.json()["status"] == "ARCHIVED"

    versions = (await client.get(f"/api/v1/template-versions/pm/by-template/{template_id}")).json()
    assert len(versions) == 2, "Duyệt lại không được tạo thêm version mới nào"


@pytest.mark.asyncio
async def test_approve_version_fails_when_no_tasks(client, test_data):
    _, template_id, _ = await _create_project_with_template(client, test_data)
    empty_version = (
        await client.post("/api/v1/template-versions/pm", json={"template_id": template_id})
    ).json()

    response = await client.patch(f"/api/v1/template-versions/pm/{empty_version['version_id']}/approve")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_approve_version_fails_when_not_draft(client, test_data):
    _, _, v1_id = await _create_project_with_template(client, test_data)
    first = await client.patch(f"/api/v1/template-versions/pm/{v1_id}/approve")
    assert first.status_code == 200

    second = await client.patch(f"/api/v1/template-versions/pm/{v1_id}/approve")
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_approve_version_fails_on_cycle(client, test_data):
    """Cycle không thể tạo qua API bình thường (create_dependency đã chặn) — chèn thẳng qua ORM
    để xác nhận approve_version có validate phòng thủ ở tầng service (SoT §17.2), không chỉ dựa
    vào việc chặn từ lúc tạo dependency."""
    _, _, v1_id = await _create_project_with_template(client, test_data)

    async with AsyncSessionLocal() as db:
        tasks_result = await db.execute(
            select(TemplateTask).where(TemplateTask.version_id == v1_id).order_by(TemplateTask.display_order).limit(2)
        )
        task_a, task_b = tasks_result.scalars().all()
        # Chèn CẢ HAI chiều để chắc chắn có chu trình, thay vì dựa vào việc template fork sẵn có
        # cạnh A->B giữa đúng 2 task đầu danh sách — giả định đó vỡ mỗi khi thứ tự task ở Master
        # Template đổi (vd thêm nhóm COMPANY lên đầu).
        db.add(TaskDependency(predecessor_task_id=task_a.template_task_id, successor_task_id=task_b.template_task_id))
        db.add(TaskDependency(predecessor_task_id=task_b.template_task_id, successor_task_id=task_a.template_task_id))
        await db.commit()

    response = await client.patch(f"/api/v1/template-versions/pm/{v1_id}/approve")
    assert response.status_code == 422
