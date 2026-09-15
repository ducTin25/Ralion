import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from src.config import get_settings
from src.model.blocker import Blocker
from src.model.document_version import DocumentVersion
from src.model.enums import (
    BlockerCategory,
    BlockerStatus,
    DocumentCategory,
    DocumentDomain,
    DocumentStatus,
    PlanStatus,
    ProjectRole,
    TaskCategory,
    TaskStatus,
    TemplateScope,
    TemplateStatus,
    TemplateVersionStatus,
    VersionStatus,
)
from src.model.knowledge_document import KnowledgeDocument
from src.model.onboarding_plan import OnboardingPlan
from src.model.onboarding_template import OnboardingTemplate
from src.model.plan_task import PlanTask
from src.model.plan_task_source import PlanTaskSource
from src.model.project import Project
from src.model.project_membership import ProjectMembership
from src.model.session import AsyncSessionLocal
from src.model.task_dependency import TaskDependency
from src.model.template_task import TemplateTask
from src.model.template_version import TemplateVersion
from src.model.user import User


@dataclass
class MemberPortalData:
    member_email: str
    project_id: int
    project_without_plan_id: int
    foreign_project_id: int
    plan_id: int
    done_task_id: int
    blocked_task_id: int
    transition_task_id: int
    first_task_id: int
    first_pr_id: int
    dependency_task_id: int
    foreign_task_id: int
    membership_id: int
    active_source_version_id: int


