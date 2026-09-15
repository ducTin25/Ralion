from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import require_admin, require_project_member, require_template_id_write_access
from src.dto.request.onboarding_template_request_dto import OnboardingTemplateCreateRequestDTO
from src.dto.response.onboarding_template_response_dto import OnboardingTemplateResponseDTO
from src.model.enums import ProjectRole
from src.model.project_membership import ProjectMembership
from src.model.session import get_db
from src.services import onboarding_template_service

# Prefix "/pm" trên từng path operation (xem giải thích trong project_router.py).
router = APIRouter(prefix="/onboarding-templates", tags=["pm-onboarding-templates"])


@router.post(
    "/pm",
    response_model=OnboardingTemplateResponseDTO,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
async def create_template(
    dto: OnboardingTemplateCreateRequestDTO, db: AsyncSession = Depends(get_db)
) -> OnboardingTemplateResponseDTO:
    """Không dùng từ UI PM — chỉ để backfill project cũ hoặc test qua Swagger (xem service)."""
    template = await onboarding_template_service.create_template_for_project(db, dto.project_id)
    return OnboardingTemplateResponseDTO.from_entity(template)


@router.get("/pm/by-project/{project_id}", response_model=OnboardingTemplateResponseDTO)
async def get_template_by_project(
    project_id: int,
    _membership: Annotated[
        ProjectMembership | None, Depends(require_project_member(ProjectRole.PM))
    ],
    db: AsyncSession = Depends(get_db),
) -> OnboardingTemplateResponseDTO:
    template = await onboarding_template_service.get_by_project(db, project_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Project chưa có Master Template")
    return OnboardingTemplateResponseDTO.from_entity(template)


@router.get(
    "/pm/{template_id}",
    response_model=OnboardingTemplateResponseDTO,
    dependencies=[Depends(require_template_id_write_access())],
)
async def get_template(template_id: int, db: AsyncSession = Depends(get_db)) -> OnboardingTemplateResponseDTO:
    template = await onboarding_template_service.get_template(db, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return OnboardingTemplateResponseDTO.from_entity(template)
