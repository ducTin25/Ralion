"""Test cho 4 tính năng PM thêm ngày 15/08: đính kèm minh chứng blocker, thứ tự blocker theo thời
gian, xem tiến độ 1 Engineer, và trang Tổng quan dự án (Dashboard).

Dùng chung quy ước với `test_plan_generation.py`: AI tắt qua fixture autouse (không cần ở đây vì
các test này không đụng bước sinh nội dung AI), gọi thẳng qua HTTP client thật, dọn dữ liệu qua
`test_data` tracker có sẵn trong `conftest.py`.
"""

import base64
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select

from src.model.blocker import Blocker
from src.model.blocker_attachment import BlockerAttachment
from src.model.plan_task import PlanTask
from src.model.session import AsyncSessionLocal
from src.model.template_task import TemplateTask

PM_USER_ID = 19  # user seed sẵn, system_role=ADMIN -> require_project_member() tự cho qua

# Test upload thật lên Cloudinary (quy ước cả repo, không mock storage_service) -> Cloudinary
# validate nội dung thật, chuỗi byte tuỳ ý bị từ chối ("Invalid image file"). Đây là PNG 1x1 pixel
# trong suốt hợp lệ tối thiểu.
_MINIMAL_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _unique_key() -> str:
    import uuid

    return f"TEST{uuid.uuid4().hex[:8].upper()}"


async def _create_project(client, test_data) -> int:
    response = await client.post(
        "/api/v1/projects/pm",
        json={"key": _unique_key(), "name": "PM Progress Test", "created_by_admin_id": PM_USER_ID},
    )
    assert response.status_code == 201
    project_id = response.json()["project_id"]
    test_data.project_ids.append(project_id)
    return project_id


async def _create_engineer(client, test_data, project_id: int) -> tuple[int, int]:
    """Trả về (membership_id, user_id)."""
    import uuid

    email = f"test-eng-{uuid.uuid4().hex[:8]}@onboarding.dev"
    user_response = await client.post(
        "/api/v1/users",
        headers={"X-User-Id": str(PM_USER_ID)},
        json={"email": email, "display_name": "Progress Engineer", "created_by_admin_id": PM_USER_ID},
    )
    assert user_response.status_code == 201
    user_id = user_response.json()["user_id"]
    test_data.user_ids.append(user_id)

    membership_response = await client.post(
        "/api/v1/project-memberships/pm",
        json={
            "user_id": user_id,
            "project_id": project_id,
            "project_role": "ENGINEER",
            "assigned_by_admin_id": PM_USER_ID,
        },
    )
    assert membership_response.status_code == 201
    return membership_response.json()["membership_id"], user_id


async def _approve_template(client, project_id: int) -> int:
    template_response = await client.get(f"/api/v1/onboarding-templates/pm/by-project/{project_id}")
    template_id = template_response.json()["template_id"]
    versions = (await client.get(f"/api/v1/template-versions/pm/by-template/{template_id}")).json()
    version_id = versions[0]["version_id"]
    approve = await client.patch(f"/api/v1/template-versions/pm/{version_id}/approve")
    assert approve.status_code == 200, approve.text
    return version_id


async def _generate_and_approve_plan(client, project_id: int, membership_id: int) -> tuple[int, int]:
    """Sinh + duyệt plan cho 1 Engineer (bản chuẩn trước, rồi cấp cho Engineer) — trả về
    (plan_id, plan_task_id của task đầu tiên)."""
    reference = await client.post(
        "/api/v1/onboarding-plans/pm/reference/generate", json={"project_id": project_id}
    )
    assert reference.status_code == 202, reference.text
    reference_job = (
        await client.get(f"/api/v1/onboarding-plans/pm/generate/{reference.json()['job_id']}")
    ).json()
    assert reference_job["status"] == "DONE", reference_job["error"]

    generate = await client.post(
        "/api/v1/onboarding-plans/pm/generate", json={"membership_id": membership_id}
    )
    assert generate.status_code == 202, generate.text
    job = (await client.get(f"/api/v1/onboarding-plans/pm/generate/{generate.json()['job_id']}")).json()
    assert job["status"] == "DONE", job["error"]
    plan_id = job["plan_id"]

    approve = await client.patch(
        f"/api/v1/onboarding-plans/pm/{plan_id}/approve", json={"approved_by_user_id": PM_USER_ID}
    )
    assert approve.status_code == 200, approve.text

    tasks = (await client.get(f"/api/v1/onboarding-plans/pm/{plan_id}/tasks")).json()
    return plan_id, tasks[0]["plan_task_id"]


