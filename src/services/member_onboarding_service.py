from collections import defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dto.response.member_onboarding_response_dto import (
    MemberBlockerResponseDTO,
    MemberChecklistProgressResponseDTO,
    MemberChecklistProjectResponseDTO,
    MemberChecklistResponseDTO,
    MemberProfileResponseDTO,
    MemberProjectResponseDTO,
    MemberProjectsResponseDTO,
    MemberTaskDependencyResponseDTO,
    MemberTaskDetailResponseDTO,
    MemberTaskGroupResponseDTO,
    MemberTaskSourceResponseDTO,
    MemberTaskSummaryResponseDTO,
)
from src.dto.response.notification_response_dto import TaskNotificationResponseDTO
from src.dto.response.plan_task_response_dto import PlanTaskCitationResponseDTO
from src.model.blocker import Blocker
from src.model.blocker_attachment import BlockerAttachment
from src.model.document_version import DocumentVersion
from src.model.enums import (
    BlockerCategory,
    BlockerStatus,
    DocumentStatus,
    MembershipStatus,
    PlanStatus,
    ProjectRole,
    ProjectStatus,
    TaskCategory,
    TaskStatus,
    VersionStatus,
)
from src.model.knowledge_document import KnowledgeDocument
from src.model.onboarding_plan import OnboardingPlan
from src.model.plan_task import PlanTask
from src.model.plan_task_source import PlanTaskSource
from src.model.project import Project
from src.model.project_membership import ProjectMembership
from src.model.task_dependency import TaskDependency
from src.model.template_task import TemplateTask
from src.model.user import User
from src.services import blocker_service, storage_service
from src.services.plan_task_service import list_task_citations

# UC-08: "Chọn category, nhập lý do và có thể tải attachment" — tuỳ chọn nhưng có giới hạn để
# tránh lạm dụng (báo blocker không phải chỗ upload file lớn tuỳ ý).
MAX_BLOCKER_ATTACHMENTS = 5
MAX_BLOCKER_ATTACHMENT_BYTES = 15 * 1024 * 1024  # 15MB/file
ALLOWED_BLOCKER_ATTACHMENT_PREFIXES = ("image/", "video/")


class MemberOnboardingError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


PUBLISHED_PLAN_STATUSES = (
    PlanStatus.APPROVED,
    PlanStatus.ACTIVE,
    PlanStatus.PROJECT_READY,
    PlanStatus.ONBOARDING_CLOSED,
)
MEMBER_CHECKLIST_CATEGORIES = (
    TaskCategory.COMPANY,
    TaskCategory.ORIENTATION,
    TaskCategory.ACCESS,
    TaskCategory.SETUP,
    TaskCategory.CODEBASE,
    TaskCategory.CONVENTION,
)
# Task được coi là "sắp đến hạn" khi due_at còn trong vòng 20 PHÚT tới (chưa qua hạn) -- theo yêu
# cầu PM: cửa sổ ngắn để chuông chỉ nhắc việc THỰC SỰ cận kề, không nhắc cả những task còn nguyên
# ngày. Cùng ngưỡng dùng cho chuông thông báo của PM (pm_dashboard_service.list_notifications) --
# 2 bên phải khớp nhau, nếu không PM và Engineer sẽ tranh cãi vì thấy 2 danh sách khác nhau cho
# cùng 1 task.
DUE_SOON_WINDOW_MINUTES = 20
NOTIFICATION_LIMIT = 20


def _profile(member: User) -> MemberProfileResponseDTO:
    return MemberProfileResponseDTO(
        user_id=member.user_id,
        email=member.email,
        display_name=member.display_name,
    )


async def _published_plan(db: AsyncSession, membership_id: int) -> OnboardingPlan | None:
    return await db.scalar(
        select(OnboardingPlan)
        .where(
            OnboardingPlan.membership_id == membership_id,
            OnboardingPlan.status.in_(PUBLISHED_PLAN_STATUSES),
        )
        .order_by(OnboardingPlan.plan_id.desc())
        .limit(1)
    )


