"""Test Phase 4 — sinh / duyệt / tạo lại Candidate Plan (UC-06).

Bước 5 (gọi LLM) được TẮT bằng `plan_generation_use_ai=False` trong toàn bộ file này: test phải
deterministic và không phụ thuộc mạng/API key. Khi tắt AI, pipeline chạy baseline B0 — vẫn đi qua
đủ 6 bước, vẫn ghi PlanTask/PlanTaskSource thật, chỉ khác ở chỗ nội dung lấy từ
`TemplateTask.instruction_template` thay vì do LLM viết. Nhờ vậy test kiểm được toàn bộ phần
nghiệp vụ (ràng buộc, mapping nguồn, INV7, unique index) mà không bao giờ flaky.
"""

import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import select

from src.config import get_settings
from src.model.document_chunk import DocumentChunk
from src.model.document_version import DocumentVersion
from src.model.enums import (
    DocumentDomain,
    DocumentStatus,
    PlanStatus,
    PolicyCategory,
    TaskCategory,
    TemplateVersionStatus,
    VersionStatus,
)
from src.model.knowledge_document import KnowledgeDocument
from src.model.onboarding_plan import OnboardingPlan
from src.model.onboarding_template import OnboardingTemplate
from src.model.plan_task import PlanTask
from src.model.session import AsyncSessionLocal
from src.model.template_task import TemplateTask
from src.model.template_version import TemplateVersion
from src.services.plan_generation.content_llm import (
    DocumentOutline,
    EvidenceCard,
    _batch_documents,
    _build_evidence_block,
    _build_sources_section,
    _citations_within_range,
    _parse_evidence_cards,
    _validate_instruction,
)
from src.services.plan_generation.prompts import (
    NO_SOURCE_NOTICE,
    READ_FULL_DOCUMENT_NOTICE,
    UNSUMMARIZED_CHUNK_NOTE,
)
from src.services.plan_generation.steps import DocumentRef, GenerationContext, compute_due_dates
from src.services.plan_generation.tools import ChunkHit
from src.services.plan_task_service import SNIPPET_MAX_CHARS, _plain_text_snippet

PM_USER_ID = 19


@pytest.fixture(autouse=True)
def disable_ai_generation():
    """Tắt bước LLM cho mọi test trong file. `get_settings` có @lru_cache nên sửa thẳng instance
    đang cache là đủ; khôi phục lại ở teardown để không rò trạng thái sang file test khác."""
    settings = get_settings()
    original = settings.plan_generation_use_ai
    settings.plan_generation_use_ai = False
    yield
    settings.plan_generation_use_ai = original


def _unique_key() -> str:
    return f"TEST{uuid.uuid4().hex[:8].upper()}"


async def _create_project(client, test_data) -> int:
    response = await client.post(
        "/api/v1/projects/pm",
        json={"key": _unique_key(), "name": "Phase4 Plan Test", "created_by_admin_id": PM_USER_ID},
    )
    assert response.status_code == 201
    project_id = response.json()["project_id"]
    test_data.project_ids.append(project_id)
    return project_id


async def _create_engineer_membership_with_user(client, test_data, project_id: int) -> tuple[int, int]:
    """Như `_create_engineer_membership()` nhưng trả thêm `user_id` — Member Portal xác thực theo
    NGƯỜI DÙNG (`X-User-Id`/cookie phiên), không theo `membership_id`, nên test gọi thẳng API Member
    cần biết user_id thật của kỹ sư."""
    email = f"test-eng-{uuid.uuid4().hex[:8]}@onboarding.dev"
    user_response = await client.post(
        "/api/v1/users",
        headers={"X-User-Id": str(PM_USER_ID)},
        json={"email": email, "display_name": "Test Engineer", "created_by_admin_id": PM_USER_ID},
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


async def _create_engineer_membership(client, test_data, project_id: int) -> int:
    membership_id, _ = await _create_engineer_membership_with_user(client, test_data, project_id)
    return membership_id


async def _approve_project_template(client, project_id: int) -> int:
    """Duyệt version DRAFT mà project tự có sẵn từ lúc tạo (Phase 2 fork từ Global Master)."""
    template_response = await client.get(f"/api/v1/onboarding-templates/pm/by-project/{project_id}")
    assert template_response.status_code == 200
    template_id = template_response.json()["template_id"]

    versions = await client.get(f"/api/v1/template-versions/pm/by-template/{template_id}")
    version_id = versions.json()[0]["version_id"]

    approve = await client.patch(f"/api/v1/template-versions/pm/{version_id}/approve")
    assert approve.status_code == 200, approve.text
    return version_id


async def _add_project_document(project_id: int, category: str, title: str) -> int:
    """Tạo 1 tài liệu ACTIVE cho project. Dùng ORM trực tiếp vì route upload thật sẽ đẩy file lên
    Cloudinary (chậm + phụ thuộc mạng) và version upload xong ở PROCESSING chứ không ACTIVE."""
    async with AsyncSessionLocal() as db:
        document = KnowledgeDocument(
            project_id=project_id,
            created_by_user_id=PM_USER_ID,
            knowledge_domain=DocumentDomain.PROJECT,
            document_category=category,
            policy_category=None,
            title=title,
            source_url="https://example.test/doc.md",
            status=DocumentStatus.ACTIVE,
        )
        db.add(document)
        await db.flush()
        db.add(
            DocumentVersion(
                document_id=document.document_id,
                version_no="1",
                revision_no=1,
                embedding_model_version="pending",
                storage_uri="https://example.test/doc.md",
                checksum=uuid.uuid4().hex,
                status=VersionStatus.ACTIVE,
            )
        )
        await db.commit()
        return document.document_id


async def _generate_plan(client, membership_id: int, *, start_at: str | None = None) -> dict:
    """Gọi API sinh plan. BackgroundTasks của FastAPI chạy XONG trước khi httpx trả response
    (ASGITransport đợi hết lifespan của request), nên đến đây job đã hoàn tất — không cần poll.

    `start_at`: mô phỏng PM chọn giờ ở modal (ISO string) — không truyền thì giữ hành vi cũ."""
    payload: dict = {"membership_id": membership_id}
    if start_at is not None:
        payload["start_at"] = start_at
    response = await client.post("/api/v1/onboarding-plans/pm/generate", json=payload)
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]

    job = await client.get(f"/api/v1/onboarding-plans/pm/generate/{job_id}")
    assert job.status_code == 200
    return job.json()


async def _generate_reference_plan(client, project_id: int) -> dict:
    """Sinh lộ trình CHUẨN cấp dự án (không gắn kỹ sư). Cùng cơ chế job như `_generate_plan`."""
    response = await client.post(
        "/api/v1/onboarding-plans/pm/reference/generate", json={"project_id": project_id}
    )
    assert response.status_code == 202, response.text
    job = await client.get(f"/api/v1/onboarding-plans/pm/generate/{response.json()['job_id']}")
    assert job.status_code == 200
    return job.json()


async def _list_tasks(client, plan_id: int) -> list[dict]:
    response = await client.get(f"/api/v1/onboarding-plans/pm/{plan_id}/tasks")
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
async def test_generate_with_chosen_start_at_schedules_tasks_from_that_moment(client, ready_project):
    """Modal chọn giờ bắt đầu (mục 2 của plan sửa lỗi) — PM truyền `start_at`, task ĐẦU TIÊN phải
    bắt đầu đúng mốc đó, không phải giờ server gọi API."""
    chosen_start = "2026-08-24T09:00:00"  # Thứ Hai 09:00 — cố định để so sánh chính xác

    job = await _generate_plan(client, ready_project["membership_id"], start_at=chosen_start)
    assert job["status"] == "DONE", job["error"]

    tasks = await _list_tasks(client, job["plan_id"])
    assert tasks, "Plan phải có task"
    first = min(tasks, key=lambda t: t["display_order"])
    assert first["start_at"] == chosen_start, (
        f"Task đầu tiên phải bắt đầu đúng giờ PM chọn, thực tế {first['start_at']!r}"
    )


@pytest.mark.asyncio
async def test_generate_without_start_at_still_works_as_before(client, ready_project):
    """Không truyền `start_at` (luồng cũ, vd script/test khác chưa cập nhật) vẫn phải sinh được
    plan bình thường — trường mới phải optional thật, không bắt buộc ngầm."""
    job = await _generate_plan(client, ready_project["membership_id"])
    assert job["status"] == "DONE", job["error"]


@pytest.mark.asyncio
async def test_task_due_dates_increase_monotonically_after_generate(client, ready_project):
    """Hồi quy end-to-end cho đúng lỗi PM báo cáo: sinh xong, KHÔNG được có 2 task cùng hạn, và
    hạn phải tăng dần theo display_order."""
    job = await _generate_plan(
        client, ready_project["membership_id"], start_at="2026-08-24T09:00:00"
    )
    assert job["status"] == "DONE", job["error"]

    tasks = sorted(
        await _list_tasks(client, job["plan_id"]), key=lambda t: t["display_order"]
    )
    due_dates = [t["due_at"] for t in tasks]
    assert len(set(due_dates)) == len(due_dates), (
        f"Có task trùng giờ hạn — đúng bug đã sửa: {due_dates}"
    )
    assert due_dates == sorted(due_dates), "Hạn phải tăng dần theo display_order"


