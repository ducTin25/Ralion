from dataclasses import dataclass

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dto.request.project_membership_request_dto import (
    ProjectMembershipCreateRequestDTO,
    ProjectMembershipUpdateRequestDTO,
)
from src.dto.response.membership_context_response_dto import (
    ActiveMembershipResponseDTO,
    MembershipCardDTO,
    MembershipPlanDTO,
)
from src.model.blocker import Blocker
from src.model.enums import (
    BlockerStatus,
    MembershipStatus,
    PlanStatus,
    ProjectRole,
    ProjectStatus,
    TaskStatus,
)
from src.model.onboarding_plan import OnboardingPlan
from src.model.plan_task import PlanTask
from src.model.project import Project
from src.model.project_membership import ProjectMembership
from src.model.user import User

# ---------------------------------------------------------------------------
# Ngữ cảnh membership của chính người đang đăng nhập (màn hình chọn dự án)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MembershipSelectionError(Exception):
    code: str
    message: str
    status_code: int


def _task_stats_subquery():
    return (
        select(
            PlanTask.plan_id.label("plan_id"),
            func.count(PlanTask.plan_task_id)
            .filter(PlanTask.mandatory.is_(True))
            .label("required_total"),
            func.count(PlanTask.plan_task_id)
            .filter(and_(PlanTask.mandatory.is_(True), PlanTask.status == TaskStatus.DONE))
            .label("required_done"),
        )
        .group_by(PlanTask.plan_id)
        .subquery()
    )


def _blocker_stats_subquery():
    return (
        select(
            PlanTask.plan_id.label("plan_id"),
            func.count(Blocker.blocker_id)
            .filter(Blocker.status.in_((BlockerStatus.OPEN, BlockerStatus.ROUTED)))
            .label("open_blockers"),
        )
        .outerjoin(Blocker, Blocker.plan_task_id == PlanTask.plan_task_id)
        .group_by(PlanTask.plan_id)
        .subquery()
    )


async def list_selectable_memberships(
    db: AsyncSession,
    user_id: int,
    status: MembershipStatus = MembershipStatus.ACTIVE,
) -> list[MembershipCardDTO]:
    task_stats = _task_stats_subquery()
    blocker_stats = _blocker_stats_subquery()
    statement = (
        select(
            ProjectMembership,
            Project,
            OnboardingPlan,
            task_stats.c.required_done,
            task_stats.c.required_total,
            blocker_stats.c.open_blockers,
        )
        .join(Project, Project.project_id == ProjectMembership.project_id)
        .outerjoin(
            OnboardingPlan,
            and_(
                OnboardingPlan.membership_id == ProjectMembership.membership_id,
                OnboardingPlan.status != PlanStatus.ONBOARDING_CLOSED,
            ),
        )
        .outerjoin(task_stats, task_stats.c.plan_id == OnboardingPlan.plan_id)
        .outerjoin(blocker_stats, blocker_stats.c.plan_id == OnboardingPlan.plan_id)
        .where(
            ProjectMembership.user_id == user_id,
            ProjectMembership.status == status,
            Project.status == ProjectStatus.ACTIVE,
        )
        .order_by(ProjectMembership.joined_at.desc(), ProjectMembership.membership_id.desc())
    )
    rows = (await db.execute(statement)).all()
    cards: list[MembershipCardDTO] = []
    for membership, project, plan, required_done, required_total, open_blockers in rows:
        plan_dto = None
        if plan is not None:
            plan_dto = MembershipPlanDTO(
                status=plan.status,
                revision=plan.revision,
                required_done=required_done or 0,
                required_total=required_total or 0,
                open_blockers=open_blockers or 0,
            )
        cards.append(
            MembershipCardDTO(
                membership_id=membership.membership_id,
                project_id=project.project_id,
                project_name=project.name,
                project_key=project.key,
                project_status=project.status,
                project_role=membership.project_role,
                joined_at=membership.joined_at,
                sync_status=project.sync_status,
                last_synced_at=project.last_synced_at,
                plan=plan_dto,
            )
        )
    return cards