async def list_projects(db: AsyncSession, member: User) -> MemberProjectsResponseDTO:
    rows = (
        await db.execute(
            select(ProjectMembership, Project)
            .join(Project, Project.project_id == ProjectMembership.project_id)
            .where(
                ProjectMembership.user_id == member.user_id,
                ProjectMembership.project_role == ProjectRole.ENGINEER,
                ProjectMembership.status == MembershipStatus.ACTIVE,
                Project.status == ProjectStatus.ACTIVE,
            )
            .order_by(Project.name, Project.project_id)
        )
    ).all()

    projects: list[MemberProjectResponseDTO] = []
    for membership, project in rows:
        plan = await _published_plan(db, membership.membership_id)
        projects.append(
            MemberProjectResponseDTO(
                project_id=project.project_id,
                membership_id=membership.membership_id,
                key=project.key,
                name=project.name,
                project_role=membership.project_role,
                plan_id=plan.plan_id if plan else None,
                plan_status=plan.status if plan else None,
            )
        )
    return MemberProjectsResponseDTO(member=_profile(member), projects=projects)


async def _membership_and_project(
    db: AsyncSession, member_id: int, project_id: int
) -> tuple[ProjectMembership, Project]:
    row = (
        await db.execute(
            select(ProjectMembership, Project)
            .join(Project, Project.project_id == ProjectMembership.project_id)
            .where(
                ProjectMembership.user_id == member_id,
                ProjectMembership.project_id == project_id,
                ProjectMembership.project_role == ProjectRole.ENGINEER,
                ProjectMembership.status == MembershipStatus.ACTIVE,
                Project.status == ProjectStatus.ACTIVE,
            )
        )
    ).one_or_none()
    if row is None:
        raise MemberOnboardingError(404, "Bạn không có Engineer Membership đang hoạt động trong dự án này")
    return row


async def _plan_for_project(
    db: AsyncSession, member_id: int, project_id: int
) -> tuple[OnboardingPlan, ProjectMembership, Project]:
    membership, project = await _membership_and_project(db, member_id, project_id)
    plan = await _published_plan(db, membership.membership_id)
    if plan is None:
        raise MemberOnboardingError(409, "Dự án chưa có Onboarding Plan được phát hành cho bạn")
    return plan, membership, project


async def _task_rows(db: AsyncSession, plan_id: int) -> list[tuple[PlanTask, TemplateTask]]:
    result = await db.execute(
        select(PlanTask, TemplateTask)
        .join(TemplateTask, TemplateTask.template_task_id == PlanTask.template_task_id)
        .where(
            PlanTask.plan_id == plan_id,
            TemplateTask.category.in_(MEMBER_CHECKLIST_CATEGORIES),
        )
        .order_by(PlanTask.display_order)
    )
    return list(result.all())


async def _task_context(
    db: AsyncSession, plan: OnboardingPlan, rows: list[tuple[PlanTask, TemplateTask]]
) -> tuple[dict[int, list[MemberTaskDependencyResponseDTO]], dict[int, int], dict[int, int]]:
    task_by_template_id = {task.template_task_id: task for task, _ in rows}
    template_ids = list(task_by_template_id)
    dependencies: dict[int, list[MemberTaskDependencyResponseDTO]] = defaultdict(list)
    if template_ids:
        dependency_rows = (
            await db.execute(select(TaskDependency).where(TaskDependency.successor_task_id.in_(template_ids)))
        ).scalars()
        for dependency in dependency_rows:
            predecessor = task_by_template_id.get(dependency.predecessor_task_id)
            successor = task_by_template_id.get(dependency.successor_task_id)
            if predecessor is not None and successor is not None:
                dependencies[successor.plan_task_id].append(
                    MemberTaskDependencyResponseDTO(
                        plan_task_id=predecessor.plan_task_id,
                        title=predecessor.title,
                        status=predecessor.status,
                    )
                )

    plan_task_ids = [task.plan_task_id for task, _ in rows]
    blocker_counts: dict[int, int] = defaultdict(int)
    if plan_task_ids:
        blocker_rows = await db.execute(
            select(Blocker.plan_task_id, func.count(Blocker.blocker_id))
            .where(
                Blocker.plan_task_id.in_(plan_task_ids),
                Blocker.status != BlockerStatus.RESOLVED,
            )
            .group_by(Blocker.plan_task_id)
        )
        blocker_counts.update({plan_task_id: count for plan_task_id, count in blocker_rows})
    source_counts: dict[int, int] = defaultdict(int)
    if plan_task_ids:
        source_rows = await db.execute(
            select(PlanTaskSource.plan_task_id, func.count(PlanTaskSource.task_source_id))
            .where(PlanTaskSource.plan_task_id.in_(plan_task_ids))
            .group_by(PlanTaskSource.plan_task_id)
        )
        source_counts.update({plan_task_id: count for plan_task_id, count in source_rows})
    return dependencies, blocker_counts, source_counts


