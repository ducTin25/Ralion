"""Service cho OnboardingPlan — đọc trạng thái (Phase 1) + sinh/duyệt Candidate Plan (Phase 4).

Ràng buộc DB phải nhớ khi sửa file này:
- INV7 (trigger `enforce_onboarding_plan_forward_status`): status chỉ đi tới
  DRAFT→APPROVED→ACTIVE→PROJECT_READY→ONBOARDING_CLOSED, không lùi được.
- `uq_onboarding_plans_one_open_per_membership`: mỗi membership chỉ có TỐI ĐA 1 plan chưa
  ONBOARDING_CLOSED → không thể tạo plan DRAFT thứ 2 song song với plan đang APPROVED.
Hai ràng buộc này quyết định cách "Regenerate" hoạt động — xem `regenerate_plan`.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.model.enums import PlanStatus, TaskStatus
from src.model.onboarding_plan import OnboardingPlan
from src.model.plan_task import PlanTask
from src.model.plan_task_citation import PlanTaskCitation
from src.model.plan_task_source import PlanTaskSource
from src.model.project_membership import ProjectMembership

logger = logging.getLogger(__name__)


async def get_plan_by_membership(db: AsyncSession, membership_id: int) -> OnboardingPlan | None:
    return await db.scalar(select(OnboardingPlan).where(OnboardingPlan.membership_id == membership_id))


async def list_plans_by_project(db: AsyncSession, project_id: int) -> list[OnboardingPlan]:
    """Toàn bộ Plan (mọi trạng thái) của các membership thuộc 1 project — dùng để FE tự map theo
    membership_id, tránh phải gọi API riêng cho từng dòng thành viên."""
    result = await db.execute(
        select(OnboardingPlan)
        .join(ProjectMembership, ProjectMembership.membership_id == OnboardingPlan.membership_id)
        .where(ProjectMembership.project_id == project_id)
    )
    return list(result.scalars().all())


async def get_plan(db: AsyncSession, plan_id: int) -> OnboardingPlan | None:
    return await db.get(OnboardingPlan, plan_id)


async def find_reference_plan(db: AsyncSession, project_id: int) -> OnboardingPlan | None:
    """Bản chuẩn của dự án — row có `project_id` và `membership_id IS NULL`.

    Đây là lộ trình mẫu PM soạn 1 lần cho cả dự án; mỗi kỹ sư được cấp plan sẽ nhận 1 bản sao
    (SoT §12 "kỹ sư cùng dự án nhận cấu trúc và nội dung giống nhau"). Index
    `uq_onboarding_plans_one_reference_per_project` bảo đảm tối đa 1 bản chuẩn/dự án nên `scalar()`
    không bao giờ vướng nhiều kết quả.
    """
    return await db.scalar(
        select(OnboardingPlan).where(
            OnboardingPlan.project_id == project_id,
            OnboardingPlan.membership_id.is_(None),
        )
    )


# Giữ tên cũ làm alias để chỗ gọi khác không phải sửa — cùng ý nghĩa, cùng tham số.
get_reference_plan_for_project = find_reference_plan


def is_reference_plan(plan: OnboardingPlan) -> bool:
    return plan.membership_id is None


async def assert_reference_plan_exists(db: AsyncSession, membership_id: int) -> OnboardingPlan:
    """Chặn sớm ở router: chưa có lộ trình chuẩn thì không cấp plan cho kỹ sư được.

    Kiểm tra tại đây (thay vì để pipeline phát hiện) để FE nhận 422 đồng bộ và hướng dẫn PM đi tạo
    lộ trình chuẩn trước, thay vì mở màn 6 bước rồi mới báo hỏng.
    """
    membership = await db.get(ProjectMembership, membership_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="Membership không tồn tại")

    reference = await find_reference_plan(db, membership.project_id)
    if reference is None:
        raise HTTPException(
            status_code=422,
            detail="Dự án chưa có lộ trình chuẩn — vào mục Onboarding Plan tạo lộ trình chuẩn "
            "trước, rồi mới cấp plan cho kỹ sư",
        )
    return reference


async def list_plan_tasks(db: AsyncSession, plan_id: int) -> list[PlanTask]:
    result = await db.execute(
        select(PlanTask).where(PlanTask.plan_id == plan_id).order_by(PlanTask.display_order)
    )
    return list(result.scalars().all())


async def list_plan_task_sources(db: AsyncSession, plan_id: int) -> list[PlanTaskSource]:
    result = await db.execute(
        select(PlanTaskSource)
        .join(PlanTask, PlanTask.plan_task_id == PlanTaskSource.plan_task_id)
        .where(PlanTask.plan_id == plan_id)
    )
    return list(result.scalars().all())


async def persist_generated_plan(
    db: AsyncSession,
    *,
    context,  # steps.GenerationContext — không import để tránh phụ thuộc vòng
    contents: dict,  # dict[int, content_llm.TaskContent]
    existing_plan_id: int | None = None,
    schedule_start_at: datetime | None = None,
) -> OnboardingPlan:
    """Ghi kết quả 6 bước xuống DB trong ĐÚNG 1 transaction.

    `existing_plan_id` != None nghĩa là đang Regenerate: tái dùng chính bản ghi plan cũ (xoá task cũ,
    ghi task mới, tăng revision) thay vì tạo bản mới — bắt buộc phải vậy vì unique index chỉ cho 1
    plan chưa đóng / membership.

    `schedule_start_at`: giờ bắt đầu PM chọn ở modal khi cấp plan cho kỹ sư — truyền thẳng vào
    `compute_due_dates()`. `None` thì hàm đó tự rơi về giờ gọi (hành vi cũ).
    """
    from src.services.plan_generation.steps import compute_due_dates

    is_reference = context.membership is None

    # Bản chuẩn luôn ghi đè tại chỗ (không tạo row thứ 2) — index
    # uq_onboarding_plans_one_reference_per_project chỉ cho 1 bản chuẩn/dự án.
    if is_reference and existing_plan_id is None:
        current = await find_reference_plan(db, context.project_id)
        existing_plan_id = current.plan_id if current else None

    if existing_plan_id is not None:
        plan = await db.get(OnboardingPlan, existing_plan_id)
        if plan is None:
            raise HTTPException(status_code=404, detail="Plan cần tạo lại không tồn tại")
        old_task_ids = list(
            (await db.scalars(select(PlanTask.plan_task_id).where(PlanTask.plan_id == plan.plan_id))).all()
        )
        if old_task_ids:
            # Thứ tự xoá bám theo chiều FK (không cột nào ON DELETE CASCADE):
            # citation -> source -> task. Đảo thứ tự là vi phạm khoá ngoại ngay.
            await db.execute(
                delete(PlanTaskCitation).where(PlanTaskCitation.plan_task_id.in_(old_task_ids))
            )
            await db.execute(delete(PlanTaskSource).where(PlanTaskSource.plan_task_id.in_(old_task_ids)))
            await db.execute(delete(PlanTask).where(PlanTask.plan_task_id.in_(old_task_ids)))
        plan.revision += 1
        plan.template_version_id = context.template_version.version_id
    else:
        plan = OnboardingPlan(
            # CHECK ck_onboarding_plans_owner ép đúng 1 trong 2 cột có giá trị.
            project_id=context.project_id if is_reference else None,
            membership_id=None if is_reference else context.membership.membership_id,
            template_version_id=context.template_version.version_id,
            revision=1,
            status=PlanStatus.DRAFT,  # SoT UC-06: "Kết quả luôn là DRAFT"
        )
        db.add(plan)
    await db.flush()

    due_dates = compute_due_dates(context, start=schedule_start_at)
    for task_input in context.task_inputs:
        template_task = task_input.template_task
        content = contents.get(template_task.template_task_id)
        if content is None:
            continue

        plan_task = PlanTask(
            plan_id=plan.plan_id,
            template_task_id=template_task.template_task_id,
            title=content.title,
            instruction=content.instruction,
            display_order=template_task.display_order,
            mandatory=template_task.mandatory,
            due_at=due_dates.get(template_task.template_task_id),
            status=TaskStatus.NOT_STARTED,
        )
        db.add(plan_task)
        await db.flush()

        # Tầng 1 — mức TÀI LIỆU. Giữ nguyên hợp đồng cũ (1 dòng = 1 tài liệu cần đọc) vì Member
        # Portal đọc thẳng bảng này; đổi ngữ nghĩa ở đây sẽ làm bên đó hiện trùng lặp file.
        source_id_by_version: dict[int, int] = {}
        for source in content.sources:
            plan_task_source = PlanTaskSource(
                plan_task_id=plan_task.plan_task_id,
                version_id=source.version_id,
                chunk_id=source.chunk_id,
                citation_note=source.citation_note,
            )
            db.add(plan_task_source)
            await db.flush()
            source_id_by_version[source.version_id] = plan_task_source.task_source_id

        # Tầng 2 — mức ĐOẠN. Mỗi `[n]` trong nội dung là 1 dòng, trỏ đúng chunk để bấm vào mở đúng
        # chỗ. Trích dẫn nào không tìm được tài liệu cha thì bỏ (không tạo bản ghi mồ côi) — chỉ xảy
        # ra nếu 2 tầng lệch nhau, nên log lại để thấy được thay vì hỏng âm thầm.
        for citation in content.citations:
            task_source_id = source_id_by_version.get(citation.version_id)
            if task_source_id is None:
                logger.warning(
                    "plan_generation: bỏ trích dẫn %s của task %s — không có nguồn tài liệu tương ứng",
                    citation.citation_order,
                    plan_task.plan_task_id,
                )
                continue
            db.add(
                PlanTaskCitation(
                    plan_task_id=plan_task.plan_task_id,
                    task_source_id=task_source_id,
                    chunk_id=citation.chunk_id,
                    citation_order=citation.citation_order,
                    citation_note=citation.citation_note,
                )
            )

    await db.commit()
    await db.refresh(plan)
    return plan


async def approve_plan(db: AsyncSession, plan_id: int, approved_by_user_id: int) -> OnboardingPlan:
    """DRAFT → APPROVED. Chỉ đi tới 1 nấc, không tự nhảy sang ACTIVE (đó là việc Phase 5 khi
    Engineer bắt đầu thực hiện)."""
    plan = await db.get(OnboardingPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan không tồn tại")
    if is_reference_plan(plan):
        # Bản chuẩn là nội dung mẫu của dự án, không phát hành cho ai nên không có khái niệm duyệt.
        # Nếu cho duyệt thì nó thành APPROVED và PM mất luôn quyền sửa (update_task chặn khác DRAFT).
        raise HTTPException(
            status_code=409,
            detail="Đây là lộ trình chuẩn của dự án, không có bước duyệt — "
            "duyệt là việc của từng plan đã cấp cho kỹ sư",
        )
    if plan.status != PlanStatus.DRAFT:
        raise HTTPException(
            status_code=409,
            detail=f"Chỉ duyệt được plan đang ở trạng thái Nháp (hiện tại: {plan.status.value})",
        )

    plan.status = PlanStatus.APPROVED
    plan.approved_by_user_id = approved_by_user_id
    plan.approved_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
    await db.refresh(plan)
    return plan


async def assert_plan_regeneratable(db: AsyncSession, plan_id: int) -> OnboardingPlan:
    """Chỉ cho tạo lại khi plan còn DRAFT.

    Vì sao KHÔNG cho tạo lại sau khi APPROVED (khác với ghi chú cũ ở docs/PM/plan-pm.md dòng 105):
    - Không thể set status lùi về DRAFT — trigger INV7 chặn.
    - Cũng không thể tạo 1 OnboardingPlan DRAFT mới thay thế — unique index
      `uq_onboarding_plans_one_open_per_membership` chỉ cho 1 plan chưa đóng / membership, nên bản
      mới sẽ đụng bản APPROVED đang tồn tại.
    → Sau khi duyệt, muốn đổi nội dung thì PM sửa tay từng task (đúng SoT rule 11: PlanTask là
      snapshot thực thi, không sinh lại ngầm dưới chân Engineer đang làm dở).
    """
    plan = await db.get(OnboardingPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan không tồn tại")
    if plan.status != PlanStatus.DRAFT:
        raise HTTPException(
            status_code=409,
            detail=f"Plan đã duyệt ({plan.status.value}) thì không tạo lại được — hãy sửa từng task",
        )
    return plan


async def assert_no_open_plan(db: AsyncSession, membership_id: int) -> None:
    """Chặn sớm ở tầng service thay vì để DB ném IntegrityError khó hiểu ra ngoài."""
    existing = await db.scalar(
        select(OnboardingPlan).where(
            OnboardingPlan.membership_id == membership_id,
            OnboardingPlan.status != PlanStatus.ONBOARDING_CLOSED,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Thành viên này đã có Onboarding Plan (#{existing.plan_id}, "
            f"{existing.status.value}) — mỗi thành viên chỉ có 1 plan đang mở",
        )