@pytest.mark.asyncio
async def test_task_start_at_chains_from_previous_task_due_at(client, ready_project):
    """Giờ bắt đầu hiển thị của task N phải đúng bằng giờ kết thúc của task N-1 (mục 3 của plan) —
    không có khoảng trống hay chồng lấn giữa 2 task liên tiếp."""
    job = await _generate_plan(
        client, ready_project["membership_id"], start_at="2026-08-24T09:00:00"
    )
    tasks = sorted(
        await _list_tasks(client, job["plan_id"]), key=lambda t: t["display_order"]
    )
    assert len(tasks) >= 2, "Cần ít nhất 2 task để kiểm chuỗi nối tiếp"

    assert tasks[0]["start_at"] == "2026-08-24T09:00:00"
    for previous, current in zip(tasks, tasks[1:], strict=False):
        assert current["start_at"] == previous["due_at"], (
            f"start_at của task {current['display_order']} phải = due_at của task "
            f"{previous['display_order']} ({previous['due_at']!r}), thực tế {current['start_at']!r}"
        )


@pytest.mark.asyncio
async def test_pm_can_edit_task_due_at_while_draft(client, ready_project):
    """PM sửa giờ 1 task khi plan còn DRAFT (mục 5 của plan) — request cũ (chỉ title/instruction)
    vẫn phải hoạt động bình thường, do due_at là optional."""
    job = await _generate_plan(client, ready_project["membership_id"])
    tasks = await _list_tasks(client, job["plan_id"])
    task_id = tasks[0]["plan_task_id"]
    new_due_at = "2026-09-01T10:30:00"

    response = await client.patch(
        f"/api/v1/plan-tasks/pm/{task_id}", json={"due_at": new_due_at}
    )
    assert response.status_code == 200, response.text
    assert response.json()["due_at"] == new_due_at

    async with AsyncSessionLocal() as db:
        task = await db.get(PlanTask, task_id)
        assert task.due_at == datetime(2026, 9, 1, 10, 30, 0)


@pytest.mark.asyncio
async def test_pm_cannot_edit_task_due_at_after_approve(client, ready_project):
    """Đối xứng với `test_edit_task_allowed_in_draft_and_blocked_after_approve` (title/instruction)
    nhưng cho field `due_at` mới thêm — guard DRAFT-only phải áp dụng đồng đều cho mọi field."""
    job = await _generate_plan(client, ready_project["membership_id"])
    plan_id = job["plan_id"]
    tasks = await _list_tasks(client, plan_id)
    task_id = tasks[0]["plan_task_id"]

    approve = await client.patch(
        f"/api/v1/onboarding-plans/pm/{plan_id}/approve", json={"approved_by_user_id": PM_USER_ID}
    )
    assert approve.status_code == 200, approve.text

    response = await client.patch(
        f"/api/v1/plan-tasks/pm/{task_id}", json={"due_at": "2026-09-01T10:30:00"}
    )
    assert response.status_code == 409, response.text


def _step_detail(job: dict, key: str) -> str:
    return next(step["detail"] for step in job["steps"] if step["key"] == key)


@pytest_asyncio.fixture
async def project_with_docs(client, test_data):
    """Project có TemplateVersion APPROVED + 5 nhóm tài liệu ACTIVE, NHƯNG chưa có lộ trình chuẩn."""
    project_id = await _create_project(client, test_data)
    version_id = await _approve_project_template(client, project_id)
    for category in ("OVERVIEW", "ARCHITECTURE", "SETUP", "ACCESS_SECURITY", "CODEBASE_GUIDE"):
        await _add_project_document(project_id, category, f"{category} doc")
    membership_id = await _create_engineer_membership(client, test_data, project_id)
    return {"project_id": project_id, "version_id": version_id, "membership_id": membership_id}


@pytest_asyncio.fixture
async def ready_project(client, project_with_docs):
    """Như trên nhưng ĐÃ có lộ trình chuẩn — điều kiện bắt buộc để cấp plan cho kỹ sư."""
    job = await _generate_reference_plan(client, project_with_docs["project_id"])
    assert job["status"] == "DONE", job["error"]
    return {**project_with_docs, "reference_plan_id": job["plan_id"]}


@pytest.mark.asyncio
async def test_reference_generate_fails_without_approved_template(client, test_data):
    """Chưa duyệt TemplateVersion thì KHÔNG được tạo lộ trình rỗng âm thầm (SoT rule 16)."""
    project_id = await _create_project(client, test_data)

    job = await _generate_reference_plan(client, project_id)
    assert job["status"] == "FAILED"
    assert "APPROVED" in job["error"]
    assert job["plan_id"] is None

    async with AsyncSessionLocal() as db:
        plan = await db.scalar(select(OnboardingPlan).where(OnboardingPlan.project_id == project_id))
        assert plan is None, "Không được để lại plan rác khi pipeline thất bại"


@pytest.mark.asyncio
async def test_generate_for_engineer_fails_without_reference(client, project_with_docs):
    """Dự án chưa có lộ trình chuẩn thì không cấp plan cho kỹ sư được — chặn NGAY ở API (422 đồng
    bộ) để FE hướng PM đi tạo lộ trình chuẩn, không phải mở màn 6 bước rồi mới báo hỏng."""
    response = await client.post(
        "/api/v1/onboarding-plans/pm/generate",
        json={"membership_id": project_with_docs["membership_id"]},
    )
    assert response.status_code == 422
    assert "lộ trình chuẩn" in response.json()["detail"]

    async with AsyncSessionLocal() as db:
        plan = await db.scalar(
            select(OnboardingPlan).where(
                OnboardingPlan.membership_id == project_with_docs["membership_id"]
            )
        )
        assert plan is None


@pytest.mark.asyncio
async def test_reference_plan_is_project_level_not_membership(client, ready_project):
    """Lộ trình chuẩn gắn `project_id`, KHÔNG gắn kỹ sư nào — CHECK ck_onboarding_plans_owner ép
    đúng 1 trong 2 cột sở hữu."""
    async with AsyncSessionLocal() as db:
        reference = await db.get(OnboardingPlan, ready_project["reference_plan_id"])
        assert reference.project_id == ready_project["project_id"]
        assert reference.membership_id is None
        assert reference.status == PlanStatus.DRAFT

    # Không lọt vào danh sách plan của thành viên (query dùng INNER JOIN ProjectMembership).
    listed = (
        await client.get(
            f"/api/v1/onboarding-plans/pm/by-project/{ready_project['project_id']}"
        )
    ).json()
    assert ready_project["reference_plan_id"] not in [p["plan_id"] for p in listed]


@pytest.mark.asyncio
async def test_reference_uses_ai_engineer_plan_clones(client, ready_project):
    """Phân định rõ: bản chuẩn là chỗ DUY NHẤT gọi AI; cấp plan cho kỹ sư luôn sao chép."""
    # `ready_project` đã sinh sẵn bản chuẩn — sinh lại để bắt được detail của bước 5.
    reference_job = await _generate_reference_plan(client, ready_project["project_id"])
    assert "Sao chép" not in _step_detail(reference_job, "generate_content")

    engineer_job = await _generate_plan(client, ready_project["membership_id"])
    assert engineer_job["status"] == "DONE", engineer_job["error"]
    detail = _step_detail(engineer_job, "generate_content")
    assert "Sao chép" in detail
    assert f"#{ready_project['reference_plan_id']}" in detail


@pytest.mark.asyncio
async def test_reference_regenerate_overwrites_in_place(client, ready_project):
    """Tạo lại lộ trình chuẩn → vẫn đúng 1 row (UNIQUE bảo vệ), revision tăng, task cũ bị thay."""
    plan_id = ready_project["reference_plan_id"]
    before = (await client.get(f"/api/v1/onboarding-plans/pm/{plan_id}/tasks")).json()

    job = await _generate_reference_plan(client, ready_project["project_id"])
    assert job["plan_id"] == plan_id, "Phải ghi đè tại chỗ, không tạo bản chuẩn thứ 2"

    async with AsyncSessionLocal() as db:
        reference = await db.get(OnboardingPlan, plan_id)
        await db.refresh(reference)
        assert reference.revision == 2
        count = len(
            (
                await db.scalars(
                    select(OnboardingPlan.plan_id).where(
                        OnboardingPlan.project_id == ready_project["project_id"],
                        OnboardingPlan.membership_id.is_(None),
                    )
                )
            ).all()
        )
    assert count == 1, "Mỗi dự án chỉ được đúng 1 lộ trình chuẩn"

    after = (await client.get(f"/api/v1/onboarding-plans/pm/{plan_id}/tasks")).json()
    assert {t["plan_task_id"] for t in after}.isdisjoint({t["plan_task_id"] for t in before})


@pytest.mark.asyncio
async def test_reference_plan_cannot_be_approved(client, ready_project):
    """Bản chuẩn không phát hành cho ai nên không có bước duyệt — nếu cho duyệt thì nó thành
    APPROVED và PM mất luôn quyền sửa (update_task chặn khác DRAFT)."""
    response = await client.patch(
        f"/api/v1/onboarding-plans/pm/{ready_project['reference_plan_id']}/approve",
        json={"approved_by_user_id": PM_USER_ID},
    )
    assert response.status_code == 409
    assert "lộ trình chuẩn" in response.json()["detail"]


@pytest.mark.asyncio
async def test_editing_reference_does_not_touch_existing_engineer_plans(
    client, test_data, ready_project
):
    """Toàn vẹn dữ liệu — điểm quan trọng nhất của thiết kế này:
    sửa lộ trình chuẩn KHÔNG đụng kỹ sư đã nhận plan, chỉ người nhận VỀ SAU mới thấy bản mới."""
    first_job = await _generate_plan(client, ready_project["membership_id"])
    first_tasks = (
        await client.get(f"/api/v1/onboarding-plans/pm/{first_job['plan_id']}/tasks")
    ).json()
    original_title = first_tasks[0]["title"]

    reference_tasks = (
        await client.get(f"/api/v1/onboarding-plans/pm/{ready_project['reference_plan_id']}/tasks")
    ).json()
    edited = await client.patch(
        f"/api/v1/plan-tasks/pm/{reference_tasks[0]['plan_task_id']}",
        json={"title": "PM da sua lo trinh chuan"},
    )
    assert edited.status_code == 200

    unchanged = (
        await client.get(f"/api/v1/onboarding-plans/pm/{first_job['plan_id']}/tasks")
    ).json()
    assert unchanged[0]["title"] == original_title, "Plan đã cấp KHÔNG được đổi theo bản chuẩn"

    second_membership = await _create_engineer_membership(
        client, test_data, ready_project["project_id"]
    )
    second_job = await _generate_plan(client, second_membership)
    second_tasks = (
        await client.get(f"/api/v1/onboarding-plans/pm/{second_job['plan_id']}/tasks")
    ).json()
    assert second_tasks[0]["title"] == "PM da sua lo trinh chuan", "Kỹ sư mới phải nhận bản đã sửa"


