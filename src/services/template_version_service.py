from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.model.enums import DEFERRED_TASK_CATEGORIES, TemplateStatus, TemplateVersionStatus
from src.model.onboarding_template import OnboardingTemplate
from src.model.task_dependency import TaskDependency
from src.model.template_task import TemplateTask
from src.model.template_version import TemplateVersion


async def get_version(db: AsyncSession, version_id: int) -> TemplateVersion | None:
    return await db.get(TemplateVersion, version_id)


async def list_versions_by_template(db: AsyncSession, template_id: int) -> list[TemplateVersion]:
    result = await db.execute(
        select(TemplateVersion)
        .where(TemplateVersion.template_id == template_id)
        .order_by(TemplateVersion.version_no.desc())
    )
    return list(result.scalars().all())


async def create_version(
    db: AsyncSession, template_id: int, clone_from_version_id: int | None
) -> TemplateVersion:
    template = await db.get(OnboardingTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    last_version_no = await db.scalar(
        select(func.max(TemplateVersion.version_no)).where(TemplateVersion.template_id == template_id)
    )
    new_version = TemplateVersion(
        template_id=template_id, version_no=(last_version_no or 0) + 1, status=TemplateVersionStatus.DRAFT
    )
    db.add(new_version)
    await db.flush()

    if clone_from_version_id is not None:
        source_version = await db.get(TemplateVersion, clone_from_version_id)
        if source_version is None or source_version.template_id != template_id:
            raise HTTPException(status_code=422, detail="Version nguồn không hợp lệ")

        source_tasks_result = await db.execute(
            select(TemplateTask)
            .where(
                TemplateTask.version_id == source_version.version_id,
                TemplateTask.category.not_in(DEFERRED_TASK_CATEGORIES),
            )
            .order_by(TemplateTask.display_order)
        )
        source_tasks = list(source_tasks_result.scalars().all())

        id_map: dict[int, int] = {}
        for task in source_tasks:
            new_task = TemplateTask(
                version_id=new_version.version_id,
                category=task.category,
                title_pattern=task.title_pattern,
                objective=task.objective,
                instruction_template=task.instruction_template,
                display_order=task.display_order,
                mandatory=task.mandatory,
                estimated_minutes=task.estimated_minutes,
            )
            db.add(new_task)
            await db.flush()
            id_map[task.template_task_id] = new_task.template_task_id

        if id_map:
            deps_result = await db.execute(
                select(TaskDependency).where(TaskDependency.predecessor_task_id.in_(id_map.keys()))
            )
            for dep in deps_result.scalars().all():
                if dep.successor_task_id in id_map:
                    db.add(
                        TaskDependency(
                            predecessor_task_id=id_map[dep.predecessor_task_id],
                            successor_task_id=id_map[dep.successor_task_id],
                        )
                    )

    await db.commit()
    await db.refresh(new_version)
    return new_version


def _has_cycle(graph: dict[int, list[int]]) -> bool:
    white, gray, black = 0, 1, 2
    color: dict[int, int] = {}

    def visit(node: int) -> bool:
        color[node] = gray
        for neighbor in graph.get(node, []):
            state = color.get(neighbor, white)
            if state == gray:
                return True
            if state == white and visit(neighbor):
                return True
        color[node] = black
        return False

    for node in list(graph.keys()):
        if color.get(node, white) == white and visit(node):
            return True
    return False


async def approve_version(db: AsyncSession, version_id: int) -> TemplateVersion:
    version = await db.get(TemplateVersion, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")
    if version.status not in (TemplateVersionStatus.DRAFT, TemplateVersionStatus.ARCHIVED):
        raise HTTPException(
            status_code=409, detail="Chỉ có thể duyệt version đang DRAFT hoặc ARCHIVED (duyệt lại)"
        )

    template = await db.get(OnboardingTemplate, version.template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    # Validate trước khi duyệt (SoT §17.2).
    tasks_result = await db.execute(select(TemplateTask).where(TemplateTask.version_id == version_id))
    tasks = list(tasks_result.scalars().all())
    if not tasks:
        raise HTTPException(status_code=422, detail="Version chưa có task nào, không thể duyệt")

    orders = [t.display_order for t in tasks]
    if len(set(orders)) != len(orders):
        raise HTTPException(status_code=422, detail="display_order bị trùng, không thể duyệt")

    task_ids = {t.template_task_id for t in tasks}
    deps_result = await db.execute(
        select(TaskDependency).where(TaskDependency.predecessor_task_id.in_(task_ids))
    )
    graph: dict[int, list[int]] = {}
    for dep in deps_result.scalars().all():
        if dep.successor_task_id not in task_ids:
            raise HTTPException(status_code=422, detail="Có dependency tham chiếu task ngoài version")
        graph.setdefault(dep.predecessor_task_id, []).append(dep.successor_task_id)
    if _has_cycle(graph):
        raise HTTPException(status_code=422, detail="Dependency graph có chu trình (cycle), không thể duyệt")

    # Khoá cạnh tranh: SELECT ... FOR UPDATE trên mọi version cùng template trước khi đổi status,
    # tránh 2 request duyệt gần như đồng thời cùng lọt qua các check ở trên.
    locked_result = await db.execute(
        select(TemplateVersion).where(TemplateVersion.template_id == version.template_id).with_for_update()
    )
    locked_versions = list(locked_result.scalars().all())
    version = next(v for v in locked_versions if v.version_id == version_id)
    if version.status not in (TemplateVersionStatus.DRAFT, TemplateVersionStatus.ARCHIVED):
        raise HTTPException(
            status_code=409, detail="Version vừa bị thay đổi trạng thái bởi request khác, thử lại"
        )

    currently_approved = next(
        (v for v in locked_versions if v.status == TemplateVersionStatus.APPROVED), None
    )
    if currently_approved is not None:
        currently_approved.status = TemplateVersionStatus.ARCHIVED
        # Flush ngay để UPDATE archive chắc chắn chạy trước UPDATE approve bên dưới — SQLAlchemy
        # flush theo thứ tự primary key chứ không theo thứ tự gán attribute, nên nếu version đang
        # duyệt (vd version cũ, PK nhỏ hơn) có PK nhỏ hơn version đang bị archive (PK lớn hơn),
        # UPDATE approve có thể chạy trước UPDATE archive và đụng unique constraint (2 version
        # cùng APPROVED trong khoảnh khắc giữa 2 câu UPDATE) — dù cả 2 assignment nằm cùng 1
        # transaction Python, Postgres vẫn check constraint theo từng statement, không deferred.
        await db.flush()

    version.status = TemplateVersionStatus.APPROVED
    version.approved_at = datetime.now(UTC).replace(tzinfo=None)
    template.status = TemplateStatus.APPROVED

    await db.commit()
    await db.refresh(version)
    return version
