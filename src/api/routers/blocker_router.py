from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import require_project_member
from src.dto.response.pm_blocker_response_dto import PmBlockerResponseDTO
from src.model.enums import ProjectRole
from src.model.project_membership import ProjectMembership
from src.model.session import get_db
from src.services import blocker_service

router = APIRouter(prefix="/pm/projects", tags=["pm-blockers"])


@router.get(
    "/{project_id}/blockers",
    response_model=list[PmBlockerResponseDTO],
)
async def list_project_blockers(
    project_id: int,
    _pm_membership: Annotated[
        ProjectMembership | None, Depends(require_project_member(ProjectRole.PM))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[PmBlockerResponseDTO]:
    return await blocker_service.list_for_pm(db, project_id)


@router.patch(
    "/{project_id}/blockers/{blocker_id}/resolve",
    response_model=PmBlockerResponseDTO,
)
async def resolve_project_blocker(
    project_id: int,
    blocker_id: int,
    _pm_membership: Annotated[
        ProjectMembership | None, Depends(require_project_member(ProjectRole.PM))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PmBlockerResponseDTO:
    try:
        return await blocker_service.resolve_for_pm(db, project_id, blocker_id)
    except blocker_service.PmBlockerError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