@pytest.mark.asyncio
async def test_generate_creates_plan_with_all_template_tasks(client, ready_project):
    """Số PlanTask phải khớp số TemplateTask và giữ đủ task bắt buộc (SoT rule 10)."""
    job = await _generate_plan(client, ready_project["membership_id"])
    assert job["status"] == "DONE", job["error"]
    assert len(job["steps"]) == 6
    assert all(step["status"] == "DONE" for step in job["steps"])
    assert job["plan_id"] is not None

    tasks = (await client.get(f"/api/v1/onboarding-plans/pm/{job['plan_id']}/tasks")).json()
    template_tasks = (
        await client.get(f"/api/v1/template-tasks/pm/by-version/{ready_project['version_id']}")
    ).json()

    assert len(tasks) == len(template_tasks)
    assert {t["template_task_id"] for t in tasks} == {t["template_task_id"] for t in template_tasks}
    mandatory_template = {t["template_task_id"] for t in template_tasks if t["mandatory"]}
    mandatory_plan = {t["template_task_id"] for t in tasks if t["mandatory"]}
    assert mandatory_template.issubset(mandatory_plan)


@pytest.mark.asyncio
async def test_generated_plan_starts_as_draft_with_ordered_due_dates(client, ready_project):
    """Plan mới luôn DRAFT (SoT UC-06) và deadline tăng dần theo display_order."""
    job = await _generate_plan(client, ready_project["membership_id"])
    plan = (
        await client.get(f"/api/v1/onboarding-plans/pm/by-membership/{ready_project['membership_id']}")
    ).json()
    assert plan["status"] == "DRAFT"
    assert plan["revision"] == 1
    assert plan["approved_at"] is None

    tasks = (await client.get(f"/api/v1/onboarding-plans/pm/{job['plan_id']}/tasks")).json()
    orders = [t["display_order"] for t in tasks]
    assert orders == sorted(orders), "Task phải trả về đúng thứ tự template"
    due_dates = [t["due_at"] for t in tasks]
    assert all(d is not None for d in due_dates)
    assert due_dates == sorted(due_dates), "Deadline phải tăng dần theo thứ tự thực hiện"


@pytest.mark.asyncio
async def test_sources_only_reference_own_project_documents(client, test_data, ready_project):
    """Chống rò rỉ chéo project: nguồn trích dẫn chỉ được trỏ tới tài liệu của ĐÚNG project."""
    other_project_id = await _create_project(client, test_data)
    for category in ("OVERVIEW", "SETUP"):
        await _add_project_document(other_project_id, category, f"KHONG DUOC DUNG {category}")

    job = await _generate_plan(client, ready_project["membership_id"])
    tasks = (await client.get(f"/api/v1/onboarding-plans/pm/{job['plan_id']}/tasks")).json()

    used_document_ids = {s["document_id"] for t in tasks for s in t["sources"]}
    assert used_document_ids, "Phải có ít nhất 1 trích dẫn nguồn"

    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(KnowledgeDocument.document_id, KnowledgeDocument.project_id).where(
                    KnowledgeDocument.document_id.in_(used_document_ids)
                )
            )
        ).all()
    for document_id, project_id in rows:
        assert project_id in (
            ready_project["project_id"],
            None,  # None = tài liệu POLICY (Company Core dùng chung mọi project)
        ), f"Tài liệu {document_id} thuộc project khác đã lọt vào nguồn"


@pytest.mark.asyncio
async def test_task_without_source_still_created_with_warning(client, test_data):
    """Không có tài liệu nào -> vẫn tạo được lộ trình chuẩn (không chặn PM), nhưng phải cảnh báo và
    KHÔNG bịa citation."""
    project_id = await _create_project(client, test_data)
    await _approve_project_template(client, project_id)

    job = await _generate_reference_plan(client, project_id)
    assert job["status"] == "DONE", job["error"]
    assert len(job["warnings"]) > 0, "Phải cảnh báo khi task không có nguồn"

    tasks = (await client.get(f"/api/v1/onboarding-plans/pm/{job['plan_id']}/tasks")).json()
    assert tasks, "Vẫn phải tạo task dù thiếu tài liệu"
    project_sources = [s for t in tasks for s in t["sources"] if s["document_id"] is not None]
    async with AsyncSessionLocal() as db:
        for source in project_sources:
            document = await db.get(KnowledgeDocument, source["document_id"])
            assert document is not None, "Không được bịa nguồn trỏ tới tài liệu không tồn tại"


@pytest.mark.asyncio
async def test_task_without_document_does_not_fabricate_steps(client, test_data):
    """Task KHÔNG có tài liệu nguồn thì không được trình bày `instruction_template` như hướng dẫn
    thật — đó là khung mẫu PM soạn ở Master Template, chưa được tài liệu dự án xác nhận.

    Đúng lỗi phát hiện khi PM test thật: task hiện "TÀI LIỆU NGUỒN (0)" mà vẫn có đủ mục
    "Các bước thực hiện" như thể đã đọc tài liệu."""
    project_id = await _create_project(client, test_data)
    await _approve_project_template(client, project_id)

    job = await _generate_reference_plan(client, project_id)
    assert job["status"] == "DONE", job["error"]
    tasks = (await client.get(f"/api/v1/onboarding-plans/pm/{job['plan_id']}/tasks")).json()

    # Project mới chưa có tài liệu PROJECT nào -> mọi task nhóm dự án đều rơi vào nhánh "no source".
    without_sources = [t for t in tasks if not t["sources"]]
    assert without_sources, "Fixture phải có ít nhất 1 task không nguồn để kiểm tra"
    for task in without_sources:
        assert NO_SOURCE_NOTICE in task["instruction"], "Phải nói rõ là chưa có tài liệu nguồn"
        assert "## Các bước thực hiện" not in task["instruction"], (
            "Không được dựng mục 'Các bước thực hiện' khi chưa có bằng chứng từ tài liệu"
        )


@pytest.mark.asyncio
async def test_company_task_reads_policy_and_appears_in_plan(client, test_data):
    """Nhóm "Tìm hiểu công ty" (TaskCategory.COMPANY) phải sinh ra task thật trong lộ trình và lấy
    nguồn từ chính sách công ty (POLICY), không phải tài liệu riêng của dự án.

    Task được thêm qua ĐÚNG luồng Master Template (version DRAFT -> thêm task -> duyệt), không ghi
    thẳng DB: `template_task_service` chỉ cho sửa task khi version còn DRAFT, ghi tắt là phá đúng
    bất biến mình đang bảo vệ."""
    project_id = await _create_project(client, test_data)

    template = (await client.get(f"/api/v1/onboarding-templates/pm/by-project/{project_id}")).json()
    versions = (
        await client.get(f"/api/v1/template-versions/pm/by-template/{template['template_id']}")
    ).json()
    draft_version_id = versions[0]["version_id"]

    created = await client.post(
        "/api/v1/template-tasks/pm",
        json={
            "version_id": draft_version_id,
            "category": "COMPANY",
            "title_pattern": "Tìm hiểu chính sách công ty",
            "objective": "Nắm chính sách nhân sự, bảo mật, phúc lợi trước khi bắt đầu việc kỹ thuật",
            "instruction_template": "Đọc bộ chính sách công ty trong Company Core.",
            "mandatory": True,
            "estimated_minutes": 60,
        },
    )
    assert created.status_code == 201, created.text

    approve = await client.patch(f"/api/v1/template-versions/pm/{draft_version_id}/approve")
    assert approve.status_code == 200, approve.text

    job = await _generate_reference_plan(client, project_id)
    assert job["status"] == "DONE", job["error"]

    tasks = (await client.get(f"/api/v1/onboarding-plans/pm/{job['plan_id']}/tasks")).json()
    company_tasks = [t for t in tasks if t["category"] == "COMPANY"]
    assert company_tasks, "Lộ trình chuẩn phải có nhóm 'Tìm hiểu công ty'"

    # Nguồn của nhóm COMPANY phải là tài liệu POLICY (project_id IS NULL), không phải tài liệu dự án.
    async with AsyncSessionLocal() as db:
        for source in (s for t in company_tasks for s in t["sources"]):
            document = await db.get(KnowledgeDocument, source["document_id"])
            assert document is not None
            assert document.project_id is None, "Nhóm công ty chỉ được đọc chính sách chung"


