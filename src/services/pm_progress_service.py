"""PM xem tiến độ 1 Engineer cụ thể — SoT §17.2: "Theo dõi tiến độ, deadline và blocker của từng
plan". Tách file riêng (không nhét vào `member_onboarding_service.py`) vì đây là góc nhìn của PM,
không phải của Engineer — PM được xem TOÀN BỘ category (kể cả những nhóm Member Portal ẩn), khác
hẳn phạm vi `MEMBER_CHECKLIST_CATEGORIES` chỉ dành cho chính Engineer tự xem checklist của mình.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dto.response.pm_member_progress_response_dto import (
    PmMemberProgressResponseDTO,
    PmProgressTaskDTO,
)
from src.model.enums import ProjectRole, TaskStatus
from src.model.onboarding_plan import OnboardingPlan
from src.model.plan_task import PlanTask
from src.model.project_membership import ProjectMembership
from src.model.template_task import TemplateTask
from src.model.user import User
from src.services import blocker_service
from src.services.member_onboarding_service import PUBLISHED_PLAN_STATUSES


class PmProgressError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


async def get_member_progress(
    db: AsyncSession, project_id: int, membership_id: int
) -> PmMemberProgressResponseDTO:
    row = (
        await db.execute(
            select(ProjectMembership, User)
            .join(User, User.user_id == ProjectMembership.user_id)
            .where(
                ProjectMembership.membership_id == membership_id,
                ProjectMembership.project_id == project_id,
                ProjectMembership.project_role == ProjectRole.ENGINEER,
            )
        )
    ).one_or_none()
    if row is None:
        raise PmProgressError(404, "Không tìm thấy Engineer này trong dự án.")
    membership, engineer = row

    # Plan CHƯA phát hành (DRAFT) không tính là "tiến độ" để PM xem — Engineer chưa nhìn thấy plan
    # đó, không có gì để theo dõi tiến độ thật. Khớp đúng khái niệm `PUBLISHED_PLAN_STATUSES` mà
    # Member Portal đang dùng để không có 2 định nghĩa "plan nào coi là đang chạy" lệch nhau.
    plan = await db.scalar(
        select(OnboardingPlan)
        .where(
            OnboardingPlan.membership_id == membership_id,
            OnboardingPlan.status.in_(PUBLISHED_PLAN_STATUSES),
        )
        .order_by(OnboardingPlan.plan_id.desc())
        .limit(1)
    )

    tasks: list[PmProgressTaskDTO] = []
    overdue_count = 0
    if plan is not None:
        rows = (
            await db.execute(
                select(PlanTask, TemplateTask)
                .join(TemplateTask, TemplateTask.template_task_id == PlanTask.template_task_id)
                .where(PlanTask.plan_id == plan.plan_id)
                .order_by(PlanTask.display_order)
            )
        ).all()
        now = datetime.now(UTC).replace(tzinfo=None)
        # `rows` đã sort theo display_order — nhớ due_at của task trước làm start_at cho task sau,
        # khớp đúng cách compute_due_dates() sinh chúng (xem plan_task_service.list_task_details,
        # cùng 1 quy tắc, viết lại ở đây vì DTO/nguồn dữ liệu khác nhau). Task đầu tiên: suy ngược
        # từ due_at của chính nó — KHÔNG dùng `plan.created_at` (lúc DB tạo dòng, khác giờ PM chọn
        # ở modal khi sinh, không phản ánh đúng nếu PM sửa tay due_at sau này).
        previous_due_at = None
        for task, template_task in rows:
            is_overdue = (
                task.due_at is not None and task.due_at < now and task.status != TaskStatus.DONE
            )
            if is_overdue:
                overdue_count += 1
            if previous_due_at is not None:
                start_at = previous_due_at
            elif task.due_at is not None:
                start_at = task.due_at - timedelta(minutes=template_task.estimated_minutes)
            else:
                start_at = None
            tasks.append(
                PmProgressTaskDTO(
                    plan_task_id=task.plan_task_id,
                    title=task.title,
                    category=template_task.category,
                    mandatory=task.mandatory,
                    status=task.status,
                    start_at=start_at,
                    due_at=task.due_at,
                    is_overdue=is_overdue,
                )
            )
            previous_due_at = task.due_at

    mandatory_total = sum(1 for t in tasks if t.mandatory)
    mandatory_done = sum(1 for t in tasks if t.mandatory and t.status == TaskStatus.DONE)
    percent = round(mandatory_done * 100 / mandatory_total) if mandatory_total else 0

    blockers = await blocker_service.list_for_membership(db, project_id, membership_id)

    return PmMemberProgressResponseDTO(
        membership_id=membership.membership_id,
        engineer_name=engineer.display_name,
        engineer_email=engineer.email,
        plan_id=plan.plan_id if plan else None,
        plan_status=plan.status if plan else None,
        approved_at=plan.approved_at if plan else None,
        completed_count=mandatory_done,
        total_count=mandatory_total,
        percent=percent,
        overdue_count=overdue_count,
        tasks=tasks,
        blockers=blockers,
    )