@pytest_asyncio.fixture
async def project_with_approved_plan(client, test_data):
    project_id = await _create_project(client, test_data)
    await _approve_template(client, project_id)
    membership_id, user_id = await _create_engineer(client, test_data, project_id)
    plan_id, plan_task_id = await _generate_and_approve_plan(client, project_id, membership_id)
    return {
        "project_id": project_id,
        "membership_id": membership_id,
        "user_id": user_id,
        "plan_id": plan_id,
        "plan_task_id": plan_task_id,
    }


# --- 1. Đính kèm minh chứng blocker -----------------------------------------------------------


@pytest.mark.asyncio
async def test_create_blocker_with_image_attachment_persists_and_pm_sees_it(
    client, project_with_approved_plan
):
    """UC-08: kỹ sư báo blocker kèm ảnh minh chứng -> lưu Object Storage, PM cùng dự án thấy được."""
    fixture = project_with_approved_plan
    response = await client.post(
        f"/api/v1/member/plan-tasks/{fixture['plan_task_id']}/blockers",
        headers={"X-User-Id": str(fixture["user_id"])},
        data={"category": "SETUP", "reason": "May cong ty loi mang, khong cai duoc dependency."},
        # Cloudinary validate nội dung thật (resource_type=auto), không chấp nhận byte giả —
        # phải là 1 PNG hợp lệ tối thiểu (1x1 pixel, decode từ base64) chứ không phải chuỗi bất kỳ.
        files=[("attachments", ("loi-mang.png", _MINIMAL_PNG_BYTES, "image/png"))],
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert len(body["attachments"]) == 1
    assert body["attachments"][0]["file_name"] == "loi-mang.png"
    assert body["attachments"][0]["mime_type"] == "image/png"
    assert body["attachments"][0]["url"].startswith("http"), "Phải là URL Object Storage thật"

    pm_list = await client.get(
        f"/api/v1/pm/projects/{fixture['project_id']}/blockers",
        headers={"X-User-Id": str(PM_USER_ID)},
    )
    assert pm_list.status_code == 200
    [seen] = pm_list.json()
    assert len(seen["attachments"]) == 1
    assert seen["attachments"][0]["url"] == body["attachments"][0]["url"]

    async with AsyncSessionLocal() as db:
        rows = list((await db.scalars(select(BlockerAttachment))).all())
        assert any(r.file_name == "loi-mang.png" for r in rows)


@pytest.mark.asyncio
async def test_create_blocker_without_attachment_still_works(client, project_with_approved_plan):
    """Đính kèm là TUỲ CHỌN (UC-08) — không gửi file vẫn phải tạo được blocker bình thường."""
    fixture = project_with_approved_plan
    response = await client.post(
        f"/api/v1/member/plan-tasks/{fixture['plan_task_id']}/blockers",
        headers={"X-User-Id": str(fixture["user_id"])},
        data={"category": "TECHNICAL", "reason": "Loi khong ro nguyen nhan, can ho tro."},
    )
    assert response.status_code == 201, response.text
    assert response.json()["attachments"] == []


@pytest.mark.asyncio
async def test_create_blocker_rejects_non_image_video_attachment(client, project_with_approved_plan):
    fixture = project_with_approved_plan
    response = await client.post(
        f"/api/v1/member/plan-tasks/{fixture['plan_task_id']}/blockers",
        headers={"X-User-Id": str(fixture["user_id"])},
        data={"category": "OTHER", "reason": "Dinh kem nham dinh dang de kiem tra validate."},
        files=[("attachments", ("secret.txt", b"not an image", "text/plain"))],
    )
    assert response.status_code == 422
    async with AsyncSessionLocal() as db:
        count = await db.scalar(select(Blocker).where(Blocker.reason.contains("Dinh kem nham")))
        assert count is None, "Không được tạo blocker khi file đính kèm không hợp lệ"


@pytest.mark.asyncio
async def test_create_blocker_rejects_too_many_attachments(client, project_with_approved_plan):
    fixture = project_with_approved_plan
    files = [
        ("attachments", (f"anh-{i}.png", b"fake png bytes", "image/png")) for i in range(6)
    ]
    response = await client.post(
        f"/api/v1/member/plan-tasks/{fixture['plan_task_id']}/blockers",
        headers={"X-User-Id": str(fixture["user_id"])},
        data={"category": "OTHER", "reason": "Qua nhieu file dinh kem de kiem tra gioi han."},
        files=files,
    )
    assert response.status_code == 422


# --- 2. Blocker sắp xếp theo thời gian (cũ nhất trước) -----------------------------------------


@pytest.mark.asyncio
async def test_pm_blockers_sorted_oldest_first(client, project_with_approved_plan):
    """PM xử lý theo FIFO — blocker báo TRƯỚC phải đứng ĐẦU danh sách, không phải blocker mới nhất."""
    fixture = project_with_approved_plan
    async with AsyncSessionLocal() as db:
        now = datetime.now(UTC).replace(tzinfo=None)
        older = Blocker(
            plan_task_id=fixture["plan_task_id"],
            reported_by_membership_id=fixture["membership_id"],
            category="TECHNICAL",
            reason="Bao truoc, phai xep dau danh sach cho PM.",
            status="OPEN",
            reported_at=now - timedelta(hours=2),
        )
        newer = Blocker(
            plan_task_id=fixture["plan_task_id"],
            reported_by_membership_id=fixture["membership_id"],
            category="TECHNICAL",
            reason="Bao sau, phai xep sau danh sach cho PM.",
            status="OPEN",
            reported_at=now - timedelta(minutes=5),
        )
        db.add_all([older, newer])
        await db.commit()

    response = await client.get(
        f"/api/v1/pm/projects/{fixture['project_id']}/blockers",
        headers={"X-User-Id": str(PM_USER_ID)},
    )
    assert response.status_code == 200
    reasons = [b["reason"] for b in response.json()]
    assert reasons.index("Bao truoc, phai xep dau danh sach cho PM.") < reasons.index(
        "Bao sau, phai xep sau danh sach cho PM."
    )


# --- 3. Xem tiến độ 1 thành viên ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_member_progress_shows_overdue_task_and_blocker(client, project_with_approved_plan):
    fixture = project_with_approved_plan

    async with AsyncSessionLocal() as db:
        task = await db.get(PlanTask, fixture["plan_task_id"])
        task.due_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
        db.add(
            Blocker(
                plan_task_id=fixture["plan_task_id"],
                reported_by_membership_id=fixture["membership_id"],
                category="TECHNICAL",
                reason="Blocker de kiem tra man hinh tien do PM.",
                status="OPEN",
            )
        )
        await db.commit()

    response = await client.get(
        f"/api/v1/pm/projects/{fixture['project_id']}/members/{fixture['membership_id']}/progress",
        headers={"X-User-Id": str(PM_USER_ID)},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["plan_id"] == fixture["plan_id"]
    assert body["overdue_count"] >= 1
    overdue_task = next(t for t in body["tasks"] if t["plan_task_id"] == fixture["plan_task_id"])
    assert overdue_task["is_overdue"] is True
    assert len(body["blockers"]) == 1
    assert body["blockers"][0]["reason"] == "Blocker de kiem tra man hinh tien do PM."


@pytest.mark.asyncio
async def test_member_progress_percent_matches_mandatory_completion(client, project_with_approved_plan):
    fixture = project_with_approved_plan

    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(PlanTask, TemplateTask.mandatory)
                .join(TemplateTask, TemplateTask.template_task_id == PlanTask.template_task_id)
                .where(PlanTask.plan_id == fixture["plan_id"])
            )
        ).all()
        mandatory_tasks = [task for task, mandatory in rows if mandatory]
        assert mandatory_tasks, "Fixture template phải có ít nhất 1 task bắt buộc để kiểm"
        mandatory_tasks[0].status = "DONE"
        await db.commit()
        expected_percent = round(100 / len(mandatory_tasks))

    response = await client.get(
        f"/api/v1/pm/projects/{fixture['project_id']}/members/{fixture['membership_id']}/progress",
        headers={"X-User-Id": str(PM_USER_ID)},
    )
    assert response.status_code == 200
    assert response.json()["percent"] == expected_percent
    assert response.json()["completed_count"] == 1