def _summary(
    task: PlanTask,
    template_task: TemplateTask,
    plan: OnboardingPlan,
    dependencies: list[MemberTaskDependencyResponseDTO],
    open_blocker_count: int,
    source_count: int,
) -> MemberTaskSummaryResponseDTO:
    dependencies_met = all(dependency.status == TaskStatus.DONE for dependency in dependencies)
    closed = plan.status == PlanStatus.ONBOARDING_CLOSED
    lock_reason = "Onboarding Plan đã đóng" if closed else None

    # Cùng định nghĩa "trễ hạn" với pm_progress_service._phase... (PM's MemberProgressDrawer):
    # due_at đã qua VÀ task chưa DONE -- 2 phía (PM/Engineer) phải khớp số, tránh 1 bên thấy trễ
    # còn bên kia thì không cho cùng 1 task.
    now = datetime.now(UTC).replace(tzinfo=None)
    is_overdue = task.due_at is not None and task.due_at < now and task.status != TaskStatus.DONE
    is_due_soon = (
        not is_overdue
        and task.due_at is not None
        and task.status != TaskStatus.DONE
        and task.due_at <= now + timedelta(minutes=DUE_SOON_WINDOW_MINUTES)
    )

    return MemberTaskSummaryResponseDTO(
        plan_task_id=task.plan_task_id,
        title=task.title,
        category=template_task.category,
        display_order=task.display_order,
        mandatory=task.mandatory,
        estimated_minutes=template_task.estimated_minutes,
        status=task.status,
        due_at=task.due_at,
        is_overdue=is_overdue,
        is_due_soon=is_due_soon,
        started_at=task.started_at,
        completed_at=task.completed_at,
        dependencies_met=dependencies_met,
        open_blocker_count=open_blocker_count,
        source_count=source_count,
        is_locked=closed,
        lock_reason=lock_reason,
        can_start=task.status == TaskStatus.NOT_STARTED and not closed,
        can_complete=(
            task.status == TaskStatus.IN_PROGRESS and dependencies_met and open_blocker_count == 0 and not closed
        ),
    )


async def get_checklist(db: AsyncSession, member: User, project_id: int) -> MemberChecklistResponseDTO:
    plan, membership, project = await _plan_for_project(db, member.user_id, project_id)
    rows = await _task_rows(db, plan.plan_id)
    dependencies, blocker_counts, source_counts = await _task_context(db, plan, rows)

    grouped: dict[TaskCategory, list[MemberTaskSummaryResponseDTO]] = defaultdict(list)
    for task, template_task in rows:
        grouped[template_task.category].append(
            _summary(
                task,
                template_task,
                plan,
                dependencies[task.plan_task_id],
                blocker_counts[task.plan_task_id],
                source_counts[task.plan_task_id],
            )
        )

    mandatory_tasks = [task for task, _ in rows if task.mandatory]
    completed = sum(task.status == TaskStatus.DONE for task in mandatory_tasks)
    total = len(mandatory_tasks)
    percent = round(completed * 100 / total) if total else 0

    return MemberChecklistResponseDTO(
        member=_profile(member),
        project=MemberChecklistProjectResponseDTO(project_id=project.project_id, key=project.key, name=project.name),
        membership_id=membership.membership_id,
        plan_id=plan.plan_id,
        plan_status=plan.status,
        approved_at=plan.approved_at,
        progress=MemberChecklistProgressResponseDTO(completed=completed, total=total, percent=percent),
        groups=[
            MemberTaskGroupResponseDTO(category=category, tasks=grouped[category])
            for category in MEMBER_CHECKLIST_CATEGORIES
            if grouped[category]
        ],
    )