@pytest_asyncio.fixture
async def member_portal_data(client):
    suffix = uuid.uuid4().hex[:8]

    async with AsyncSessionLocal() as db:
        admin = User(email=f"admin-{suffix}@onboarding.dev", display_name="Test Admin")
        member = User(email=f"member-{suffix}@onboarding.dev", display_name="Nguyễn Văn Test")
        other_member = User(email=f"other-{suffix}@onboarding.dev", display_name="Other Engineer")
        db.add_all([admin, member, other_member])
        await db.flush()

        # `settings.demo_member_email` (lối tắt "member demo" cũ) đã bị bỏ khi đổi sang xác thực
        # theo project context thật (commit 7a10757). Xác thực các request dưới đây bằng đúng cơ
        # chế hiện tại — header X-User-Id (autouse `allow_header_user_context` ở conftest.py bật
        # sẵn cho toàn bộ tests/), y hệt cách `test_policy_acknowledgement.py::sign_in_as` mô
        # phỏng đăng nhập.
        client.headers["X-User-Id"] = str(member.user_id)

        project = Project(key=f"MEM{suffix.upper()}", name="Member Portal", created_by_admin_id=admin.user_id)
        project_without_plan = Project(
            key=f"NOP{suffix.upper()}", name="Project Without Plan", created_by_admin_id=admin.user_id
        )
        foreign_project = Project(
            key=f"FOR{suffix.upper()}", name="Foreign Project", created_by_admin_id=admin.user_id
        )
        db.add_all([project, project_without_plan, foreign_project])
        await db.flush()

        membership = ProjectMembership(
            user_id=member.user_id,
            project_id=project.project_id,
            project_role=ProjectRole.ENGINEER,
            assigned_by_admin_id=admin.user_id,
        )
        membership_without_plan = ProjectMembership(
            user_id=member.user_id,
            project_id=project_without_plan.project_id,
            project_role=ProjectRole.ENGINEER,
            assigned_by_admin_id=admin.user_id,
        )
        foreign_membership = ProjectMembership(
            user_id=other_member.user_id,
            project_id=foreign_project.project_id,
            project_role=ProjectRole.ENGINEER,
            assigned_by_admin_id=admin.user_id,
        )
        db.add_all([membership, membership_without_plan, foreign_membership])
        await db.flush()

        template = OnboardingTemplate(
            project_id=project.project_id,
            scope=TemplateScope.PROJECT,
            name=f"Member template {suffix}",
            description="Template for member API tests",
            status=TemplateStatus.APPROVED,
        )
        db.add(template)
        await db.flush()
        version = TemplateVersion(
            template_id=template.template_id,
            version_no=1,
            status=TemplateVersionStatus.APPROVED,
            approved_by_user_id=admin.user_id,
            approved_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add(version)
        await db.flush()

        categories = [
            TaskCategory.ORIENTATION,
            TaskCategory.SETUP,
            TaskCategory.CODEBASE,
            TaskCategory.FIRST_TASK,
            TaskCategory.FIRST_PR,
            TaskCategory.CONVENTION,
        ]
        template_tasks: list[TemplateTask] = []
        for order, category in enumerate(categories, start=1):
            template_task = TemplateTask(
                version_id=version.version_id,
                category=category,
                title_pattern=f"Task {order}",
                objective=f"Objective {order}",
                instruction_template=f"Instruction {order}",
                display_order=order,
                mandatory=order != 3,
                estimated_minutes=order * 15,
            )
            db.add(template_task)
            template_tasks.append(template_task)
        await db.flush()

        dependency_one = TaskDependency(
            predecessor_task_id=template_tasks[0].template_task_id,
            successor_task_id=template_tasks[1].template_task_id,
        )
        dependency_two = TaskDependency(
            predecessor_task_id=template_tasks[1].template_task_id,
            successor_task_id=template_tasks[5].template_task_id,
        )
        db.add_all([dependency_one, dependency_two])

        plan = OnboardingPlan(
            membership_id=membership.membership_id,
            template_version_id=version.version_id,
            status=PlanStatus.ACTIVE,
            approved_by_user_id=admin.user_id,
            approved_at=datetime.now(UTC).replace(tzinfo=None),
        )
        foreign_plan = OnboardingPlan(
            membership_id=foreign_membership.membership_id,
            template_version_id=version.version_id,
            status=PlanStatus.ACTIVE,
        )
        db.add_all([plan, foreign_plan])
        await db.flush()

        statuses = [
            TaskStatus.DONE,
            TaskStatus.IN_PROGRESS,
            TaskStatus.NOT_STARTED,
            TaskStatus.NOT_STARTED,
            TaskStatus.NOT_STARTED,
            TaskStatus.IN_PROGRESS,
        ]
        tasks: list[PlanTask] = []
        for template_task, status in zip(template_tasks, statuses, strict=True):
            task = PlanTask(
                plan_id=plan.plan_id,
                template_task_id=template_task.template_task_id,
                title=template_task.title_pattern,
                instruction=template_task.instruction_template,
                display_order=template_task.display_order,
                mandatory=template_task.mandatory,
                status=status,
                started_at=datetime.now(UTC).replace(tzinfo=None) if status != TaskStatus.NOT_STARTED else None,
                completed_at=datetime.now(UTC).replace(tzinfo=None) if status == TaskStatus.DONE else None,
            )
            db.add(task)
            tasks.append(task)
        foreign_task = PlanTask(
            plan_id=foreign_plan.plan_id,
            template_task_id=template_tasks[0].template_task_id,
            title="Foreign task",
            instruction="Not visible",
            display_order=1,
            mandatory=True,
        )
        db.add(foreign_task)
        await db.flush()

        blocker = Blocker(
            plan_task_id=tasks[1].plan_task_id,
            reported_by_membership_id=membership.membership_id,
            category=BlockerCategory.TECHNICAL,
            reason="Open test blocker",
            status=BlockerStatus.OPEN,
        )
        db.add(blocker)

        active_document = KnowledgeDocument(
            project_id=project.project_id,
            created_by_user_id=admin.user_id,
            knowledge_domain=DocumentDomain.PROJECT,
            document_category=DocumentCategory.OVERVIEW,
            title="Active guide",
            source_url="https://example.test/active-guide",
            status=DocumentStatus.ACTIVE,
        )
        archived_document = KnowledgeDocument(
            project_id=project.project_id,
            created_by_user_id=admin.user_id,
            knowledge_domain=DocumentDomain.PROJECT,
            document_category=DocumentCategory.OVERVIEW,
            title="Archived guide",
            source_url="https://example.test/archived-guide",
            status=DocumentStatus.ARCHIVED,
        )
        db.add_all([active_document, archived_document])
        await db.flush()
        active_version = DocumentVersion(
            document_id=active_document.document_id,
            version_no="1",
            embedding_model_version="test-model",
            revision_no=1,
            storage_uri="test/active.pdf",
            checksum=f"active-{suffix}",
            status=VersionStatus.ACTIVE,
        )
        archived_document_version = DocumentVersion(
            document_id=archived_document.document_id,
            version_no="1",
            embedding_model_version="test-model",
            revision_no=1,
            storage_uri="test/archived.pdf",
            checksum=f"archived-{suffix}",
            status=VersionStatus.ACTIVE,
        )
        db.add_all([active_version, archived_document_version])
        await db.flush()
        db.add_all(
            [
                PlanTaskSource(
                    plan_task_id=tasks[1].plan_task_id,
                    version_id=active_version.version_id,
                    citation_note="Read sections 1-2",
                ),
                PlanTaskSource(
                    plan_task_id=tasks[1].plan_task_id,
                    version_id=archived_document_version.version_id,
                ),
            ]
        )
        await db.commit()

        data = MemberPortalData(
            member_email=member.email,
            project_id=project.project_id,
            project_without_plan_id=project_without_plan.project_id,
            foreign_project_id=foreign_project.project_id,
            plan_id=plan.plan_id,
            done_task_id=tasks[0].plan_task_id,
            blocked_task_id=tasks[1].plan_task_id,
            transition_task_id=tasks[2].plan_task_id,
            first_task_id=tasks[3].plan_task_id,
            first_pr_id=tasks[4].plan_task_id,
            dependency_task_id=tasks[5].plan_task_id,
            foreign_task_id=foreign_task.plan_task_id,
            membership_id=membership.membership_id,
            active_source_version_id=active_version.version_id,
        )
        cleanup = {
            "blocker_ids": [blocker.blocker_id],
            "plan_ids": [plan.plan_id, foreign_plan.plan_id],
            "version_id": version.version_id,
            "template_id": template.template_id,
            "document_ids": [active_document.document_id, archived_document.document_id],
            "user_ids": [member.user_id, other_member.user_id, admin.user_id],
            "project_ids": [project.project_id, project_without_plan.project_id, foreign_project.project_id],
        }

    try:
        yield data
    finally:
        client.headers.pop("X-User-Id", None)
        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(Blocker).where(
                    Blocker.plan_task_id.in_(
                        select(PlanTask.plan_task_id).where(PlanTask.plan_id.in_(cleanup["plan_ids"]))
                    )
                )
            )
            await db.execute(delete(PlanTaskSource).where(PlanTaskSource.plan_task_id.in_([
                data.blocked_task_id,
            ])))
            await db.execute(delete(PlanTask).where(PlanTask.plan_id.in_(cleanup["plan_ids"])))
            await db.execute(delete(OnboardingPlan).where(OnboardingPlan.plan_id.in_(cleanup["plan_ids"])))
            await db.execute(
                delete(TaskDependency).where(
                    TaskDependency.successor_task_id.in_(
                        select(TemplateTask.template_task_id).where(TemplateTask.version_id == cleanup["version_id"])
                    )
                )
            )
            await db.execute(delete(TemplateTask).where(TemplateTask.version_id == cleanup["version_id"]))
            await db.execute(delete(DocumentVersion).where(DocumentVersion.document_id.in_(cleanup["document_ids"])))
            await db.execute(delete(KnowledgeDocument).where(KnowledgeDocument.document_id.in_(cleanup["document_ids"])))
            await db.execute(delete(TemplateVersion).where(TemplateVersion.version_id == cleanup["version_id"]))
            await db.execute(delete(OnboardingTemplate).where(OnboardingTemplate.template_id == cleanup["template_id"]))
            await db.execute(
                delete(ProjectMembership).where(ProjectMembership.project_id.in_(cleanup["project_ids"]))
            )
            await db.execute(delete(Project).where(Project.project_id.in_(cleanup["project_ids"])))
            await db.execute(delete(User).where(User.user_id.in_(cleanup["user_ids"])))
            await db.commit()


