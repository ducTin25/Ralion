"""Trang "Tổng quan" của PM — SoT §21 (TV1): "Progress dashboard và close onboarding". Tổng hợp số
liệu đã có sẵn rải rác ở các trang khác (Thành viên, Blocker Engineer, Tài liệu dự án, Master
Template) vào 1 màn hình, không tính lại theo cách khác — nếu lệch với các trang kia thì PM sẽ mất
niềm tin vào cả 2 nơi.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dto.response.notification_response_dto import PmNotificationResponseDTO
from src.dto.response.pm_blocker_response_dto import PmBlockerResponseDTO
from src.dto.response.pm_dashboard_response_dto import (
    PmDashboardEngineerOverdueDTO,
    PmDashboardResponseDTO,
)
from src.model.blocker import Blocker
from src.model.enums import (
    BlockerStatus,
    DocumentDomain,
    DocumentStatus,
    IngestionJobStatus,
    IngestionJobType,
    PlanStatus,
    ProjectRole,
    TaskStatus,
    TemplateVersionStatus,
)
from src.model.ingestion_job import IngestionJob
from src.model.knowledge_document import KnowledgeDocument
from src.model.onboarding_plan import OnboardingPlan
from src.model.onboarding_template import OnboardingTemplate
from src.model.plan_task import PlanTask
from src.model.project import Project
from src.model.project_membership import ProjectMembership
from src.model.template_task import TemplateTask
from src.model.template_version import TemplateVersion
from src.model.user import User
from src.observability import get_project_ai_cost_usd
from src.services import blocker_service
from src.services.plan_generation.steps import TASK_CATEGORY_DOCUMENT_MAP

TOP_BLOCKERS_LIMIT = 5
TOP_OVERDUE_ENGINEERS_LIMIT = 5
# Cùng ngưỡng "sắp đến hạn" với member_onboarding_service.DUE_SOON_WINDOW_MINUTES -- 2 chuông
# thông báo (PM + Engineer) phải khớp nhau cho cùng 1 task.
DUE_SOON_WINDOW_MINUTES = 20
NOTIFICATION_LIMIT = 20


class PmDashboardError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


async def _plan_counts(db: AsyncSession, project_id: int) -> tuple[int, int, int, int]:
    """(engineer_count, with_plan_count, active_count, done_count) — cùng định nghĩa với
    `MembersView.tsx` phía FE (đã có sẵn: đã có Plan / chưa có Plan / đã hoàn tất) để 2 nơi
    không lệch số."""
    engineer_ids = list(
        (
            await db.scalars(
                select(ProjectMembership.membership_id).where(
                    ProjectMembership.project_id == project_id,
                    ProjectMembership.project_role == ProjectRole.ENGINEER,
                )
            )
        ).all()
    )
    if not engineer_ids:
        return 0, 0, 0, 0

    plan_rows = (
        await db.execute(
            select(OnboardingPlan.membership_id, OnboardingPlan.status).where(
                OnboardingPlan.membership_id.in_(engineer_ids)
            )
        )
    ).all()
    with_plan_ids = {membership_id for membership_id, _ in plan_rows}
    done_ids = {
        membership_id
        for membership_id, status in plan_rows
        if status == PlanStatus.ONBOARDING_CLOSED
    }
    return len(engineer_ids), len(with_plan_ids), len(with_plan_ids - done_ids), len(done_ids)


async def _overdue_task_stats(
    db: AsyncSession, project_id: int
) -> tuple[int, list[PmDashboardEngineerOverdueDTO]]:
    """Tổng số task quá hạn trong dự án + top N Engineer trễ hẹn nhiều nhất.

    "Quá hạn" tính GIỐNG HỆT `pm_progress_service`: `due_at` đã qua VÀ task chưa `DONE` — 2 nơi
    dùng chung định nghĩa, tránh PM thấy 2 con số khác nhau cho cùng 1 khái niệm.
    """
    now = datetime.now(UTC).replace(tzinfo=None)
    rows = (
        await db.execute(
            select(ProjectMembership.membership_id, User.display_name, PlanTask.plan_task_id)
            .select_from(PlanTask)
            .join(OnboardingPlan, OnboardingPlan.plan_id == PlanTask.plan_id)
            .join(ProjectMembership, ProjectMembership.membership_id == OnboardingPlan.membership_id)
            .join(User, User.user_id == ProjectMembership.user_id)
            .where(
                ProjectMembership.project_id == project_id,
                ProjectMembership.project_role == ProjectRole.ENGINEER,
                PlanTask.due_at.is_not(None),
                PlanTask.due_at < now,
                PlanTask.status != TaskStatus.DONE,
            )
        )
    ).all()

    per_engineer: dict[int, dict[str, object]] = {}
    for membership_id, engineer_name, _task_id in rows:
        bucket = per_engineer.setdefault(membership_id, {"name": engineer_name, "count": 0})
        bucket["count"] = int(bucket["count"]) + 1

    ranked = sorted(per_engineer.items(), key=lambda item: item[1]["count"], reverse=True)
    top = [
        PmDashboardEngineerOverdueDTO(
            membership_id=membership_id, engineer_name=str(data["name"]), overdue_count=int(data["count"])
        )
        for membership_id, data in ranked[:TOP_OVERDUE_ENGINEERS_LIMIT]
    ]
    return len(rows), top


async def _document_coverage(db: AsyncSession, project_id: int) -> tuple[int, int]:
    """Bao nhiêu / tổng bao nhiêu nhóm tài liệu bắt buộc đã có ít nhất 1 tài liệu ACTIVE — cùng bộ
    5 nhóm mà pipeline sinh plan thật sự tiêu thụ (`TASK_CATEGORY_DOCUMENT_MAP`), không phải liệt kê
    lại tay dễ lệch khi nhóm tài liệu đổi."""
    required_categories = {c for values in TASK_CATEGORY_DOCUMENT_MAP.values() for c in values}
    present_categories = set(
        (
            await db.scalars(
                select(KnowledgeDocument.document_category)
                .where(
                    KnowledgeDocument.project_id == project_id,
                    KnowledgeDocument.knowledge_domain == DocumentDomain.PROJECT,
                    KnowledgeDocument.status == DocumentStatus.ACTIVE,
                    KnowledgeDocument.document_category.in_(required_categories),
                )
                .distinct()
            )
        ).all()
    )
    return len(present_categories), len(required_categories)


async def _template_status(db: AsyncSession, project_id: int) -> tuple[bool, int]:
    template = await db.scalar(
        select(OnboardingTemplate).where(OnboardingTemplate.project_id == project_id)
    )
    if template is None:
        return False, 0
    version = await db.scalar(
        select(TemplateVersion).where(
            TemplateVersion.template_id == template.template_id,
            TemplateVersion.status == TemplateVersionStatus.APPROVED,
        )
    )
    if version is None:
        return False, 0
    task_count = int(
        await db.scalar(
            select(func.count(TemplateTask.template_task_id)).where(
                TemplateTask.version_id == version.version_id
            )
        )
    )
    return True, task_count


async def get_dashboard(db: AsyncSession, project_id: int) -> PmDashboardResponseDTO:
    project = await db.get(Project, project_id)
    if project is None:
        raise PmDashboardError(404, "Không tìm thấy dự án.")

    engineer_count, with_plan_count, active_count, done_count = await _plan_counts(db, project_id)
    overdue_task_count, engineers_with_most_overdue = await _overdue_task_stats(db, project_id)
    document_group_count, document_group_total = await _document_coverage(db, project_id)
    template_approved, template_task_count = await _template_status(db, project_id)

    open_blocker_count = int(
        await db.scalar(
            select(func.count(Blocker.blocker_id))
            .select_from(Blocker)
            .join(PlanTask, PlanTask.plan_task_id == Blocker.plan_task_id)
            .join(OnboardingPlan, OnboardingPlan.plan_id == PlanTask.plan_id)
            .join(ProjectMembership, ProjectMembership.membership_id == OnboardingPlan.membership_id)
            .where(
                ProjectMembership.project_id == project_id,
                ProjectMembership.project_role == ProjectRole.ENGINEER,
                Blocker.status != BlockerStatus.RESOLVED,
            )
        )
    )
    all_blockers = await blocker_service.list_for_pm(db, project_id)
    oldest_open: list[PmBlockerResponseDTO] = [
        b for b in all_blockers if b.status != BlockerStatus.RESOLVED
    ][:TOP_BLOCKERS_LIMIT]

    # Nguồn NGOÀI Postgres duy nhất trong hàm này — cố ý KHÔNG để lỗi/timeout Langfuse chặn cả
    # dashboard (`get_project_ai_cost_usd` tự nuốt lỗi, trả `None`), khác các số liệu khác ở trên
    # đều suy ra thẳng từ DB nội bộ.
    total_ai_cost_usd = await get_project_ai_cost_usd(project_id)

    return PmDashboardResponseDTO(
        project_id=project.project_id,
        project_key=project.key,
        project_name=project.name,
        engineer_count=engineer_count,
        with_plan_count=with_plan_count,
        active_count=active_count,
        done_count=done_count,
        open_blocker_count=open_blocker_count,
        overdue_task_count=overdue_task_count,
        document_group_count=document_group_count,
        document_group_total=document_group_total,
        template_approved=template_approved,
        template_task_count=template_task_count,
        oldest_open_blockers=oldest_open,
        engineers_with_most_overdue=engineers_with_most_overdue,
        total_ai_cost_usd=total_ai_cost_usd,
    )


async def list_notifications(db: AsyncSession, project_id: int) -> list[PmNotificationResponseDTO]:
    """Task sắp/đã trễ hạn của MỌI Engineer trong dự án, cho dropdown chuông thông báo PM.

    Cùng điều kiện "quá hạn" với `_overdue_task_stats` ở trên (due_at đã qua + chưa DONE), cộng
    thêm cửa sổ "sắp đến hạn" (DUE_SOON_WINDOW_MINUTES). Sắp theo due_at tăng dần nên task quá hạn
    lâu nhất lên đầu, rồi tới task sắp đến hạn gần nhất.
    """
    now = datetime.now(UTC).replace(tzinfo=None)
    soon = now + timedelta(minutes=DUE_SOON_WINDOW_MINUTES)
    rows = (
        await db.execute(
            select(PlanTask, User.display_name, ProjectMembership.membership_id)
            .select_from(PlanTask)
            .join(OnboardingPlan, OnboardingPlan.plan_id == PlanTask.plan_id)
            .join(ProjectMembership, ProjectMembership.membership_id == OnboardingPlan.membership_id)
            .join(User, User.user_id == ProjectMembership.user_id)
            .where(
                ProjectMembership.project_id == project_id,
                ProjectMembership.project_role == ProjectRole.ENGINEER,
                PlanTask.due_at.is_not(None),
                PlanTask.due_at <= soon,
                PlanTask.status != TaskStatus.DONE,
            )
            .order_by(PlanTask.due_at.asc())
            .limit(NOTIFICATION_LIMIT)
        )
    ).all()
    notifications = [
        PmNotificationResponseDTO(
            notification_id=f"task:{task.plan_task_id}:{task.due_at.isoformat()}",
            kind="TASK_DUE",
            title=task.title,
            message=("Overdue" if task.due_at < now else "Due soon"),
            created_at=task.due_at,
            is_overdue=task.due_at < now,
            engineer_name=engineer_name,
            membership_id=membership_id,
            plan_task_id=task.plan_task_id,
        )
        for task, engineer_name, membership_id in rows
    ]

    completed_jobs = list(
        (
            await db.scalars(
                select(IngestionJob)
                .where(
                    IngestionJob.project_id == project_id,
                    IngestionJob.status == IngestionJobStatus.SUCCEEDED,
                    IngestionJob.job_type.in_(
                        [IngestionJobType.GITHUB_SYNC, IngestionJobType.RULE_MINING]
                    ),
                )
                .order_by(IngestionJob.finished_at.desc())
                .limit(NOTIFICATION_LIMIT)
            )
        ).all()
    )
    for job in completed_jobs:
        if job.finished_at is None:
            continue
        if job.job_type == IngestionJobType.GITHUB_SYNC:
            kind = "GITHUB_SYNC_COMPLETED"
            title = "GitHub sync finished"
            message = "All fetched documents have finished indexing."
        else:
            kind = "CONVENTION_SCAN_COMPLETED"
            title = "Convention scan finished"
            message = (
                f"{job.families_created_count} conventions created · "
                f"{job.families_updated_count} reinforced"
            )
        notifications.append(
            PmNotificationResponseDTO(
                notification_id=f"job:{job.ingestion_job_id}",
                kind=kind,
                title=title,
                message=message,
                created_at=job.finished_at,
            )
        )
    return sorted(notifications, key=lambda item: item.created_at, reverse=True)[
        :NOTIFICATION_LIMIT
    ]
