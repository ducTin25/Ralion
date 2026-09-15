"""Test Phase 2 — OnboardingTemplate: mỗi project tự có 1 Project Template (fork từ GLOBAL) ngay
khi tạo (SoT §11.16, §17.2), báo lỗi rõ ràng nếu thiếu GLOBAL thay vì tạo template rỗng."""

import uuid

import pytest
from sqlalchemy import select

from src.model.enums import TemplateScope, TemplateStatus
from src.model.onboarding_template import OnboardingTemplate
from src.model.session import AsyncSessionLocal


def _unique_key() -> str:
    return f"TEST{uuid.uuid4().hex[:8].upper()}"


async def _create_project(client, test_data) -> int:
    response = await client.post(
        "/api/v1/projects/pm",
        json={"key": _unique_key(), "name": "Template Test Project", "created_by_admin_id": 19},
    )
    assert response.status_code == 201
    project_id = response.json()["project_id"]
    test_data.project_ids.append(project_id)
    return project_id


@pytest.mark.asyncio
async def test_create_project_auto_creates_project_template(client, test_data):
    """Golden path SoT §11.16: tạo project xong là có ngay 1 Project Template DRAFT, fork đủ
    task từ GLOBAL — không có bước 'tạo template' riêng nào."""
    project_id = await _create_project(client, test_data)

    response = await client.get(f"/api/v1/onboarding-templates/pm/by-project/{project_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == project_id
    assert data["scope"] == "PROJECT"
    assert data["status"] == "DRAFT"
    assert data["source_template_id"] is not None

    versions_response = await client.get(f"/api/v1/template-versions/pm/by-template/{data['template_id']}")
    assert versions_response.status_code == 200
    versions = versions_response.json()
    assert len(versions) == 1
    assert versions[0]["version_no"] == 1
    assert versions[0]["status"] == "DRAFT"

    tasks_response = await client.get(f"/api/v1/template-tasks/pm/by-version/{versions[0]['version_id']}")
    assert tasks_response.status_code == 200
    tasks = tasks_response.json()
    assert len(tasks) > 0
    categories = {t["category"] for t in tasks}
    # Đúng 5 category chuẩn khớp 5 giá trị đầu của DocumentCategory (OVERVIEW/ARCHITECTURE/SETUP/
    # ACCESS_SECURITY/CODEBASE_GUIDE) — CONVENTION/FIRST_TASK/FIRST_PR đã rút khỏi Master Template
    # (mở rộng làm sau, xem scripts/reshape_template_task_categories.py).
    assert categories == {
        # 1 nhóm công ty (đọc chính sách chung, domain POLICY) + 5 nhóm dự án khớp 5 giá trị đầu
        # của DocumentCategory — đúng cấu trúc "1 phần công ty + 5 phần dự án" của lộ trình chuẩn.
        "COMPANY",
        "ORIENTATION",
        "ARCHITECTURE",
        "ACCESS",
        "SETUP",
        "CODEBASE",
    }


@pytest.mark.asyncio
async def test_create_project_fails_when_global_template_missing(client, test_data):
    """SoT §11.16: thiếu GLOBAL template APPROVED thì tạo project phải lỗi rõ ràng (422), không
    được tạo project với template rỗng. Tạm chuyển GLOBAL sang NEEDS_REVIEW rồi phục hồi lại
    ngay sau test — dùng DB thật dùng chung nên phải đảm bảo phục hồi kể cả khi assert fail."""
    async with AsyncSessionLocal() as db:
        global_template = await db.scalar(
            select(OnboardingTemplate).where(OnboardingTemplate.scope == TemplateScope.GLOBAL)
        )
        assert global_template is not None, "Cần seed GLOBAL template trước (scripts/seed_dev_data.py)"
        global_template_id = global_template.template_id
        global_template.status = TemplateStatus.NEEDS_REVIEW
        await db.commit()

    try:
        response = await client.post(
            "/api/v1/projects/pm",
            json={"key": _unique_key(), "name": "Should Fail", "created_by_admin_id": 19},
        )
        assert response.status_code == 422
    finally:
        async with AsyncSessionLocal() as db:
            global_template = await db.get(OnboardingTemplate, global_template_id)
            global_template.status = TemplateStatus.APPROVED
            await db.commit()


@pytest.mark.asyncio
async def test_manual_create_template_rejects_project_that_already_has_one(client, test_data):
    """POST /onboarding-templates/pm chỉ dùng cho backfill — project đã có template (luôn đúng
    từ Phase 2) thì phải 409, không tạo thêm bản thứ 2 (UniqueConstraint("project_id"))."""
    project_id = await _create_project(client, test_data)

    response = await client.post("/api/v1/onboarding-templates/pm", json={"project_id": project_id})
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_manual_create_template_404_when_project_not_found(client):
    response = await client.post("/api/v1/onboarding-templates/pm", json={"project_id": 999999})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_template_by_project_not_found(client):
    response = await client.get("/api/v1/onboarding-templates/pm/by-project/999999")
    assert response.status_code == 404