@pytest.mark.asyncio
async def test_member_projects_only_returns_active_engineer_memberships(client, member_portal_data):
    response = await client.get("/api/v1/member/projects")

    assert response.status_code == 200
    data = response.json()
    assert data["member"]["email"] == member_portal_data.member_email
    assert [project["project_id"] for project in data["projects"]] == [
        member_portal_data.project_id,
        member_portal_data.project_without_plan_id,
    ]
    assert data["projects"][0]["plan_status"] == "ACTIVE"
    assert data["projects"][1]["plan_status"] is None


@pytest.mark.asyncio
async def test_member_checklist_excludes_first_contribution_from_groups_and_progress(
    client, member_portal_data
):
    response = await client.get("/api/v1/member/checklist", params={"project_id": member_portal_data.project_id})

    assert response.status_code == 200
    data = response.json()
    assert data["membership_id"] == member_portal_data.membership_id
    assert data["progress"] == {"completed": 1, "total": 3, "percent": 33}
    assert {group["category"] for group in data["groups"]}.isdisjoint({"FIRST_TASK", "FIRST_PR"})
    tasks = [task for group in data["groups"] for task in group["tasks"]]
    blocked_task = next(task for task in tasks if task["plan_task_id"] == member_portal_data.blocked_task_id)
    assert blocked_task["dependencies_met"] is True
    assert blocked_task["open_blocker_count"] == 1
    assert blocked_task["can_complete"] is False