async def list_notifications(
    db: AsyncSession, member: User, project_id: int
) -> list[TaskNotificationResponseDTO]:
    """Task sắp/đã trễ hạn của chính kỹ sư này, cho dropdown chuông thông báo Member Portal.

    Đi qua `_plan_for_project` giống hệt `get_checklist` để dùng chung 1 định nghĩa "plan nào
    đang phát hành cho kỹ sư" -- không tự query PlanTask theo cách khác, tránh 2 nơi lệch nhau.
    """
    plan, _membership, _project = await _plan_for_project(db, member.user_id, project_id)
    now = datetime.now(UTC).replace(tzinfo=None)
    soon = now + timedelta(minutes=DUE_SOON_WINDOW_MINUTES)
    rows = (
        await db.execute(
            select(PlanTask)
            .join(TemplateTask, TemplateTask.template_task_id == PlanTask.template_task_id)
            .where(
                PlanTask.plan_id == plan.plan_id,
                TemplateTask.category.in_(MEMBER_CHECKLIST_CATEGORIES),
                PlanTask.due_at.is_not(None),
                PlanTask.due_at <= soon,
                PlanTask.status != TaskStatus.DONE,
            )
            .order_by(PlanTask.due_at.asc())
            .limit(NOTIFICATION_LIMIT)
        )
    ).scalars()
    return [
        TaskNotificationResponseDTO(
            plan_task_id=task.plan_task_id,
            title=task.title,
            due_at=task.due_at,
            is_overdue=task.due_at < now,
        )
        for task in rows
    ]


async def _authorized_task(
    db: AsyncSession, member_id: int, task_id: int, *, for_update: bool = False
) -> tuple[PlanTask, TemplateTask, OnboardingPlan]:
    query = (
        select(PlanTask, TemplateTask, OnboardingPlan)
        .join(OnboardingPlan, OnboardingPlan.plan_id == PlanTask.plan_id)
        .join(ProjectMembership, ProjectMembership.membership_id == OnboardingPlan.membership_id)
        .join(Project, Project.project_id == ProjectMembership.project_id)
        .join(TemplateTask, TemplateTask.template_task_id == PlanTask.template_task_id)
        .where(
            PlanTask.plan_task_id == task_id,
            ProjectMembership.user_id == member_id,
            ProjectMembership.project_role == ProjectRole.ENGINEER,
            ProjectMembership.status == MembershipStatus.ACTIVE,
            Project.status == ProjectStatus.ACTIVE,
            OnboardingPlan.status.in_(PUBLISHED_PLAN_STATUSES),
            TemplateTask.category.in_(MEMBER_CHECKLIST_CATEGORIES),
        )
    )
    if for_update:
        query = query.with_for_update(of=PlanTask)
    row = (await db.execute(query)).one_or_none()
    if row is None:
        raise MemberOnboardingError(404, "Không tìm thấy task thuộc Onboarding Plan của bạn")
    return row


async def _task_sources(db: AsyncSession, task_id: int) -> list[MemberTaskSourceResponseDTO]:
    rows = (
        await db.execute(
            select(PlanTaskSource, DocumentVersion, KnowledgeDocument)
            .join(DocumentVersion, DocumentVersion.version_id == PlanTaskSource.version_id)
            .join(KnowledgeDocument, KnowledgeDocument.document_id == DocumentVersion.document_id)
            .where(
                PlanTaskSource.plan_task_id == task_id,
                DocumentVersion.status == VersionStatus.ACTIVE,
                KnowledgeDocument.status == DocumentStatus.ACTIVE,
            )
            .order_by(KnowledgeDocument.title, DocumentVersion.version_no.desc())
        )
    ).all()
    return [
        MemberTaskSourceResponseDTO(
            document_id=document.document_id,
            version_id=version.version_id,
            title=document.title,
            source_url=document.source_url,
            citation_note=source.citation_note,
        )
        for source, version, document in rows
    ]


