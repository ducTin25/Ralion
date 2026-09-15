from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dto.response.blocker_attachment_response_dto import BlockerAttachmentResponseDTO
from src.dto.response.pm_blocker_response_dto import PmBlockerResponseDTO
from src.model.blocker import Blocker
from src.model.blocker_attachment import BlockerAttachment
from src.model.enums import BlockerStatus, ProjectRole
from src.model.onboarding_plan import OnboardingPlan
from src.model.plan_task import PlanTask
from src.model.project_membership import ProjectMembership
from src.model.user import User


class PmBlockerError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def attachment_response(attachment: BlockerAttachment) -> BlockerAttachmentResponseDTO:
    """Dùng chung cho cả PM (`blocker_service`) và Member (`member_onboarding_service`) — 1 dữ liệu,
    không có bản dựng riêng cho mỗi phía."""
    return BlockerAttachmentResponseDTO(
        attachment_id=attachment.attachment_id,
        file_name=attachment.file_name,
        mime_type=attachment.mime_type,
        url=attachment.storage_key,
        uploaded_at=attachment.uploaded_at,
    )


async def list_attachments(db: AsyncSession, blocker_id: int) -> list[BlockerAttachmentResponseDTO]:
    rows = list(
        (
            await db.scalars(
                select(BlockerAttachment)
                .where(BlockerAttachment.blocker_id == blocker_id)
                .order_by(BlockerAttachment.attachment_id)
            )
        ).all()
    )
    return [attachment_response(row) for row in rows]


def _response(
    blocker: Blocker,
    task: PlanTask,
    engineer_membership: ProjectMembership,
    engineer: User,
    attachments: list[BlockerAttachmentResponseDTO],
) -> PmBlockerResponseDTO:
    return PmBlockerResponseDTO(
        blocker_id=blocker.blocker_id,
        project_id=engineer_membership.project_id,
        membership_id=engineer_membership.membership_id,
        plan_task_id=task.plan_task_id,
        engineer_name=engineer.display_name,
        engineer_email=engineer.email,
        task_title=task.title,
        category=blocker.category,
        reason=blocker.reason,
        status=blocker.status,
        reported_at=blocker.reported_at,
        resolved_at=blocker.resolved_at,
        attachments=attachments,
    )


def _blocker_query(project_id: int, blocker_id: int | None = None):
    query = (
        select(Blocker, PlanTask, ProjectMembership, User)
        .join(PlanTask, PlanTask.plan_task_id == Blocker.plan_task_id)
        .join(OnboardingPlan, OnboardingPlan.plan_id == PlanTask.plan_id)
        .join(ProjectMembership, ProjectMembership.membership_id == OnboardingPlan.membership_id)
        .join(User, User.user_id == ProjectMembership.user_id)
        .where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.project_role == ProjectRole.ENGINEER,
        )
    )
    if blocker_id is not None:
        query = query.where(Blocker.blocker_id == blocker_id)
    return query


async def attachments_by_blocker(
    db: AsyncSession, blocker_ids: list[int]
) -> dict[int, list[BlockerAttachmentResponseDTO]]:
    if not blocker_ids:
        return {}
    rows = list(
        (
            await db.scalars(
                select(BlockerAttachment)
                .where(BlockerAttachment.blocker_id.in_(blocker_ids))
                .order_by(BlockerAttachment.blocker_id, BlockerAttachment.attachment_id)
            )
        ).all()
    )
    grouped: dict[int, list[BlockerAttachmentResponseDTO]] = {}
    for row in rows:
        grouped.setdefault(row.blocker_id, []).append(attachment_response(row))
    return grouped


async def list_for_membership(db: AsyncSession, project_id: int, membership_id: int) -> list[PmBlockerResponseDTO]:
    """Blocker của ĐÚNG 1 Engineer — dùng cho màn "Xem tiến độ" (PM xem 1 thành viên cụ thể),
    tái dùng chung `_blocker_query`/`_response` với `list_for_pm` để 2 màn hình luôn nhất quán dữ
    liệu, chỉ khác phạm vi lọc."""
    rows = (
        await db.execute(
            _blocker_query(project_id)
            .where(ProjectMembership.membership_id == membership_id)
            .order_by(Blocker.reported_at.asc(), Blocker.blocker_id.asc())
        )
    ).all()
    attachments = await attachments_by_blocker(db, [blocker.blocker_id for blocker, *_ in rows])
    return [
        _response(blocker, task, membership, engineer, attachments.get(blocker.blocker_id, []))
        for blocker, task, membership, engineer in rows
    ]


async def list_for_pm(db: AsyncSession, project_id: int) -> list[PmBlockerResponseDTO]:
    """Sắp xếp CŨ NHẤT trước — PM xử lý theo thứ tự "tới trước xử lý trước" (FIFO), không để
    blocker mới nhất che khuất blocker đang chờ lâu nhất."""
    rows = (
        await db.execute(
            _blocker_query(project_id).order_by(Blocker.reported_at.asc(), Blocker.blocker_id.asc())
        )
    ).all()
    attachments = await attachments_by_blocker(db, [blocker.blocker_id for blocker, *_ in rows])
    return [
        _response(blocker, task, membership, engineer, attachments.get(blocker.blocker_id, []))
        for blocker, task, membership, engineer in rows
    ]


async def resolve_for_pm(
    db: AsyncSession, project_id: int, blocker_id: int
) -> PmBlockerResponseDTO:
    row = (
        await db.execute(_blocker_query(project_id, blocker_id))
    ).one_or_none()
    if row is None:
        raise PmBlockerError(404, "Không tìm thấy blocker trong project này.")

    blocker, task, membership, engineer = row
    if blocker.status != BlockerStatus.RESOLVED:
        blocker.status = BlockerStatus.RESOLVED
        blocker.resolved_at = datetime.now(UTC).replace(tzinfo=None)
        await db.commit()
        await db.refresh(blocker)
    attachments = await list_attachments(db, blocker.blocker_id)
    return _response(blocker, task, membership, engineer, attachments)