@pytest.mark.asyncio
async def test_orientation_task_only_cites_overview_category(client, ready_project):
    """Sau khi bỏ mapping thừa `TASK_CATEGORY_POLICY_MAP[ORIENTATION]` (steps.py), task "Đọc tài
    liệu Overview" chỉ được trích tài liệu category OVERVIEW của đúng project — không còn lẫn nguồn
    Company Core (POLICY) như lỗi PM phát hiện thật: project chỉ có 1 tài liệu Overview nhưng task
    hiện "4 NGUỒN" vì bị cộng thêm nguồn policy không liên quan."""
    job = await _generate_plan(client, ready_project["membership_id"])
    tasks = (await client.get(f"/api/v1/onboarding-plans/pm/{job['plan_id']}/tasks")).json()

    orientation_tasks = [t for t in tasks if t["category"] == "ORIENTATION"]
    assert orientation_tasks, "Fixture project_with_docs phải có task nhóm Tổng quan (ORIENTATION)"

    async with AsyncSessionLocal() as db:
        for source in (s for t in orientation_tasks for s in t["sources"]):
            document = await db.get(KnowledgeDocument, source["document_id"])
            assert document is not None
            assert document.knowledge_domain == DocumentDomain.PROJECT, (
                "Task Overview không được lẫn nguồn POLICY nữa"
            )
            assert document.document_category == "OVERVIEW"


@pytest.mark.asyncio
async def test_company_task_lists_every_active_policy_document(client, ready_project):
    """Nhóm "Tìm hiểu công ty" phải liệt kê ĐỦ MỌI tài liệu chính sách ACTIVE, không trần nào cắt.

    Đây là bất biến quan trọng nhất của đợt sửa này: trước đây trần cứng (4, rồi 10) khiến 18 tài
    liệu chính sách chỉ hiện vài nguồn — kỹ sư đọc xong vẫn sót chính sách. Đối chiếu thẳng với số
    tài liệu POLICY ACTIVE đếm được trong DB, không hardcode con số.
    """
    job = await _generate_plan(client, ready_project["membership_id"])
    tasks = (await client.get(f"/api/v1/onboarding-plans/pm/{job['plan_id']}/tasks")).json()

    company_tasks = [t for t in tasks if t["category"] == "COMPANY"]
    assert company_tasks, "Global Master Template phải có sẵn task nhóm COMPANY"

    async with AsyncSessionLocal() as db:
        active_policy_ids = set(
            (
                await db.scalars(
                    select(KnowledgeDocument.document_id)
                    .join(
                        DocumentVersion,
                        DocumentVersion.document_id == KnowledgeDocument.document_id,
                    )
                    .where(
                        KnowledgeDocument.knowledge_domain == DocumentDomain.POLICY,
                        KnowledgeDocument.status == DocumentStatus.ACTIVE,
                        DocumentVersion.status == VersionStatus.ACTIVE,
                    )
                )
            ).all()
        )

    cited_ids = {s["document_id"] for s in company_tasks[0]["sources"]}
    assert cited_ids == active_policy_ids, (
        "Phải liệt kê đúng và đủ mọi tài liệu chính sách ACTIVE, không thừa không thiếu"
    )


@pytest.mark.asyncio
async def test_plan_task_source_stays_one_row_per_document(client, ready_project):
    """BẢO VỆ MODULE KHÁC: `plan_task_sources` phải giữ đúng 1 dòng / 1 tài liệu.

    Member Portal (`member_onboarding_service._task_sources()`, module của thành viên khác) đọc thẳng
    bảng này để dựng danh sách tài liệu tham khảo. Nếu tính năng trích dẫn nhiều đoạn lỡ chen thêm
    dòng vào đây, bên đó sẽ hiện trùng lặp cùng 1 file — nên chi tiết theo đoạn nằm ở
    `plan_task_citations`, và test này canh đúng ranh giới đó.
    """
    from src.model.plan_task import PlanTask
    from src.model.plan_task_source import PlanTaskSource

    job = await _generate_plan(client, ready_project["membership_id"])

    async with AsyncSessionLocal() as db:
        task_ids = list(
            (await db.scalars(select(PlanTask.plan_task_id).where(PlanTask.plan_id == job["plan_id"]))).all()
        )
        rows = (
            await db.execute(
                select(PlanTaskSource.plan_task_id, PlanTaskSource.version_id).where(
                    PlanTaskSource.plan_task_id.in_(task_ids)
                )
            )
        ).all()

    pairs = [(plan_task_id, version_id) for plan_task_id, version_id in rows]
    assert len(pairs) == len(set(pairs)), "Không được có 2 dòng nguồn cùng (task, tài liệu)"


# --- Nhánh AI với LLM giả -------------------------------------------------------------------------
# `disable_ai_generation` (autouse) tắt AI cho cả file để test deterministic; nhóm dưới đây bật lại
# và thay LLM thật bằng bản giả. Nhờ vậy vẫn kiểm được TOÀN BỘ đường đi thật của trích dẫn (truy xuất
# đoạn -> chia lô -> ráp nội dung -> ghi DB -> API) mà không phụ thuộc mạng hay tính ngẫu nhiên.


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeLLM:
    """LLM giả: tóm tắt lô thì trả đủ dòng `[k]`, viết các bước thì trả đúng khung markdown.

    `summarize_only_first` mô phỏng đúng ca LLM bỏ sót — dùng để kiểm cơ chế bù trích dẫn.
    """

    def __init__(self, *, summarize_only_first: bool = False) -> None:
        self.summarize_only_first = summarize_only_first
        self.calls = 0

    async def ainvoke(self, messages, config=None):  # noqa: ARG002 - chữ ký khớp LangChain
        self.calls += 1
        user_text = messages[-1][1]
        if "CÁC ĐOẠN TÀI LIỆU CẦN TÓM TẮT" in user_text:
            indexes = [int(n) for n in re.findall(r"^\[(\d+)\]", user_text, flags=re.MULTILINE)]
            if self.summarize_only_first:
                indexes = indexes[:1]
            return _FakeResponse("\n".join(f"[{i}] Y chinh cua doan {i}" for i in indexes))
        return _FakeResponse(
            "## Mục tiêu\nHiểu tài liệu.\n\n"
            "## Các bước thực hiện\n1. Đọc tài liệu [1]\n\n"
            "## Kết quả cần đạt\n- [ ] Đọc xong\n"
        )


@pytest_asyncio.fixture
async def project_with_chunked_docs(client, test_data):
    """Project có tài liệu ĐÃ TÁCH ĐOẠN thật — điều kiện để pipeline sinh được trích dẫn mức đoạn."""
    project_id = await _create_project(client, test_data)
    version_id = await _approve_project_template(client, project_id)
    document_id = await _add_project_document(project_id, "OVERVIEW", "Overview co chunk")

    async with AsyncSessionLocal() as db:
        doc_version_id = await db.scalar(
            select(DocumentVersion.version_id).where(DocumentVersion.document_id == document_id)
        )
        for index in range(3):
            db.add(
                DocumentChunk(
                    version_id=doc_version_id,
                    heading=f"Muc {index}",
                    content=f"Noi dung doan {index} cua tai lieu overview.",
                    embedding_text=f"Muc {index} noi dung doan {index}",
                    lexical_identifiers="",
                    lexical_technical="",
                    section_path=f"Muc {index}",
                    anchor=f"muc-{index}",
                    content_hash=uuid.uuid4().hex,
                    embedding_model_version="test",
                    chunk_index=index,
                    token_count=10,
                )
            )
        await db.commit()

    membership_id, user_id = await _create_engineer_membership_with_user(client, test_data, project_id)
    return {
        "project_id": project_id,
        "version_id": version_id,
        "membership_id": membership_id,
        "user_id": user_id,
    }


@pytest.fixture
def enable_fake_ai(monkeypatch):
    """Bật nhánh AI + tráo LLM thật bằng bản giả."""

    def _enable(llm: _FakeLLM) -> _FakeLLM:
        monkeypatch.setattr("src.services.plan_generation.content_llm.should_use_ai", lambda: True)
        monkeypatch.setattr("src.services.llm.get_plan_content_llm", lambda: llm)
        return llm

    return _enable


@pytest.mark.asyncio
async def test_ai_plan_persists_one_citation_per_chunk(
    client, project_with_chunked_docs, enable_fake_ai
):
    """Đường đi đầy đủ: mỗi ĐOẠN tài liệu thành 1 trích dẫn `[n]` bấm được, còn `plan_task_sources`
    vẫn đúng 1 dòng cho tài liệu đó (không phá hợp đồng mà Member Portal đang dùng)."""
    enable_fake_ai(_FakeLLM())

    job = await _generate_reference_plan(client, project_with_chunked_docs["project_id"])
    assert job["status"] == "DONE", job["error"]

    tasks = (await client.get(f"/api/v1/onboarding-plans/pm/{job['plan_id']}/tasks")).json()
    orientation = next(t for t in tasks if t["category"] == "ORIENTATION")

    assert len(orientation["citations"]) == 3, "3 đoạn tài liệu -> 3 trích dẫn"
    assert [c["citation_order"] for c in orientation["citations"]] == [1, 2, 3]
    assert len({c["chunk_id"] for c in orientation["citations"]}) == 3, "Mỗi trích dẫn 1 đoạn riêng"
    assert len(orientation["sources"]) == 1, "Nguồn mức tài liệu vẫn đúng 1 dòng cho 1 file"

    for citation in orientation["citations"]:
        assert citation["document_url"], "Phải mở được tài liệu"
        assert citation["content_snippet"], "Phải có đoạn văn bản thuần để nhảy đúng chỗ"

    used = {int(n) for n in re.findall(r"\[(\d+)\]", orientation["instruction"])}
    assert used, "Nội dung phải có trích dẫn"
    assert used <= {c["citation_order"] for c in orientation["citations"]}, "Không có [n] bịa"