async def _task_detail_from_entities(
    db: AsyncSession,
    task: PlanTask,
    template_task: TemplateTask,
    plan: OnboardingPlan,
) -> MemberTaskDetailResponseDTO:
    rows = await _task_rows(db, plan.plan_id)
    dependencies, blocker_counts, source_counts = await _task_context(db, plan, rows)
    task_dependencies = dependencies[task.plan_task_id]
    summary = _summary(
        task,
        template_task,
        plan,
        task_dependencies,
        blocker_counts[task.plan_task_id],
        source_counts[task.plan_task_id],
    )
    citations_by_task = await list_task_citations(db, plan.plan_id)
    return MemberTaskDetailResponseDTO(
        **summary.model_dump(),
        plan_id=plan.plan_id,
        plan_status=plan.status,
        objective=template_task.objective,
        instruction=task.instruction,
        dependencies=task_dependencies,
        sources=await _task_sources(db, task.plan_task_id),
        citations=[
            PlanTaskCitationResponseDTO.from_detail(citation)
            for citation in citations_by_task.get(task.plan_task_id, [])
        ],
    )


async def get_task_detail(db: AsyncSession, member: User, task_id: int) -> MemberTaskDetailResponseDTO:
    task, template_task, plan = await _authorized_task(db, member.user_id, task_id)
    return await _task_detail_from_entities(db, task, template_task, plan)


async def update_task_status(
    db: AsyncSession, member: User, task_id: int, target_status: TaskStatus
) -> MemberTaskDetailResponseDTO:
    if target_status not in (TaskStatus.IN_PROGRESS, TaskStatus.DONE):
        raise MemberOnboardingError(422, "Chỉ hỗ trợ chuyển task sang IN_PROGRESS hoặc DONE")

    task, template_task, plan = await _authorized_task(db, member.user_id, task_id, for_update=True)
    if task.status == target_status:
        return await _task_detail_from_entities(db, task, template_task, plan)
    if task.status == TaskStatus.DONE:
        raise MemberOnboardingError(409, "Task đã hoàn thành và không thể chuyển lùi trạng thái")
    if target_status == TaskStatus.IN_PROGRESS and task.status != TaskStatus.NOT_STARTED:
        raise MemberOnboardingError(409, "Task không ở trạng thái có thể bắt đầu")
    if target_status == TaskStatus.DONE and task.status != TaskStatus.IN_PROGRESS:
        raise MemberOnboardingError(409, "Phải bắt đầu task trước khi đánh dấu hoàn thành")

    # Các cột timestamp hiện tại là TIMESTAMP WITHOUT TIME ZONE; lưu UTC-naive
    # nhất quán với schema/seed hiện hữu cho tới khi có migration timezone riêng.
    now = datetime.now(UTC).replace(tzinfo=None)
    if target_status == TaskStatus.IN_PROGRESS:
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = task.started_at or now
    else:
        rows = await _task_rows(db, plan.plan_id)
        dependencies, blocker_counts, _ = await _task_context(db, plan, rows)
        if any(dependency.status != TaskStatus.DONE for dependency in dependencies[task.plan_task_id]):
            raise MemberOnboardingError(409, "Chưa thể hoàn thành task vì dependency chưa DONE")
        if blocker_counts[task.plan_task_id] > 0:
            raise MemberOnboardingError(409, "Chưa thể hoàn thành task khi còn blocker chưa xử lý")
        task.status = TaskStatus.DONE
        task.started_at = task.started_at or now
        task.completed_at = now

    await db.commit()
    await db.refresh(task)
    return await _task_detail_from_entities(db, task, template_task, plan)


