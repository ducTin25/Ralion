from fastapi import HTTPException
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dto.request.template_task_request_dto import (
    TemplateTaskCreateRequestDTO,
    TemplateTaskReorderRequestDTO,
    TemplateTaskUpdateRequestDTO,
)
from src.model.enums import TemplateVersionStatus
from src.model.task_dependency import TaskDependency
from src.model.template_task import TemplateTask
from src.model.template_version import TemplateVersion


async def _require_draft_version(db: AsyncSession, version_id: int) -> TemplateVersion:
    version = await db.get(TemplateVersion, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")
    if version.status != TemplateVersionStatus.DRAFT:
        raise HTTPException(status_code=409, detail="Chỉ sửa được task khi version đang ở trạng thái DRAFT")
    return version


async def get_task(db: AsyncSession, template_task_id: int) -> TemplateTask | None:
    return await db.get(TemplateTask, template_task_id)


async def list_by_version(db: AsyncSession, version_id: int) -> list[TemplateTask]:
    result = await db.execute(
        select(TemplateTask).where(TemplateTask.version_id == version_id).order_by(TemplateTask.display_order)
    )
    return list(result.scalars().all())


async def create_task(db: AsyncSession, dto: TemplateTaskCreateRequestDTO) -> TemplateTask:
    await _require_draft_version(db, dto.version_id)

    max_order = await db.scalar(
        select(func.max(TemplateTask.display_order)).where(TemplateTask.version_id == dto.version_id)
    )
    task = TemplateTask(
        version_id=dto.version_id,
        category=dto.category,
        title_pattern=dto.title_pattern,
        objective=dto.objective,
        instruction_template=dto.instruction_template,
        display_order=(max_order or 0) + 1,
        mandatory=dto.mandatory,
        estimated_minutes=dto.estimated_minutes,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def update_task(db: AsyncSession, template_task_id: int, dto: TemplateTaskUpdateRequestDTO) -> TemplateTask:
    task = await db.get(TemplateTask, template_task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    await _require_draft_version(db, task.version_id)

    if dto.category is not None:
        task.category = dto.category
    if dto.title_pattern is not None:
        task.title_pattern = dto.title_pattern
    if dto.objective is not None:
        task.objective = dto.objective
    if dto.instruction_template is not None:
        task.instruction_template = dto.instruction_template
    if dto.mandatory is not None:
        task.mandatory = dto.mandatory
    if dto.estimated_minutes is not None:
        task.estimated_minutes = dto.estimated_minutes

    await db.commit()
    await db.refresh(task)
    return task


async def delete_task(db: AsyncSession, template_task_id: int) -> None:
    task = await db.get(TemplateTask, template_task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    await _require_draft_version(db, task.version_id)

    # Xoá luôn mọi TaskDependency có tham chiếu tới task này (dù làm predecessor hay successor)
    # trước khi xoá task — nếu không sẽ vướng FK, đặc biệt phổ biến vì fork từ GLOBAL/clone
    # version đã copy sẵn dependency chuỗi tuần tự cho hầu hết task.
    await db.execute(
        delete(TaskDependency).where(
            or_(
                TaskDependency.predecessor_task_id == template_task_id,
                TaskDependency.successor_task_id == template_task_id,
            )
        )
    )
    await db.delete(task)
    await db.commit()


async def reorder_tasks(db: AsyncSession, dto: TemplateTaskReorderRequestDTO) -> list[TemplateTask]:
    await _require_draft_version(db, dto.version_id)

    tasks = await list_by_version(db, dto.version_id)
    existing_ids = {t.template_task_id for t in tasks}
    if set(dto.ordered_template_task_ids) != existing_ids:
        raise HTTPException(
            status_code=422, detail="Danh sách task_id không khớp đúng tập task hiện có của version"
        )

    tasks_by_id = {t.template_task_id: t for t in tasks}
    # Đẩy về giá trị âm tạm thời trước để tránh đụng unique constraint (version_id, display_order)
    # khi các task hoán đổi vị trí cho nhau.
    for task in tasks:
        task.display_order = -task.display_order
    await db.flush()

    for order, task_id in enumerate(dto.ordered_template_task_ids, start=1):
        tasks_by_id[task_id].display_order = order

    await db.commit()
    return await list_by_version(db, dto.version_id)