@pytest.mark.asyncio
async def test_ai_plan_still_cites_chunks_llm_skipped(
    client, project_with_chunked_docs, enable_fake_ai
):
    """LLM bỏ sót đoạn thì code tự bù — đoạn vẫn được liệt kê kèm ghi chú và vẫn bấm mở được.

    Đây là điểm mấu chốt của thiết kế: bao phủ do CODE bảo đảm, không phải do LLM nhớ liệt kê đủ.
    """
    enable_fake_ai(_FakeLLM(summarize_only_first=True))

    job = await _generate_reference_plan(client, project_with_chunked_docs["project_id"])
    assert job["status"] == "DONE", job["error"]

    tasks = (await client.get(f"/api/v1/onboarding-plans/pm/{job['plan_id']}/tasks")).json()
    orientation = next(t for t in tasks if t["category"] == "ORIENTATION")

    assert len(orientation["citations"]) == 3, "Vẫn đủ 3 trích dẫn dù LLM chỉ tóm tắt 1 đoạn"
    assert UNSUMMARIZED_CHUNK_NOTE in orientation["instruction"], "Phải ghi rõ đoạn chưa tóm tắt được"
    assert READ_FULL_DOCUMENT_NOTICE in orientation["instruction"]


@pytest.mark.asyncio
async def test_regenerate_replaces_citations_without_fk_error(
    client, project_with_chunked_docs, enable_fake_ai
):
    """Tạo lại plan phải dọn trích dẫn cũ trước khi xoá task — sai thứ tự là vỡ khoá ngoại."""
    enable_fake_ai(_FakeLLM())

    first = await _generate_reference_plan(client, project_with_chunked_docs["project_id"])
    second = await _generate_reference_plan(client, project_with_chunked_docs["project_id"])
    assert second["status"] == "DONE", second["error"]
    assert second["plan_id"] == first["plan_id"], "Bản chuẩn ghi đè tại chỗ"

    tasks = (await client.get(f"/api/v1/onboarding-plans/pm/{second['plan_id']}/tasks")).json()
    orientation = next(t for t in tasks if t["category"] == "ORIENTATION")
    assert len(orientation["citations"]) == 3, "Không nhân bản trích dẫn qua mỗi lần tạo lại"


@pytest.mark.asyncio
async def test_engineer_plan_clones_citations_from_reference(
    client, project_with_chunked_docs, enable_fake_ai
):
    """Kỹ sư nhận bản sao có ĐỦ trích dẫn — nội dung có `[n]` mà thiếu bản ghi thì bấm vào ra rỗng."""
    enable_fake_ai(_FakeLLM())

    reference = await _generate_reference_plan(client, project_with_chunked_docs["project_id"])
    reference_tasks = (
        await client.get(f"/api/v1/onboarding-plans/pm/{reference['plan_id']}/tasks")
    ).json()
    reference_orientation = next(t for t in reference_tasks if t["category"] == "ORIENTATION")

    job = await _generate_plan(client, project_with_chunked_docs["membership_id"])
    assert job["status"] == "DONE", job["error"]
    tasks = (await client.get(f"/api/v1/onboarding-plans/pm/{job['plan_id']}/tasks")).json()
    orientation = next(t for t in tasks if t["category"] == "ORIENTATION")

    assert [c["citation_order"] for c in orientation["citations"]] == [
        c["citation_order"] for c in reference_orientation["citations"]
    ]
    assert [c["chunk_id"] for c in orientation["citations"]] == [
        c["chunk_id"] for c in reference_orientation["citations"]
    ]


@pytest.mark.asyncio
async def test_member_portal_displays_exact_citations_pm_approved(
    client, project_with_chunked_docs, enable_fake_ai
):
    """Member Portal CHỈ HIỂN THỊ LẠI đúng những gì PM đã tạo — không tự sinh nội dung riêng.

    Gọi THẲNG endpoint `/api/v1/member/plan-tasks/{task_id}` (khác hẳn endpoint PM đang dùng ở các
    test khác trong file) bằng danh tính CỦA CHÍNH kỹ sư, đối chiếu với bản PM đã duyệt — đây là bài
    kiểm chứng thật cho yêu cầu "member hiện y chang PM tạo cho nó", không suy luận qua code.
    """
    enable_fake_ai(_FakeLLM())

    reference = await _generate_reference_plan(client, project_with_chunked_docs["project_id"])
    reference_tasks = (
        await client.get(f"/api/v1/onboarding-plans/pm/{reference['plan_id']}/tasks")
    ).json()
    reference_orientation = next(t for t in reference_tasks if t["category"] == "ORIENTATION")

    job = await _generate_plan(client, project_with_chunked_docs["membership_id"])
    assert job["status"] == "DONE", job["error"]
    pm_tasks = (await client.get(f"/api/v1/onboarding-plans/pm/{job['plan_id']}/tasks")).json()
    pm_orientation = next(t for t in pm_tasks if t["category"] == "ORIENTATION")

    approve = await client.patch(
        f"/api/v1/onboarding-plans/pm/{job['plan_id']}/approve",
        json={"approved_by_user_id": PM_USER_ID},
    )
    assert approve.status_code == 200, "Member Portal chỉ đọc plan đã duyệt (APPROVED trở lên)"

    member_response = await client.get(
        f"/api/v1/member/plan-tasks/{pm_orientation['plan_task_id']}",
        headers={"X-User-Id": str(project_with_chunked_docs["user_id"])},
    )
    assert member_response.status_code == 200, member_response.text
    member_task = member_response.json()

    # Nội dung + citation_order phải khớp TỪNG CHỮ với bản PM đã duyệt — không lệch, không thiếu.
    assert member_task["instruction"] == pm_orientation["instruction"]
    assert [c["citation_order"] for c in member_task["citations"]] == [
        c["citation_order"] for c in pm_orientation["citations"]
    ]
    assert [c["chunk_id"] for c in member_task["citations"]] == [
        c["chunk_id"] for c in pm_orientation["citations"]
    ]
    # Cũng phải khớp với bản chuẩn gốc, không chỉ khớp PM (bắc cầu qua clone ở bước generate_plan).
    assert [c["citation_order"] for c in member_task["citations"]] == [
        c["citation_order"] for c in reference_orientation["citations"]
    ]
    for citation in member_task["citations"]:
        assert citation["document_url"], "Member phải mở được tài liệu, không chỉ thấy con số"
        assert citation["content_snippet"], "Member phải có đoạn văn bản để nhảy đúng chỗ như PM"


@pytest.mark.asyncio
async def test_plan_task_citation_rejects_duplicate_order(
    client, project_with_chunked_docs, enable_fake_ai
):
    """`[n]` là định danh duy nhất trong 1 task — ép ở tầng DB, không chỉ tin tầng ứng dụng.

    Trùng `citation_order` nghĩa là 2 đoạn cùng mang số `[3]`, bấm vào ra đoạn tuỳ may rủi.
    """
    from sqlalchemy.exc import IntegrityError

    from src.model.plan_task import PlanTask
    from src.model.plan_task_citation import PlanTaskCitation

    enable_fake_ai(_FakeLLM())
    job = await _generate_reference_plan(client, project_with_chunked_docs["project_id"])

    async with AsyncSessionLocal() as db:
        existing = await db.scalar(
            select(PlanTaskCitation)
            .join(PlanTask, PlanTask.plan_task_id == PlanTaskCitation.plan_task_id)
            .where(PlanTask.plan_id == job["plan_id"])
            .limit(1)
        )
        assert existing is not None, "Plan sinh ra phải có trích dẫn mức đoạn"

        db.add(
            PlanTaskCitation(
                plan_task_id=existing.plan_task_id,
                task_source_id=existing.task_source_id,
                chunk_id=existing.chunk_id + 1,  # đoạn khác nhưng cố tình trùng số thứ tự
                citation_order=existing.citation_order,
                citation_note="trùng số thứ tự",
            )
        )
        with pytest.raises(IntegrityError):
            await db.commit()


def test_citation_validator_rejects_out_of_range_reference():
    """Trích dẫn `[n]` phải trỏ tới nguồn CÓ THẬT trong prompt.

    LLM đôi khi bịa số thứ tự — trích dẫn kiểu đó không mở được đoạn nào, phải bị loại để rơi về
    nội dung không-AI thay vì phát hành plan trích dẫn sai. Test thẳng hàm validator (không cần
    gọi LLM) vì đây là logic thuần."""
    assert _citations_within_range("Bước 1 [1] rồi bước 2 [2].", 2)
    assert _citations_within_range("Không trích dẫn gì cả.", 0)
    assert not _citations_within_range("Bước 1 [7] — nguồn không tồn tại.", 3)
    assert not _citations_within_range("Số 0 không hợp lệ [0].", 2)


# --- Bao phủ tài liệu: các hàm thuần, không cần DB ------------------------------------------------
# Nhóm test này canh đúng phần bất biến "không bỏ sót tài liệu/đoạn nào" — thứ mà trước đây phụ thuộc
# vào xếp hạng BM25 và trần số nguồn, nên hỏng âm thầm không ai biết.


def _fake_document(document_id: int, *, policy: PolicyCategory | None = None) -> DocumentRef:
    return DocumentRef(
        document_id=document_id,
        version_id=1000 + document_id,
        title=f"Tài liệu {document_id}",
        knowledge_domain=DocumentDomain.POLICY if policy else DocumentDomain.PROJECT,
        document_category=None,
        policy_category=policy,
    )


def _fake_chunks(document: DocumentRef, count: int, *, start: int = 0) -> list[ChunkHit]:
    return [
        ChunkHit(
            chunk_id=document.document_id * 100 + index,
            version_id=document.version_id,
            document_id=document.document_id,
            heading=f"Mục {index}",
            content=f"Nội dung đoạn {index} của tài liệu {document.document_id}",
            score=0.0,
        )
        for index in range(start, start + count)
    ]


# --- compute_due_dates: hạn từng task nối tiếp nhau, không còn "tất cả cùng 1 giờ" -----------------
# Bug gốc (đã fix): thiếu `current += timedelta(minutes=minutes)` khiến MỌI task nhận cùng đúng 1
# giờ hạn = giờ sinh plan, nên vừa sinh xong đã "Trễ hẹn". Nhóm test này canh đúng bất biến "hạn
# tăng dần đúng bằng estimated_minutes", không chỉ canh "có khác nhau" (dễ xanh giả vì lý do khác).


