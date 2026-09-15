"""Test route read-only cho OnboardingPlan (mục 3.2 docs/PM/Phase-1/plan-phase1-v2-rescope.md).

Chưa có API tạo OnboardingPlan/TemplateVersion (thuộc Phase 2/4), nên test tự insert thẳng qua
ORM để dựng dữ liệu — không phải hành vi nghiệp vụ thật, chỉ để có data cho route đọc.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select

from src.model.enums import PlanStatus
from src.model.onboarding_plan import OnboardingPlan
from src.model.session import AsyncSessionLocal
from src.model.template_version import TemplateVersion


def _unique_key() -> str:
    return f"TEST{uuid.uuid4().hex[:8].upper()}"


async def _create_project(client, test_data, admin_id: int) -> int:
    response = await client.post(
        "/api/v1/projects/pm",
        json={"key": _unique_key(), "name": "Onboarding Plan Test Project", "created_by_admin_id": admin_id},
    )
    assert response.status_code == 201
    project_id = response.json()["project_id"]
    test_data.project_ids.append(project_id)
    return project_id


async def _create_engineer_membership(client, test_data, project_id: int, admin_id: int) -> int:
    email = f"test-member-{uuid.uuid4().hex[:8]}@onboarding.dev"
    user_response = await client.post(
        "/api/v1/users",
        headers={"X-User-Id": str(admin_id)},
        json={"email": email, "display_name": "Test Engineer", "created_by_admin_id": admin_id},
    )
    assert user_response.status_code == 201
    user_id = user_response.json()["user_id"]
    test_data.user_ids.append(user_id)

    membership_response = await client.post(
        "/api/v1/project-memberships/pm",
        json={"user_id": user_id, "project_id": project_id, "project_role": "ENGINEER", "assigned_by_admin_id": admin_id},
    )
    assert membership_response.status_code == 201
    return membership_response.json()["membership_id"]


class _PlanDataTracker:
    def __init__(self) -> None:
        self.plan_ids: list[int] = []
        self.template_version_ids: list[int] = []


@pytest_asyncio.fixture
async def plan_data(test_data):
    """Dọn dẹp OnboardingPlan/TemplateVersion test tự tạo. Phụ thuộc `test_data` để teardown
    chạy TRƯỚC (LIFO) teardown của test_data — xoá plan trước khi xoá membership. Không tự tạo/xoá
    OnboardingTemplate nữa (từ Phase 2, project_service.create_project tự fork sẵn 1 template —
    xem `_create_template_version` bên dưới); template đó được conftest.py's `test_data` dọn theo
    project_id."""
    tracker = _PlanDataTracker()
    yield tracker

    if not (tracker.plan_ids or tracker.template_version_ids):
        return

    async with AsyncSessionLocal() as db:
        if tracker.plan_ids:
            await db.execute(delete(OnboardingPlan).where(OnboardingPlan.plan_id.in_(tracker.plan_ids)))
        if tracker.template_version_ids:
            await db.execute(
                delete(TemplateVersion).where(TemplateVersion.version_id.in_(tracker.template_version_ids))
            )
        await db.commit()


async def _create_template_version(client, plan_data, project_id: int) -> int:
    """Tạo thêm 1 version rỗng (version_no kế tiếp) trên template mà project đã tự có sẵn từ
    lúc tạo (Phase 2) — KHÔNG tạo OnboardingTemplate mới, vì mỗi project chỉ được có đúng 1
    template (UniqueConstraint("project_id"))."""
    template_response = await client.get(f"/api/v1/onboarding-templates/pm/by-project/{project_id}")
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]

    async with AsyncSessionLocal() as db:
        max_no = await db.scalar(
            select(func.max(TemplateVersion.version_no)).where(TemplateVersion.template_id == template_id)
        )
        version = TemplateVersion(template_id=template_id, version_no=(max_no or 0) + 1)
        db.add(version)
        await db.commit()
        await db.refresh(version)
        plan_data.template_version_ids.append(version.version_id)
        return version.version_id


async def _create_plan(plan_data, membership_id: int, template_version_id: int, status: PlanStatus) -> int:
    async with AsyncSessionLocal() as db:
        plan = OnboardingPlan(membership_id=membership_id, template_version_id=template_version_id, status=status)
        db.add(plan)
        await db.commit()
        await db.refresh(plan)
        plan_data.plan_ids.append(plan.plan_id)
        return plan.plan_id


@pytest.mark.asyncio
async def test_get_plan_by_membership_not_found(client):
    response = await client.get("/api/v1/onboarding-plans/pm/by-membership/999999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_plan_by_membership_found(client, test_data, plan_data, admin_id):
    project_id = await _create_project(client, test_data, admin_id)
    membership_id = await _create_engineer_membership(client, test_data, project_id, admin_id)
    version_id = await _create_template_version(client, plan_data, project_id)
    plan_id = await _create_plan(plan_data, membership_id, version_id, PlanStatus.ACTIVE)

    response = await client.get(f"/api/v1/onboarding-plans/pm/by-membership/{membership_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["plan_id"] == plan_id
    assert data["membership_id"] == membership_id
    assert data["status"] == "ACTIVE"
    assert data["template_version_id"] == version_id


@pytest.mark.asyncio
async def test_list_plans_by_project_only_returns_members_with_plan(client, test_data, plan_data, admin_id):
    """Membership nào chưa có Plan thì KHÔNG xuất hiện trong response — FE tự suy ra
    "chưa có Plan" từ việc thiếu mặt trong list (đúng thiết kế mục 3.2 của plan v2)."""
    project_id = await _create_project(client, test_data, admin_id)
    membership_with_plan = await _create_engineer_membership(client, test_data, project_id, admin_id)
    membership_without_plan = await _create_engineer_membership(client, test_data, project_id, admin_id)
    version_id = await _create_template_version(client, plan_data, project_id)
    await _create_plan(plan_data, membership_with_plan, version_id, PlanStatus.DRAFT)

    response = await client.get(f"/api/v1/onboarding-plans/pm/by-project/{project_id}")
    assert response.status_code == 200
    data = response.json()
    membership_ids = [p["membership_id"] for p in data]
    assert membership_with_plan in membership_ids
    assert membership_without_plan not in membership_ids


@pytest.mark.asyncio
async def test_list_plans_by_project_empty_when_no_plans(client, test_data, admin_id):
    project_id = await _create_project(client, test_data, admin_id)
    await _create_engineer_membership(client, test_data, project_id, admin_id)

    response = await client.get(f"/api/v1/onboarding-plans/pm/by-project/{project_id}")
    assert response.status_code == 200
    assert response.json() == []
