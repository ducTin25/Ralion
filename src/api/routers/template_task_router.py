from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import (
    authorize_template_scope_for_version,
    require_password_changed,
    require_template_task_write_access,
    require_template_version_write_access,
)
from src.dto.request.template_task_request_dto import (
    TemplateTaskCreateRequestDTO,
    TemplateTaskReorderRequestDTO,
    TemplateTaskUpdateRequestDTO,
)
from src.dto.response.template_task_response_dto import TemplateTaskResponseDTO
from src.model.session import get_db
from src.model.user import User
from src.services import template_task_service

router = APIRouter(prefix="/template-tasks", tags=["pm-template-tasks"])


@router.post("/pm", response_model=TemplateTaskResponseDTO, status_code=201)
async def create_task(
    dto: TemplateTaskCreateRequestDTO,
    current_user: Annotated[User, Depends(require_password_changed)],
    db: AsyncSession = Depends(get_db),
) -> TemplateTaskResponseDTO:
    await authorize_template_scope_for_version(db, current_user, dto.version_id)
    task = await template_task_service.create_task(db, dto)
    return TemplateTaskResponseDTO.from_entity(task)


@router.get(
    "/pm/by-version/{version_id}",
    response_model=list[TemplateTaskResponseDTO],
    dependencies=[Depends(require_template_version_write_access())],
)
async def list_tasks(version_id: int, db: AsyncSession = Depends(get_db)) -> list[TemplateTaskResponseDTO]:
    tasks = await template_task_service.list_by_version(db, version_id)
    return [TemplateTaskResponseDTO.from_entity(t) for t in tasks]


@router.patch("/pm/reorder", response_model=list[TemplateTaskResponseDTO])
async def reorder_tasks(
    dto: TemplateTaskReorderRequestDTO,
    current_user: Annotated[User, Depends(require_password_changed)],
    db: AsyncSession = Depends(get_db),
) -> list[TemplateTaskResponseDTO]:
    await authorize_template_scope_for_version(db, current_user, dto.version_id)
    tasks = await template_task_service.reorder_tasks(db, dto)
    return [TemplateTaskResponseDTO.from_entity(t) for t in tasks]


@router.patch(
    "/pm/{template_task_id}",
    response_model=TemplateTaskResponseDTO,
    dependencies=[Depends(require_template_task_write_access())],
)
async def update_task(
    template_task_id: int, dto: TemplateTaskUpdateRequestDTO, db: AsyncSession = Depends(get_db)
) -> TemplateTaskResponseDTO:
    task = await template_task_service.update_task(db, template_task_id, dto)
    return TemplateTaskResponseDTO.from_entity(task)


@router.delete(
    "/pm/{template_task_id}",
    status_code=204,
    dependencies=[Depends(require_template_task_write_access())],
)
async def delete_task(template_task_id: int, db: AsyncSession = Depends(get_db)) -> None:
    await template_task_service.delete_task(db, template_task_id)