def _fake_template_task(template_task_id: int, *, minutes: int, order: int) -> TemplateTask:
    """Dựng thẳng đối tượng ORM trong bộ nhớ — `compute_due_dates` chỉ đọc field, không đụng DB."""
    return TemplateTask(
        template_task_id=template_task_id,
        version_id=1,
        category=TaskCategory.SETUP,
        title_pattern=f"Task {template_task_id}",
        objective="obj",
        instruction_template="tmpl",
        display_order=order,
        mandatory=True,
        estimated_minutes=minutes,
    )


def _fake_context(tasks: list[TemplateTask]) -> GenerationContext:
    return GenerationContext(
        membership=None,
        project_id=1,
        template_version=SimpleNamespace(version_id=1),
        template_tasks=tasks,
        dependencies=[],
    )


def test_compute_due_dates_advances_time_by_exact_estimated_minutes():
    """3 task 60/45/30 phút, cùng ngày làm việc: hạn phải tăng đúng bằng số phút đó, không đứng yên.

    Đây là hồi quy trực tiếp cho bug đã sửa — trước khi fix, cả 3 task ra CÙNG 1 giá trị `start`.
    """
    start = datetime(2026, 8, 19, 9, 0)  # Thứ Tư — không rơi vào nhánh nhảy cuối tuần
    tasks = [
        _fake_template_task(1, minutes=60, order=1),
        _fake_template_task(2, minutes=45, order=2),
        _fake_template_task(3, minutes=30, order=3),
    ]

    due_dates = compute_due_dates(_fake_context(tasks), start=start)

    assert due_dates[1] == start + timedelta(minutes=60)
    assert due_dates[2] == start + timedelta(minutes=60 + 45)
    assert due_dates[3] == start + timedelta(minutes=60 + 45 + 30)
    # Bất biến chính PM báo lỗi: không được có 2 task nào trùng giờ hạn.
    assert len(set(due_dates.values())) == 3


def test_compute_due_dates_sorts_by_display_order_not_input_order():
    """Đưa vào KHÔNG theo display_order — hàm phải tự sắp trước khi cộng dồn."""
    start = datetime(2026, 8, 19, 9, 0)
    tasks = [
        _fake_template_task(1, minutes=60, order=2),
        _fake_template_task(2, minutes=30, order=1),
    ]

    due_dates = compute_due_dates(_fake_context(tasks), start=start)

    assert due_dates[2] == start + timedelta(minutes=30), "order=1 phải được cộng trước"
    assert due_dates[1] == start + timedelta(minutes=30 + 60)


def test_compute_due_dates_overflows_to_next_working_day_skipping_weekend():
    """Task tràn quá 8h/ngày (480 phút) phải nhảy sang ngày làm việc kế tiếp, bỏ qua T7/CN."""
    start = datetime(2026, 8, 21, 9, 0)  # Thứ Sáu 09:00
    tasks = [
        _fake_template_task(1, minutes=500, order=1),  # > 480 -> tràn ngày
    ]

    due_dates = compute_due_dates(_fake_context(tasks), start=start)

    result = due_dates[1]
    assert result.weekday() == 0, f"Phải rơi vào Thứ Hai (0), thực tế weekday={result.weekday()}"
    assert result > start + timedelta(days=1), "Phải nhảy qua cả T7 (21) và CN (22), không chỉ +1 ngày"


def test_compute_due_dates_falls_back_to_now_when_start_omitted():
    """Không truyền `start` thì rơi về giờ gọi hàm — không phải giá trị cố định/None."""
    before = datetime.now(UTC).replace(tzinfo=None)
    tasks = [_fake_template_task(1, minutes=30, order=1)]

    due_dates = compute_due_dates(_fake_context(tasks))
    after = datetime.now(UTC).replace(tzinfo=None)

    assert before <= due_dates[1] - timedelta(minutes=30) <= after


def test_compute_due_dates_empty_template_returns_empty_dict():
    assert compute_due_dates(_fake_context([])) == {}


def test_batch_documents_never_mixes_policy_categories():
    """Mỗi lô chỉ chứa 1 nhóm chính sách — nhóm nhỏ (vd BENEFIT 1 tài liệu) phải được tóm tắt trong
    ngữ cảnh riêng, không bị lời văn của nhóm lớn lấn át, và luôn có mặt trong nội dung."""
    hr = _fake_document(1, policy=PolicyCategory.HR_POLICY)
    benefit = _fake_document(2, policy=PolicyCategory.BENEFIT)
    outlines = [
        DocumentOutline(document=hr, chunks=_fake_chunks(hr, 2)),
        DocumentOutline(document=benefit, chunks=_fake_chunks(benefit, 1)),
    ]

    batches = _batch_documents(outlines, max_chunks_per_batch=10)

    assert len(batches) == 2, "2 nhóm chính sách khác nhau không được gộp chung 1 lô"
    version_by_batch = [{chunk.version_id for chunk in batch.chunks} for batch in batches]
    assert version_by_batch == [{hr.version_id}, {benefit.version_id}]


def test_batch_documents_splits_oversized_document_without_losing_chunks():
    """Tài liệu dài hơn ngân sách lô KHÔNG bị cắt — tách thành nhiều lô, phần đuôi vẫn được xử lý.

    Đây chính là chỗ thiết kế cũ hỏng: cắt còn N đoạn đầu thì nội dung cuối file biến mất vĩnh viễn.
    """
    document = _fake_document(1)
    outlines = [DocumentOutline(document=document, chunks=_fake_chunks(document, 25))]

    batches = _batch_documents(outlines, max_chunks_per_batch=10)

    assert len(batches) == 3
    assert [len(batch.chunks) for batch in batches] == [10, 10, 5]
    # Không mất, không trùng đoạn nào so với đầu vào.
    all_ids = [chunk.chunk_id for batch in batches for chunk in batch.chunks]
    assert all_ids == [chunk.chunk_id for chunk in outlines[0].chunks]
    # `offset` vẫn cộng dồn đúng theo vị trí, nhưng từ khi chuyển sang Evidence Card nó KHÔNG còn
    # tham gia đánh số trích dẫn (số `[n]` do từng task tự đếm ở `_build_sources_section`).
    assert [batch.offset for batch in batches] == [0, 10, 20]


def test_build_sources_section_covers_every_chunk_even_without_summary():
    """Đoạn nào LLM không tóm tắt được vẫn phải xuất hiện kèm ghi chú + trích dẫn trỏ đúng đoạn.

    Bao phủ là bất biến của CODE: hàm ráp lặp qua từng tài liệu/từng đoạn, nên LLM trả thiếu bao
    nhiêu dòng cũng không làm mất mục nào khỏi lộ trình."""
    document = _fake_document(1)
    chunks = _fake_chunks(document, 3)
    outlines = [DocumentOutline(document=document, chunks=chunks)]

    # LLM chỉ xử lý được đoạn thứ 2, thiếu đoạn 1 và 3. Card khoá theo `chunk_id` chứ KHÔNG theo
    # số thứ tự hiển thị — nhờ vậy card dùng lại được cho task khác mà không kéo theo số `[n]` của
    # task này (đúng chỗ mà cache khoá theo số thứ tự sẽ gán nhầm trích dẫn).
    middle = chunks[1]
    section, citations = _build_sources_section(
        outlines,
        {
            middle.chunk_id: EvidenceCard(
                chunk_id=middle.chunk_id, summary="Ý chính đoạn giữa", exact_quote=None
            )
        },
    )

    assert len(citations) == 3, "Đủ 3 trích dẫn cho 3 đoạn, không phụ thuộc LLM tóm được mấy đoạn"
    assert [c.citation_order for c in citations] == [1, 2, 3]
    assert [c.chunk_id for c in citations] == [chunk.chunk_id for chunk in chunks]
    assert "Ý chính đoạn giữa [2]" in section
    assert section.count(UNSUMMARIZED_CHUNK_NOTE) == 2, "2 đoạn thiếu tóm tắt phải được ghi chú rõ"
    assert READ_FULL_DOCUMENT_NOTICE in section, "Luôn phải nhắc đọc toàn bộ tài liệu gốc"


def test_build_sources_section_groups_policy_documents_by_category():
    """Tài liệu chính sách được gom theo đúng 5 nhóm PM thấy ở Master Template."""
    hr = _fake_document(1, policy=PolicyCategory.HR_POLICY)
    benefit = _fake_document(2, policy=PolicyCategory.BENEFIT)
    outlines = [
        DocumentOutline(document=hr, chunks=_fake_chunks(hr, 1)),
        DocumentOutline(document=benefit, chunks=_fake_chunks(benefit, 1)),
    ]

    section, _ = _build_sources_section(outlines, {})

    assert "### Chính sách nhân sự" in section
    assert "### Phúc lợi" in section


def test_build_sources_section_flags_document_without_chunks():
    """Tài liệu chưa được tách đoạn phải nói thẳng là chưa có nội dung — không lờ đi cho đẹp."""
    document = _fake_document(1)
    section, citations = _build_sources_section([DocumentOutline(document=document, chunks=[])], {})

    assert citations == []
    assert document.title in section
    assert "chưa có nội dung trích xuất" in section


def test_parse_evidence_cards_rejects_chunk_id_outside_batch():
    """`chunk_id` bịa ngoài lô bị bỏ hẳn, không gán nhầm nội dung sang đoạn khác."""
    document = _fake_document(1)
    chunks = _fake_chunks(document, 2)
    batch = _batch_documents([DocumentOutline(document=document, chunks=chunks)])[0]
    text = json.dumps(
        [
            {"chunk_id": chunks[0].chunk_id, "summary": "Y chinh mot", "quote": chunks[0].content},
            {"chunk_id": 999_999, "summary": "Doan khong thuoc lo nay", "quote": "bia"},
        ],
        ensure_ascii=False,
    )

    cards = _parse_evidence_cards(text, batch)

    assert set(cards) == {chunks[0].chunk_id}, "chunk_id lạ phải bị loại, không được nhận"
    assert cards[chunks[0].chunk_id].summary == "Y chinh mot"