@pytest.mark.asyncio
async def test_member_progress_rejects_membership_from_other_project(client, test_data, project_with_approved_plan):
    fixture = project_with_approved_plan
    other_project_id = await _create_project(client, test_data)

    response = await client.get(
        f"/api/v1/pm/projects/{other_project_id}/members/{fixture['membership_id']}/progress",
        headers={"X-User-Id": str(PM_USER_ID)},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_member_progress_no_plan_returns_null_plan_and_empty_tasks(client, test_data):
    project_id = await _create_project(client, test_data)
    membership_id, _user_id = await _create_engineer(client, test_data, project_id)

    response = await client.get(
        f"/api/v1/pm/projects/{project_id}/members/{membership_id}/progress",
        headers={"X-User-Id": str(PM_USER_ID)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["plan_id"] is None
    assert body["tasks"] == []
    assert body["blockers"] == []
    assert body["percent"] == 0


# --- 4. Dashboard tổng quan dự án ---------------------------------------------------------------


@pytest.fixture(autouse=True)
def _stub_ai_cost_lookup(monkeypatch):
    """Chặn lời gọi Langfuse thật (mạng ngoài) trong MỌI test dashboard — mặc định `None` (giống
    "chưa cấu hình Langfuse trong CI"). Cùng lý do với `fake_embedder_for_tests` ở conftest.py: gọi
    dịch vụ thật làm test chậm/phụ thuộc mạng. Test riêng dưới đây override lại để kiểm số thật."""

    async def _default(_project_id: int) -> None:
        return None

    monkeypatch.setattr(
        "src.services.pm_dashboard_service.get_project_ai_cost_usd", _default
    )


@pytest.mark.asyncio
async def test_dashboard_aggregates_project_stats(client, test_data, project_with_approved_plan):
    fixture = project_with_approved_plan
    # Thêm 1 Engineer thứ 2 CHƯA có plan để kiểm KPI "Đã có Plan" phân biệt đúng với "chưa có".
    await _create_engineer(client, test_data, fixture["project_id"])
    async with AsyncSessionLocal() as db:
        db.add(
            Blocker(
                plan_task_id=fixture["plan_task_id"],
                reported_by_membership_id=fixture["membership_id"],
                category="TECHNICAL",
                reason="Blocker de kiem tra dashboard tong hop.",
                status="OPEN",
            )
        )
        await db.commit()

    response = await client.get(
        f"/api/v1/pm/projects/{fixture['project_id']}/dashboard",
        headers={"X-User-Id": str(PM_USER_ID)},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["engineer_count"] == 2
    assert body["with_plan_count"] == 1
    assert body["active_count"] == 1
    assert body["done_count"] == 0
    assert body["open_blocker_count"] == 1
    assert body["template_approved"] is True
    assert body["template_task_count"] > 0
    assert len(body["oldest_open_blockers"]) == 1
    assert body["oldest_open_blockers"][0]["reason"] == "Blocker de kiem tra dashboard tong hop."


@pytest.mark.asyncio
async def test_dashboard_document_coverage_reflects_active_documents(client, project_with_approved_plan):
    """0/5 nhóm ban đầu (fixture không tải tài liệu nào) — đúng thực tế, không giả định có sẵn."""
    fixture = project_with_approved_plan
    response = await client.get(
        f"/api/v1/pm/projects/{fixture['project_id']}/dashboard",
        headers={"X-User-Id": str(PM_USER_ID)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["document_group_total"] == 5
    assert body["document_group_count"] == 0


@pytest.mark.asyncio
async def test_dashboard_ai_cost_is_null_when_no_langfuse_data(client, project_with_approved_plan):
    """Mặc định (fixture `_stub_ai_cost_lookup` ở trên trả `None`) — field phải là `null` trong JSON,
    KHÔNG phải `0`, để FE phân biệt được "chưa có dữ liệu" với "đã tính, đúng là 0đ"."""
    fixture = project_with_approved_plan
    response = await client.get(
        f"/api/v1/pm/projects/{fixture['project_id']}/dashboard",
        headers={"X-User-Id": str(PM_USER_ID)},
    )
    assert response.status_code == 200
    assert response.json()["total_ai_cost_usd"] is None


@pytest.mark.asyncio
async def test_dashboard_ai_cost_reflects_langfuse_lookup(
    client, monkeypatch, project_with_approved_plan
):
    """Khi Langfuse trả về số thật, dashboard phải truyền đúng số đó ra API — chứng minh
    `pm_dashboard_service.get_dashboard()` thực sự GỌI và DÙNG kết quả của
    `get_project_ai_cost_usd()`, không chỉ khai báo field rồi bỏ trống."""
    fixture = project_with_approved_plan
    captured_project_ids: list[int] = []

    async def _fake_cost(project_id: int) -> float:
        captured_project_ids.append(project_id)
        return 1.234567

    monkeypatch.setattr("src.services.pm_dashboard_service.get_project_ai_cost_usd", _fake_cost)

    response = await client.get(
        f"/api/v1/pm/projects/{fixture['project_id']}/dashboard",
        headers={"X-User-Id": str(PM_USER_ID)},
    )
    assert response.status_code == 200
    assert response.json()["total_ai_cost_usd"] == pytest.approx(1.234567)
    assert captured_project_ids == [fixture["project_id"]]


@pytest.mark.asyncio
async def test_dashboard_rejects_missing_project(client):
    response = await client.get(
        "/api/v1/pm/projects/999999/dashboard",
        headers={"X-User-Id": str(PM_USER_ID)},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_dashboard_requires_pm_project_membership(client, test_data, project_with_approved_plan):
    """Engineer của CHÍNH dự án đó vẫn không được xem Dashboard — đây là màn hình của PM."""
    fixture = project_with_approved_plan
    response = await client.get(
        f"/api/v1/pm/projects/{fixture['project_id']}/dashboard",
        headers={"X-User-Id": str(fixture["user_id"])},
    )
    assert response.status_code == 403