async def establish_active_membership(
    db: AsyncSession,
    user_id: int,
    membership_id: int,
) -> ActiveMembershipResponseDTO:
    row = (
        await db.execute(
            select(ProjectMembership, Project)
            .join(Project, Project.project_id == ProjectMembership.project_id)
            .where(ProjectMembership.membership_id == membership_id)
        )
    ).one_or_none()
    if row is None:
        raise MembershipSelectionError(
            code="MEMBERSHIP_NOT_FOUND",
            message="This project membership could not be found.",
            status_code=404,
        )
    membership, project = row
    if membership.user_id != user_id:
        raise MembershipSelectionError(
            code="MEMBERSHIP_FORBIDDEN",
            message="You do not have access to this project membership.",
            status_code=403,
        )
    if membership.status != MembershipStatus.ACTIVE:
        raise MembershipSelectionError(
            code="MEMBERSHIP_INACTIVE",
            message=(
                "This project membership is no longer active. "
                "Choose another project or contact an administrator."
            ),
            status_code=409,
        )
    if project.status != ProjectStatus.ACTIVE:
        raise MembershipSelectionError(
            code="PROJECT_ARCHIVED",
            message="This project is no longer active.",
            status_code=409,
        )
    portal_path = "/product-manager" if membership.project_role == ProjectRole.PM else "/user"
    redirect_path = f"{portal_path}?project={project.project_id}"
    return ActiveMembershipResponseDTO(
        membership_id=membership.membership_id,
        project_id=project.project_id,
        project_name=project.name,
        project_key=project.key,
        project_role=membership.project_role,
        redirect_path=redirect_path,
    )


# ---------------------------------------------------------------------------
# CRUD membership cho PM/Admin
# ---------------------------------------------------------------------------


async def create_membership(
    db: AsyncSession, dto: ProjectMembershipCreateRequestDTO
) -> ProjectMembership:
    membership = ProjectMembership(
        user_id=dto.user_id,
        project_id=dto.project_id,
        project_role=dto.project_role,
        assigned_by_admin_id=dto.assigned_by_admin_id,
    )
    db.add(membership)
    await db.commit()
    await db.refresh(membership)
    return membership


async def get_membership(db: AsyncSession, membership_id: int) -> ProjectMembership | None:
    return await db.get(ProjectMembership, membership_id)


async def list_memberships_by_project(
    db: AsyncSession, project_id: int, limit: int = 50, offset: int = 0
) -> list[ProjectMembership]:
    result = await db.execute(
        select(ProjectMembership)
        .where(ProjectMembership.project_id == project_id)
        .order_by(ProjectMembership.membership_id)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def list_memberships_by_project_with_user(
    db: AsyncSession, project_id: int, limit: int = 50, offset: int = 0
) -> list[tuple[ProjectMembership, User]]:
    """Join sẵn User — dùng cho màn hình danh sách thành viên (cần email/tên)."""
    result = await db.execute(
        select(ProjectMembership, User)
        .join(User, User.user_id == ProjectMembership.user_id)
        .where(ProjectMembership.project_id == project_id)
        .order_by(ProjectMembership.membership_id)
        .limit(limit)
        .offset(offset)
    )
    return [(m, u) for m, u in result.all()]


async def list_memberships_by_user(db: AsyncSession, user_id: int) -> list[ProjectMembership]:
    """Danh sách project mà 1 user (thường là PM) đang tham gia — dùng cho owner-projects."""
    result = await db.execute(
        select(ProjectMembership)
        .where(ProjectMembership.user_id == user_id)
        .order_by(ProjectMembership.project_id)
    )
    return list(result.scalars().all())


async def update_membership(
    db: AsyncSession, membership_id: int, dto: ProjectMembershipUpdateRequestDTO
) -> ProjectMembership | None:
    membership = await db.get(ProjectMembership, membership_id)
    if membership is None:
        return None
    if dto.project_role is not None:
        membership.project_role = dto.project_role
    if dto.status is not None:
        membership.status = dto.status
    await db.commit()
    await db.refresh(membership)
    return membership


async def deactivate_membership(db: AsyncSession, membership_id: int) -> ProjectMembership | None:
    """Xoá mềm: chuyển status = INACTIVE thay vì xoá row (không hard-delete)."""
    membership = await db.get(ProjectMembership, membership_id)
    if membership is None:
        return None
    membership.status = MembershipStatus.INACTIVE
    await db.commit()
    await db.refresh(membership)
    return membership