def test_parse_evidence_cards_drops_quote_that_is_not_in_source():
    """Quote không có thật trong đoạn bị loại RIÊNG, `summary` vẫn giữ.

    Đây là điểm khác cốt lõi so với bản cũ: trước đây `[n]` chỉ cần là số hợp lệ là được nhận, nên
    câu chữ quanh trích dẫn có thể do LLM tự bịa mà không cơ chế nào phát hiện.
    """
    document = _fake_document(1)
    chunks = _fake_chunks(document, 1)
    batch = _batch_documents([DocumentOutline(document=document, chunks=chunks)])[0]
    text = json.dumps(
        [
            {
                "chunk_id": chunks[0].chunk_id,
                "summary": "Tom tat hop le",
                "quote": "cau nay khong he co trong tai lieu",
            }
        ],
        ensure_ascii=False,
    )

    cards = _parse_evidence_cards(text, batch)

    assert cards[chunks[0].chunk_id].exact_quote is None, "Quote bịa phải bị loại"
    assert cards[chunks[0].chunk_id].summary == "Tom tat hop le", "Không được mất luôn tóm tắt"


def test_parse_evidence_cards_keeps_verbatim_quote_from_source():
    """Quote khớp nguyên văn (lệch hoa-thường/khoảng trắng vẫn tính) được giữ, và giữ bản của TÀI
    LIỆU chứ không phải bản LLM gõ lại."""
    document = _fake_document(1)
    chunks = _fake_chunks(document, 1)
    batch = _batch_documents([DocumentOutline(document=document, chunks=chunks)])[0]
    source_words = chunks[0].content.split()[:4]
    text = json.dumps(
        [
            {
                "chunk_id": chunks[0].chunk_id,
                "summary": "Tom tat",
                "quote": "   ".join(source_words).upper(),
            }
        ],
        ensure_ascii=False,
    )

    cards = _parse_evidence_cards(text, batch)

    assert cards[chunks[0].chunk_id].exact_quote == " ".join(source_words)


def test_parse_evidence_cards_survives_json_wrapped_in_fence():
    """LLM hay bọc ```json dù đã dặn không — bọc thừa không được làm mất cả lô."""
    document = _fake_document(1)
    chunks = _fake_chunks(document, 1)
    batch = _batch_documents([DocumentOutline(document=document, chunks=chunks)])[0]
    payload = json.dumps(
        [{"chunk_id": chunks[0].chunk_id, "summary": "Y chinh", "quote": ""}], ensure_ascii=False
    )

    cards = _parse_evidence_cards("Day la ket qua:\n```json\n" + payload + "\n```", batch)

    assert cards[chunks[0].chunk_id].summary == "Y chinh"


def test_parse_evidence_cards_returns_empty_on_garbage():
    """Trả rác thì lô coi như không có card — không ném lỗi làm hỏng cả lượt sinh."""
    document = _fake_document(1)
    batch = _batch_documents(
        [DocumentOutline(document=document, chunks=_fake_chunks(document, 1))]
    )[0]

    assert _parse_evidence_cards("xin loi toi khong the tra loi", batch) == {}


def test_evidence_block_carries_verified_quote_to_the_writing_prompt():
    """Khối NGUỒN phải mang câu trích ĐÃ xác minh — không có nó thì LLM không có chữ nào của tài
    liệu để bám vào, và "trích dẫn" chỉ còn là con số gắn vào câu nó tự viết (lỗi gốc bản cũ)."""
    document = _fake_document(1)
    chunks = _fake_chunks(document, 2)
    outlines = [DocumentOutline(document=document, chunks=chunks)]
    cards = {
        chunks[0].chunk_id: EvidenceCard(
            chunk_id=chunks[0].chunk_id, summary="Y chinh", exact_quote="cau trich nguyen van"
        )
    }

    block = _build_evidence_block(outlines, cards)

    assert "[1]" in block and "[2]" in block, "Mọi đoạn đều phải có số để trích"
    assert "cau trich nguyen van" in block
    assert "tóm tắt: Y chinh" in block
    # Đoạn 2 không có card: vẫn xuất hiện để LLM biết nguồn tồn tại, chỉ không có gì để trích.
    assert block.count("trích:") == 1


def test_evidence_block_groups_by_policy_category_only_when_multiple():
    """Chia nhóm khi có nhiều nhóm chính sách; chỉ 1 nhóm thì không thêm tiêu đề thừa."""
    hr = _fake_document(1, policy=PolicyCategory.HR_POLICY)
    benefit = _fake_document(2, policy=PolicyCategory.BENEFIT)
    multi = _build_evidence_block(
        [
            DocumentOutline(document=hr, chunks=_fake_chunks(hr, 1)),
            DocumentOutline(document=benefit, chunks=_fake_chunks(benefit, 1)),
        ],
        {},
    )
    single = _build_evidence_block([DocumentOutline(document=hr, chunks=_fake_chunks(hr, 1))], {})

    assert "### Chính sách nhân sự" in multi and "### Phúc lợi" in multi
    assert "###" not in single, "Chỉ 1 nhóm thì không cần tiêu đề nhóm nào"


def test_evidence_block_numbering_matches_sources_section():
    """2 hàm phải đánh CÙNG dãy số. Lệch nhau nghĩa là `[n]` trong nội dung trỏ sai mục nguồn."""
    hr = _fake_document(1, policy=PolicyCategory.HR_POLICY)
    benefit = _fake_document(2, policy=PolicyCategory.BENEFIT)
    outlines = [
        DocumentOutline(document=hr, chunks=_fake_chunks(hr, 3)),
        DocumentOutline(document=benefit, chunks=_fake_chunks(benefit, 2)),
    ]

    block = _build_evidence_block(outlines, cards={})
    _, citations = _build_sources_section(outlines, {})

    numbers_in_block = [int(n) for n in re.findall(r"^\[(\d+)\]", block, flags=re.MULTILINE)]
    assert numbers_in_block == [c.citation_order for c in citations] == [1, 2, 3, 4, 5]
    # Và số phải ứng đúng chunk theo thứ tự — không chỉ trùng độ dài.
    assert [c.chunk_id for c in citations] == [c.chunk_id for o in outlines for c in o.chunks]


def test_validate_instruction_reports_the_actual_problem():
    """Trả mô tả lỗi cụ thể (không phải True/False) để nhánh sửa 1 lần nói đúng chỗ sai cho LLM."""
    good = "## Mục tiêu\nx\n## Các bước thực hiện\nBước 1 [1]"

    assert _validate_instruction(good, 1) is None
    assert "khung markdown" in _validate_instruction("Thiếu tiêu đề", 1)
    assert "ngoài phạm vi" in _validate_instruction("## Mục tiêu\nBước [9]", 2)


def test_plain_text_snippet_strips_only_what_renderer_strips():
    """Snippet phải khớp CHÍNH XÁC văn bản sau khi render ở frontend.

    Bỏ đúng cú pháp mà `renderInline`/`renderMarkdown` nuốt (đậm, code, link, tiền tố dòng). Bỏ ít
    hơn thì còn ký tự markdown không có trong DOM; bỏ nhiều hơn (vd ký tự `|` của bảng — renderer
    hiện không xử lý bảng) thì tạo ra chuỗi không tồn tại trong DOM. Cả hai đều làm việc dò trượt.
    """
    assert (
        _plain_text_snippet("## Tiêu đề mục\nDòng thân bài") == "Tiêu đề mục"
    ), "Lấy dòng đầu tiên có nội dung, vì mỗi dòng render thành 1 khối riêng"
    assert _plain_text_snippet("- **Đậm** và `mã lệnh`") == "Đậm và mã lệnh"
    assert _plain_text_snippet("1. Xem [tài liệu](http://a.b) này") == "Xem tài liệu này"
    assert _plain_text_snippet("> Câu nhắc quan trọng") == "Câu nhắc quan trọng"
    assert _plain_text_snippet("- [ ] Việc cần làm") == "Việc cần làm"
    assert _plain_text_snippet("\n\n   \nNội dung thật") == "Nội dung thật"
    assert _plain_text_snippet("") == ""


def test_plain_text_snippet_is_capped():
    long_line = "x" * 500
    assert len(_plain_text_snippet(long_line)) == SNIPPET_MAX_CHARS


@pytest.mark.asyncio
async def test_regenerate_keeps_same_plan_and_increments_revision(client, ready_project):
    """Regenerate KHÔNG tạo bản ghi plan mới — nếu tạo mới sẽ vi phạm unique index
    `uq_onboarding_plans_one_open_per_membership` (chỉ 1 plan chưa đóng / membership)."""
    first = await _generate_plan(client, ready_project["membership_id"])
    plan_id = first["plan_id"]

    tasks_before = (await client.get(f"/api/v1/onboarding-plans/pm/{plan_id}/tasks")).json()
    old_task_ids = {t["plan_task_id"] for t in tasks_before}

    regen = await client.post(f"/api/v1/onboarding-plans/pm/{plan_id}/regenerate")
    assert regen.status_code == 202, regen.text
    job = (
        await client.get(f"/api/v1/onboarding-plans/pm/generate/{regen.json()['job_id']}")
    ).json()
    assert job["status"] == "DONE", job["error"]
    assert job["plan_id"] == plan_id, "Phải tái dùng đúng plan cũ, không tạo bản mới"

    plan = (
        await client.get(f"/api/v1/onboarding-plans/pm/by-membership/{ready_project['membership_id']}")
    ).json()
    assert plan["revision"] == 2
    assert plan["status"] == "DRAFT", "Regenerate không được đổi trạng thái plan"

    tasks_after = (await client.get(f"/api/v1/onboarding-plans/pm/{plan_id}/tasks")).json()
    assert {t["plan_task_id"] for t in tasks_after}.isdisjoint(old_task_ids), "Task cũ phải bị thay"

    async with AsyncSessionLocal() as db:
        count = len(
            (
                await db.scalars(
                    select(OnboardingPlan.plan_id).where(
                        OnboardingPlan.membership_id == ready_project["membership_id"]
                    )
                )
            ).all()
        )
    assert count == 1, "Chỉ được tồn tại đúng 1 plan cho membership này"


