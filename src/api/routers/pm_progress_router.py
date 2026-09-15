from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import require_project_member
from src.dto.response.pm_member_progress_response_dto import PmMemberProgressResponseDTO
from src.model.enums import ProjectRole
from src.model.project_membership import ProjectMembership
from src.model.session import get_db
from src.services import pm_progress_service

router = APIRouter(prefix="/pm/projects", tags=["pm-progress"])


@router.get(
    "/{project_id}/members/{membership_id}/progress",
    response_model=PmMemberProgressResponseDTO,
)
async def get_member_progress(
    project_id: int,
    membership_id: int,
    _pm_membership: Annotated[
        ProjectMembership | None, Depends(require_project_member(ProjectRole.PM))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PmMemberProgressResponseDTO:
    try:
        return await pm_progress_service.get_member_progress(db, project_id, membership_id)
    except pm_progress_service.PmProgressError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
