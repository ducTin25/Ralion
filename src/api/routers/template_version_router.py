from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import (
    authorize_template_scope_for_template,
    require_password_changed,
    require_template_version_write_access,
)
from src.dto.request.template_version_request_dto import TemplateVersionCreateRequestDTO
from src.dto.response.template_version_response_dto import TemplateVersionResponseDTO
from src.model.session import get_db
from src.model.user import User
from src.services import template_version_service

router = APIRouter(prefix="/template-versions", tags=["pm-template-versions"])


@router.post("/pm", response_model=TemplateVersionResponseDTO, status_code=201)
async def create_version(
    dto: TemplateVersionCreateRequestDTO,
    current_user: Annotated[User, Depends(require_password_changed)],
    db: AsyncSession = Depends(get_db),
) -> TemplateVersionResponseDTO:
    await authorize_template_scope_for_template(db, current_user, dto.template_id)
    version = await template_version_service.create_version(db, dto.template_id, dto.clone_from_version_id)
    return TemplateVersionResponseDTO.from_entity(version)


@router.get(
    "/pm/by-template/{template_id}",
    response_model=list[TemplateVersionResponseDTO],
)
async def list_versions(
    template_id: int,
    current_user: Annotated[User, Depends(require_password_changed)],
    db: AsyncSession = Depends(get_db),
) -> list[TemplateVersionResponseDTO]:
    await authorize_template_scope_for_template(db, current_user, template_id)
    versions = await template_version_service.list_versions_by_template(db, template_id)
    return [TemplateVersionResponseDTO.from_entity(v) for v in versions]


@router.get(
    "/pm/{version_id}",
    response_model=TemplateVersionResponseDTO,
    dependencies=[Depends(require_template_version_write_access())],
)
async def get_version(version_id: int, db: AsyncSession = Depends(get_db)) -> TemplateVersionResponseDTO:
    version = await template_version_service.get_version(db, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return TemplateVersionResponseDTO.from_entity(version)


@router.patch(
    "/pm/{version_id}/approve",
    response_model=TemplateVersionResponseDTO,
    dependencies=[Depends(require_template_version_write_access())],
)
async def approve_version(version_id: int, db: AsyncSession = Depends(get_db)) -> TemplateVersionResponseDTO:
    version = await template_version_service.approve_version(db, version_id)
    return TemplateVersionResponseDTO.from_entity(version)