@pytest.mark.asyncio
async def test_approve_then_regenerate_is_rejected(client, ready_project):
    """Sau khi duyệt thì không tạo lại được — vì INV7 chặn lùi status và unique index chặn tạo
    plan DRAFT thứ 2 song song."""
    job = await _generate_plan(client, ready_project["membership_id"])
    plan_id = job["plan_id"]

    approve = await client.patch(
        f"/api/v1/onboarding-plans/pm/{plan_id}/approve", json={"approved_by_user_id": PM_USER_ID}
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "APPROVED"
    assert approve.json()["approved_at"] is not None

    again = await client.patch(
        f"/api/v1/onboarding-plans/pm/{plan_id}/approve", json={"approved_by_user_id": PM_USER_ID}
    )
    assert again.status_code == 409, "Duyệt 2 lần phải bị chặn"

    regen = await client.post(f"/api/v1/onboarding-plans/pm/{plan_id}/regenerate")
    assert regen.status_code == 409, "Plan đã duyệt không được tạo lại"


@pytest.mark.asyncio
async def test_generate_rejected_when_membership_already_has_open_plan(client, ready_project):
    await _generate_plan(client, ready_project["membership_id"])
    response = await client.post(
        "/api/v1/onboarding-plans/pm/generate", json={"membership_id": ready_project["membership_id"]}
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_inv7_trigger_blocks_backward_status(client, ready_project):
    """Kiểm chứng trigger DB thật `enforce_onboarding_plan_forward_status`, không phải chỉ tin
    tầng service chặn."""
    job = await _generate_plan(client, ready_project["membership_id"])
    plan_id = job["plan_id"]
    await client.patch(
        f"/api/v1/onboarding-plans/pm/{plan_id}/approve", json={"approved_by_user_id": PM_USER_ID}
    )

    with pytest.raises(Exception) as exc_info:
        async with AsyncSessionLocal() as db:
            plan = await db.get(OnboardingPlan, plan_id)
            plan.status = PlanStatus.DRAFT
            await db.commit()
    assert "backward" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_edit_task_allowed_in_draft_and_blocked_after_approve(client, ready_project):
    """SoT rule 11 — PlanTask là snapshot thực thi: duyệt xong thì không sửa ngầm dưới chân
    Engineer đang làm."""
    job = await _generate_plan(client, ready_project["membership_id"])
    plan_id = job["plan_id"]
    tasks = (await client.get(f"/api/v1/onboarding-plans/pm/{plan_id}/tasks")).json()
    task_id = tasks[0]["plan_task_id"]

    edit = await client.patch(
        f"/api/v1/plan-tasks/pm/{task_id}", json={"title": "PM sửa tay tiêu đề"}
    )
    assert edit.status_code == 200
    assert edit.json()["title"] == "PM sửa tay tiêu đề"

    await client.patch(
        f"/api/v1/onboarding-plans/pm/{plan_id}/approve", json={"approved_by_user_id": PM_USER_ID}
    )
    blocked = await client.patch(
        f"/api/v1/plan-tasks/pm/{task_id}", json={"title": "Sửa sau khi duyệt"}
    )
    assert blocked.status_code == 409


@pytest.mark.asyncio
async def test_plan_only_uses_five_active_categories(client, ready_project):
    """Tài liệu thuộc 2 nhóm đang hoãn (CONVENTION/FIRST_TASK) không được dùng làm nguồn."""
    await _add_project_document(ready_project["project_id"], "CONVENTION", "KHONG DUNG - convention")
    await _add_project_document(ready_project["project_id"], "FIRST_TASK", "KHONG DUNG - first task")

    job = await _generate_plan(client, ready_project["membership_id"])
    tasks = (await client.get(f"/api/v1/onboarding-plans/pm/{job['plan_id']}/tasks")).json()

    used_titles = {s["document_title"] for t in tasks for s in t["sources"]}
    assert not any(title.startswith("KHONG DUNG") for title in used_titles)


@pytest.mark.asyncio
async def test_generate_job_reports_six_named_steps(client, ready_project):
    """Tiến độ trả về đúng 6 bước theo thứ tự cố định, có duration thật để FE vẽ."""
    job = await _generate_plan(client, ready_project["membership_id"])
    assert [step["key"] for step in job["steps"]] == [
        "load_template",
        "merge_company_core",
        "collect_project_docs",
        "map_task_sources",
        "generate_content",
        "validate_and_persist",
    ]
    assert all(step["duration_ms"] is not None for step in job["steps"])
    assert job["total_duration_ms"] is not None
    assert job["correlation_id"]


@pytest.mark.asyncio
async def test_company_core_documents_are_merged_as_sources(client, ready_project):
    """Bước 2 phải thật sự gộp Company Core: task định hướng phải trích được tài liệu POLICY."""
    job = await _generate_plan(client, ready_project["membership_id"])
    tasks = (await client.get(f"/api/v1/onboarding-plans/pm/{job['plan_id']}/tasks")).json()

    used_document_ids = {s["document_id"] for t in tasks for s in t["sources"]}
    async with AsyncSessionLocal() as db:
        policy_count = len(
            (
                await db.scalars(
                    select(KnowledgeDocument.document_id).where(
                        KnowledgeDocument.document_id.in_(used_document_ids),
                        KnowledgeDocument.knowledge_domain == DocumentDomain.POLICY,
                    )
                )
            ).all()
        )
    assert policy_count > 0, "Phải có ít nhất 1 nguồn từ Company Core"


@pytest.mark.asyncio
async def test_approved_template_version_is_the_one_used(client, ready_project):
    """Plan phải gắn đúng TemplateVersion đang APPROVED, không phải version DRAFT nào khác."""
    job = await _generate_plan(client, ready_project["membership_id"])
    plan = (
        await client.get(f"/api/v1/onboarding-plans/pm/by-membership/{ready_project['membership_id']}")
    ).json()
    assert plan["template_version_id"] == ready_project["version_id"]
    assert job["plan_id"] == plan["plan_id"]

    async with AsyncSessionLocal() as db:
        template = await db.scalar(
            select(OnboardingTemplate).where(
                OnboardingTemplate.project_id == ready_project["project_id"]
            )
        )
        approved = await db.scalar(
            select(TemplateVersion).where(
                TemplateVersion.template_id == template.template_id,
                TemplateVersion.status == TemplateVersionStatus.APPROVED,
            )
        )
    assert approved.version_id == plan["template_version_id"]



@pytest.mark.asyncio
async def test_regenerate_engineer_plan_resyncs_from_reference(client, ready_project):
    """"Tạo lại" trên plan của kỹ sư = ĐỒNG BỘ LẠI từ lộ trình chuẩn hiện tại (không gọi AI).

    Đây là cách duy nhất PM đẩy bản chuẩn mới xuống 1 kỹ sư cụ thể — và vẫn phải chủ động bấm, chứ
    không tự động, để không đổi ngầm nội dung dưới chân người đang làm dở (SoT rule 11).
    """
    job = await _generate_plan(client, ready_project["membership_id"])
    plan_id = job["plan_id"]

    reference_tasks = (
        await client.get(f"/api/v1/onboarding-plans/pm/{ready_project['reference_plan_id']}/tasks")
    ).json()
    await client.patch(
        f"/api/v1/plan-tasks/pm/{reference_tasks[0]['plan_task_id']}",
        json={"title": "Ban chuan phien ban moi"},
    )

    regen = await client.post(f"/api/v1/onboarding-plans/pm/{plan_id}/regenerate")
    assert regen.status_code == 202
    regen_job = (
        await client.get(f"/api/v1/onboarding-plans/pm/generate/{regen.json()['job_id']}")
    ).json()
    assert regen_job["status"] == "DONE", regen_job["error"]
    assert regen_job["plan_id"] == plan_id, "Ghi đè tại chỗ, không tạo plan thứ 2 cho cùng kỹ sư"
    assert "Sao chép" in _step_detail(regen_job, "generate_content")

    after = (await client.get(f"/api/v1/onboarding-plans/pm/{plan_id}/tasks")).json()
    assert after[0]["title"] == "Ban chuan phien ban moi"


@pytest.mark.asyncio
async def test_get_reference_plan_endpoint(client, test_data, project_with_docs):
    """Endpoint cho trang "Onboarding Plan": 404 khi chưa có, trả đúng bản chuẩn sau khi tạo."""
    missing = await client.get(
        f"/api/v1/onboarding-plans/pm/reference?project_id={project_with_docs['project_id']}"
    )
    assert missing.status_code == 404

    job = await _generate_reference_plan(client, project_with_docs["project_id"])
    found = await client.get(
        f"/api/v1/onboarding-plans/pm/reference?project_id={project_with_docs['project_id']}"
    )
    assert found.status_code == 200
    body = found.json()
    assert body["plan_id"] == job["plan_id"]
    assert body["project_id"] == project_with_docs["project_id"]
    assert body["membership_id"] is None