@pytest.mark.asyncio
async def test_member_cannot_access_first_contribution_tasks(client, member_portal_data):
    first_task = await client.get(
        f"/api/v1/member/plan-tasks/{member_portal_data.first_task_id}"
    )
    first_pr = await client.get(f"/api/v1/member/plan-tasks/{member_portal_data.first_pr_id}")

    assert first_task.status_code == 404
    assert first_pr.status_code == 404


@pytest.mark.asyncio
async def test_member_first_pr_mutation_is_not_exposed(client, member_portal_data):
    response = await client.put(
        f"/api/v1/member/onboarding-plans/{member_portal_data.plan_id}/first-pr",
        json={"first_pr_url": "https://github.com/example/repo/pull/42"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_member_task_detail_only_returns_active_document_sources(client, member_portal_data):
    response = await client.get(f"/api/v1/member/plan-tasks/{member_portal_data.blocked_task_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["objective"] == "Objective 2"
    assert data["instruction"] == "Instruction 2"
    assert data["dependencies"] == [
        {"plan_task_id": member_portal_data.done_task_id, "title": "Task 1", "status": "DONE"}
    ]
    assert [source["version_id"] for source in data["sources"]] == [member_portal_data.active_source_version_id]


@pytest.mark.asyncio
async def test_member_cannot_read_foreign_project_or_task(client, member_portal_data):
    checklist = await client.get(
        "/api/v1/member/checklist", params={"project_id": member_portal_data.foreign_project_id}
    )
    task = await client.get(f"/api/v1/member/plan-tasks/{member_portal_data.foreign_task_id}")

    assert checklist.status_code == 404
    assert task.status_code == 404


@pytest.mark.asyncio
async def test_member_project_without_published_plan_returns_conflict(client, member_portal_data):
    response = await client.get(
        "/api/v1/member/checklist", params={"project_id": member_portal_data.project_without_plan_id}
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_member_can_start_complete_and_repeat_transition_idempotently(client, member_portal_data):
    endpoint = f"/api/v1/member/plan-tasks/{member_portal_data.transition_task_id}/status"
    started = await client.patch(endpoint, json={"status": "IN_PROGRESS"})
    started_again = await client.patch(endpoint, json={"status": "IN_PROGRESS"})
    completed = await client.patch(endpoint, json={"status": "DONE"})
    completed_again = await client.patch(endpoint, json={"status": "DONE"})
    backward = await client.patch(endpoint, json={"status": "IN_PROGRESS"})

    assert started.status_code == 200
    assert started.json()["started_at"] is not None
    assert started_again.status_code == 200
    assert completed.status_code == 200
    assert completed.json()["completed_at"] is not None
    assert completed_again.status_code == 200
    assert backward.status_code == 409


@pytest.mark.asyncio
async def test_member_cannot_complete_task_with_open_blocker(client, member_portal_data):
    response = await client.patch(
        f"/api/v1/member/plan-tasks/{member_portal_data.blocked_task_id}/status",
        json={"status": "DONE"},
    )

    assert response.status_code == 409
    assert "blocker" in response.json()["detail"]


@pytest.mark.asyncio
async def test_member_cannot_complete_task_with_unfinished_dependency(client, member_portal_data):
    response = await client.patch(
        f"/api/v1/member/plan-tasks/{member_portal_data.dependency_task_id}/status",
        json={"status": "DONE"},
    )

    assert response.status_code == 409
    assert "dependency" in response.json()["detail"]


@pytest.mark.asyncio
async def test_member_must_start_task_before_completing(client, member_portal_data):
    response = await client.patch(
        f"/api/v1/member/plan-tasks/{member_portal_data.transition_task_id}/status",
        json={"status": "DONE"},
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_demo_member_identity_is_disabled_in_production(client, member_portal_data):
    """Header `X-User-Id` (lối tắt dev) chỉ có tác dụng khi `allow_header_user_context=True` —
    `validate_production_auth` (src/config.py) bắt buộc cờ này False ở production, nên đây mới là
    cơ chế thật cần kiểm, thay cho `settings.demo_member_email` đã bị bỏ (test cũ tên khác nhưng
    cùng ý định: xác nhận lối tắt xác thực dev không hoạt động ở production)."""
    settings = get_settings()
    original = settings.allow_header_user_context
    settings.allow_header_user_context = False
    try:
        response = await client.get("/api/v1/member/projects")
    finally:
        settings.allow_header_user_context = original

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_member_lists_only_own_project_blockers(client, member_portal_data):
    response = await client.get(
        "/api/v1/member/blockers", params={"project_id": member_portal_data.project_id}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["plan_task_id"] == member_portal_data.blocked_task_id
    assert data[0]["task_title"] == "Task 2"
    assert data[0]["status"] == "OPEN"
    assert "routing" not in data[0]
    assert "sla" not in data[0]


@pytest.mark.asyncio
async def test_member_creates_blocker_without_changing_task_status(client, member_portal_data):
    # Endpoint nhận multipart/form-data (UC-08, đính kèm file) chứ không còn JSON body — dùng
    # `data=` thay `json=` để khớp `Annotated[BlockerCategory, Form()]`/`Annotated[str, Form()]`.
    response = await client.post(
        f"/api/v1/member/plan-tasks/{member_portal_data.transition_task_id}/blockers",
        data={"category": "TECHNICAL", "reason": "Không kết nối được service local sau khi setup."},
    )
    task = await client.get(f"/api/v1/member/plan-tasks/{member_portal_data.transition_task_id}")

    assert response.status_code == 201
    assert response.json()["status"] == "OPEN"
    assert response.json()["category"] == "TECHNICAL"
    assert task.status_code == 200
    assert task.json()["status"] == "NOT_STARTED"
    assert task.json()["open_blocker_count"] == 1


@pytest.mark.asyncio
async def test_member_cannot_create_blocker_for_foreign_or_done_task(client, member_portal_data):
    payload = {"category": "OTHER", "reason": "Một blocker hợp lệ nhưng không thuộc task được phép."}
    foreign = await client.post(
        f"/api/v1/member/plan-tasks/{member_portal_data.foreign_task_id}/blockers", data=payload
    )
    done = await client.post(
        f"/api/v1/member/plan-tasks/{member_portal_data.done_task_id}/blockers", data=payload
    )

    assert foreign.status_code == 404
    assert done.status_code == 409


@pytest.mark.asyncio
async def test_member_blocker_reason_is_validated(client, member_portal_data):
    # `json=` (thay vì `data=`) cũng ra 422 nhưng vì sai content-type (FastAPI từ chối form thiếu
    # field), không phải vì validate độ dài lý do (member_onboarding_service.py:483) — trước đây
    # trùng hợp cùng status code nên không lộ ra. Dùng `data=` để test đúng nhánh cần kiểm.
    response = await client.post(
        f"/api/v1/member/plan-tasks/{member_portal_data.transition_task_id}/blockers",
        data={"category": "TECHNICAL", "reason": "ngắn"},
    )

    assert response.status_code == 422

    whitespace = await client.post(
        f"/api/v1/member/plan-tasks/{member_portal_data.transition_task_id}/blockers",
        data={"category": "TECHNICAL", "reason": "               "},
    )
    assert whitespace.status_code == 422
