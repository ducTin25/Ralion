from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import require_project_member
from src.dto.response.notification_response_dto import PmNotificationResponseDTO
from src.dto.response.pm_dashboard_response_dto import PmDashboardResponseDTO
from src.model.enums import ProjectRole
from src.model.project_membership import ProjectMembership
from src.model.session import get_db
from src.services import pm_dashboard_service

router = APIRouter(prefix="/pm/projects", tags=["pm-dashboard"])


@router.get("/{project_id}/dashboard", response_model=PmDashboardResponseDTO)
async def get_project_dashboard(
    project_id: int,
    _pm_membership: Annotated[
        ProjectMembership | None, Depends(require_project_member(ProjectRole.PM))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PmDashboardResponseDTO:
    try:
        return await pm_dashboard_service.get_dashboard(db, project_id)
    except pm_dashboard_service.PmDashboardError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get("/{project_id}/notifications", response_model=list[PmNotificationResponseDTO])
async def list_project_notifications(
    project_id: int,
    _pm_membership: Annotated[
        ProjectMembership | None, Depends(require_project_member(ProjectRole.PM))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[PmNotificationResponseDTO]:
    return await pm_dashboard_service.list_notifications(db, project_id)