def _blocker_response(
    blocker: Blocker, task: PlanTask, attachments: list | None = None
) -> MemberBlockerResponseDTO:
    return MemberBlockerResponseDTO(
        blocker_id=blocker.blocker_id,
        plan_task_id=task.plan_task_id,
        task_title=task.title,
        category=blocker.category,
        reason=blocker.reason,
        status=blocker.status,
        reported_at=blocker.reported_at,
        resolved_at=blocker.resolved_at,
        attachments=attachments or [],
    )


async def list_blockers(db: AsyncSession, member: User, project_id: int) -> list[MemberBlockerResponseDTO]:
    membership, _ = await _membership_and_project(db, member.user_id, project_id)
    rows = (
        await db.execute(
            select(Blocker, PlanTask)
            .join(PlanTask, PlanTask.plan_task_id == Blocker.plan_task_id)
            .join(OnboardingPlan, OnboardingPlan.plan_id == PlanTask.plan_id)
            .join(TemplateTask, TemplateTask.template_task_id == PlanTask.template_task_id)
            .where(
                OnboardingPlan.membership_id == membership.membership_id,
                OnboardingPlan.status.in_(PUBLISHED_PLAN_STATUSES),
                TemplateTask.category.in_(MEMBER_CHECKLIST_CATEGORIES),
            )
            .order_by(Blocker.reported_at.desc(), Blocker.blocker_id.desc())
        )
    ).all()
    attachments = await blocker_service.attachments_by_blocker(db, [blocker.blocker_id for blocker, _ in rows])
    return [
        _blocker_response(blocker, task, attachments.get(blocker.blocker_id, [])) for blocker, task in rows
    ]


def _validate_attachment(file: UploadFile) -> None:
    mime_type = file.content_type or ""
    if not mime_type.startswith(ALLOWED_BLOCKER_ATTACHMENT_PREFIXES):
        raise MemberOnboardingError(
            422, f"Chỉ nhận ảnh hoặc video làm minh chứng — '{file.filename}' không hợp lệ."
        )


async def create_blocker(
    db: AsyncSession,
    member: User,
    task_id: int,
    category: BlockerCategory,
    reason: str,
    attachments: list[UploadFile] | None = None,
) -> MemberBlockerResponseDTO:
    task, _, plan = await _authorized_task(db, member.user_id, task_id, for_update=True)
    if task.status == TaskStatus.DONE:
        raise MemberOnboardingError(409, "Không thể báo blocker cho task đã hoàn thành")

    normalized_reason = reason.strip()
    if len(normalized_reason) < 10:
        raise MemberOnboardingError(422, "Mô tả blocker cần ít nhất 10 ký tự.")
    reason = normalized_reason

    files = [f for f in (attachments or []) if f.filename]
    if len(files) > MAX_BLOCKER_ATTACHMENTS:
        raise MemberOnboardingError(
            422, f"Chỉ được đính kèm tối đa {MAX_BLOCKER_ATTACHMENTS} file/blocker."
        )
    for file in files:
        _validate_attachment(file)

    blocker = Blocker(
        plan_task_id=task.plan_task_id,
        reported_by_membership_id=plan.membership_id,
        category=category,
        reason=reason.strip(),
        status=BlockerStatus.OPEN,
    )
    db.add(blocker)
    await db.flush()  # cần blocker_id để đặt folder Cloudinary trước khi upload

    attachment_rows: list[BlockerAttachment] = []
    for file in files:
        content = await file.read()
        if len(content) > MAX_BLOCKER_ATTACHMENT_BYTES:
            raise MemberOnboardingError(
                422,
                f"'{file.filename}' vượt quá {MAX_BLOCKER_ATTACHMENT_BYTES // (1024 * 1024)}MB.",
            )
        if not content:
            continue
        url = storage_service.upload_blocker_attachment_bytes(content, blocker.blocker_id, file.filename)
        attachment_rows.append(
            BlockerAttachment(
                blocker_id=blocker.blocker_id,
                storage_key=url,
                file_name=file.filename,
                mime_type=file.content_type or "application/octet-stream",
            )
        )
    db.add_all(attachment_rows)

    await db.commit()
    await db.refresh(blocker)
    return _blocker_response(
        blocker, task, [blocker_service.attachment_response(row) for row in attachment_rows]
    )
