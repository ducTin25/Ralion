from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.model.enums import DEFERRED_TASK_CATEGORIES, TemplateScope, TemplateStatus, TemplateVersionStatus
from src.model.onboarding_template import OnboardingTemplate
from src.model.project import Project
from src.model.task_dependency import TaskDependency
from src.model.template_task import TemplateTask
from src.model.template_version import TemplateVersion


async def get_approved_global_template(db: AsyncSession) -> OnboardingTemplate | None:
    return await db.scalar(
        select(OnboardingTemplate).where(
            OnboardingTemplate.scope == TemplateScope.GLOBAL,
            OnboardingTemplate.status == TemplateStatus.APPROVED,
        )
    )


async def get_template(db: AsyncSession, template_id: int) -> OnboardingTemplate | None:
    return await db.get(OnboardingTemplate, template_id)


async def get_by_project(db: AsyncSession, project_id: int) -> OnboardingTemplate | None:
    return await db.scalar(select(OnboardingTemplate).where(OnboardingTemplate.project_id == project_id))


async def get_global_template(db: AsyncSession) -> OnboardingTemplate | None:
    """Mirror `get_by_project` cho scope GLOBAL -- không lọc status (khác
    `get_approved_global_template`) để trang Admin thấy được cả version DRAFT đang sửa dở, không
    chỉ bản đã APPROVED."""
    return await db.scalar(select(OnboardingTemplate).where(OnboardingTemplate.scope == TemplateScope.GLOBAL))


async def materialize_project_template(
    db: AsyncSession, project: Project, global_template: OnboardingTemplate
) -> OnboardingTemplate:
    """Fork Global Master Template thành 1 Project Template mới cho `project`: copy toàn bộ
    TemplateTask từ version APPROVED của GLOBAL sang version 1 (DRAFT) của project (SoT §11.16,
    §17.2). Chỉ add+flush, KHÔNG commit — gọi trong cùng transaction với nơi tạo project."""
    project_template = OnboardingTemplate(
        project_id=project.project_id,
        source_template_id=global_template.template_id,
        scope=TemplateScope.PROJECT,
        name=f"Master Template — {project.key}",
        description=f"Fork từ Global Master Template cho project {project.name}.",
        status=TemplateStatus.DRAFT,
    )
    db.add(project_template)
    await db.flush()

    global_version = await db.scalar(
        select(TemplateVersion).where(
            TemplateVersion.template_id == global_template.template_id,
            TemplateVersion.status == TemplateVersionStatus.APPROVED,
        )
    )
    project_version = TemplateVersion(
        template_id=project_template.template_id,
        version_no=1,
        status=TemplateVersionStatus.DRAFT,
    )
    db.add(project_version)
    await db.flush()

    if global_version is not None:
        source_tasks_result = await db.execute(
            select(TemplateTask)
            .where(
                TemplateTask.version_id == global_version.version_id,
                TemplateTask.category.not_in(DEFERRED_TASK_CATEGORIES),
            )
            .order_by(TemplateTask.display_order)
        )
        source_tasks = list(source_tasks_result.scalars().all())

        id_map: dict[int, int] = {}
        for task in source_tasks:
            new_task = TemplateTask(
                version_id=project_version.version_id,
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
            source_deps_result = await db.execute(
                select(TaskDependency).where(TaskDependency.predecessor_task_id.in_(id_map.keys()))
            )
            for dep in source_deps_result.scalars().all():
                if dep.successor_task_id in id_map:
                    db.add(
                        TaskDependency(
                            predecessor_task_id=id_map[dep.predecessor_task_id],
                            successor_task_id=id_map[dep.successor_task_id],
                        )
                    )
            await db.flush()

    return project_template


async def create_template_for_project(db: AsyncSession, project_id: int) -> OnboardingTemplate:
    """Backfill/test only — xem OnboardingTemplateCreateRequestDTO. PM UI không gọi trực tiếp."""
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    existing = await get_by_project(db, project_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Project đã có Master Template")

    global_template = await get_approved_global_template(db)
    if global_template is None:
        raise HTTPException(
            status_code=422,
            detail="Chưa có Global Master Template đã duyệt — không thể tạo template cho project.",
        )

    project_template = await materialize_project_template(db, project, global_template)
    await db.commit()
    await db.refresh(project_template)
    return project_template
