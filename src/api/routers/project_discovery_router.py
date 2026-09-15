"""F6 Scheduled Incremental Convention Discovery — project-scoped PM API.

No raw cron, no pipeline-internal field (model, concurrency, embedding batch size, cosine
threshold, retry policy) is ever accepted or returned here — the DTOs simply have no such
field. `run-now` and the scheduler tick both call the exact same
`convention_discovery.run_discovery()` service (src/infrastructure/scheduling/
convention_discovery_scheduler.py), not a duplicated code path.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user, require_project_member
from src.dto.request.discovery_schedule_request_dto import DiscoveryScheduleUpdateRequestDTO
from src.dto.response.discovery_schedule_response_dto import DiscoveryScheduleResponseDTO
from src.infrastructure.scheduling.convention_discovery_scheduler import compute_next_run_at
from src.model.enums import IngestionJobTriggerType, IngestionJobType, ProjectRole
from src.model.ingestion_job import IngestionJob
from src.model.project import Project
from src.model.project_membership import ProjectMembership
from src.model.session import get_db
from src.model.user import User
from src.modules.knowledge.mining.convention_discovery import (
    AlreadyRunningError,
    start_discovery_run_in_background,
)

router = APIRouter(prefix="/pm/projects/{project_id}/discovery-schedule", tags=["f6-discovery"])


async def _get_project_or_404(db: AsyncSession, project_id: int) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _last_run(db: AsyncSession, project_id: int) -> IngestionJob | None:
    return await db.scalar(
        select(IngestionJob)
        .where(
            IngestionJob.project_id == project_id,
            IngestionJob.job_type == IngestionJobType.RULE_MINING,
        )
        .order_by(IngestionJob.created_at.desc())
        .limit(1)
    )


@router.get("", response_model=DiscoveryScheduleResponseDTO)
async def get_discovery_schedule(
    project_id: int,
    _membership: Annotated[ProjectMembership | None, Depends(require_project_member(ProjectRole.PM))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DiscoveryScheduleResponseDTO:
    project = await _get_project_or_404(db, project_id)
    last_run = await _last_run(db, project_id)
    return DiscoveryScheduleResponseDTO.from_entity(project, last_run)


@router.put("", response_model=DiscoveryScheduleResponseDTO)
async def update_discovery_schedule(
    project_id: int,
    dto: DiscoveryScheduleUpdateRequestDTO,
    _membership: Annotated[ProjectMembership | None, Depends(require_project_member(ProjectRole.PM))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DiscoveryScheduleResponseDTO:
    project = await _get_project_or_404(db, project_id)
    if dto.discovery_mode.value != "MANUAL_ONLY" and not project.github_repo:
        raise HTTPException(
            status_code=422, detail="Project has no configured GitHub repository to discover from"
        )

    project.discovery_mode = dto.discovery_mode
    project.discovery_interval_hours = dto.discovery_interval_hours
    project.discovery_time_of_day = dto.discovery_time_of_day
    project.discovery_day_of_week = dto.discovery_day_of_week
    project.discovery_timezone = dto.discovery_timezone
    project.discovery_next_run_at = compute_next_run_at(
        project, after=datetime.now(UTC).replace(tzinfo=None)
    )

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=422, detail="Invalid discovery schedule for this project") from exc

    last_run = await _last_run(db, project_id)
    return DiscoveryScheduleResponseDTO.from_entity(project, last_run)


@router.post("/run-now", response_model=DiscoveryScheduleResponseDTO, status_code=202)
async def run_discovery_now(
    project_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    _membership: Annotated[ProjectMembership | None, Depends(require_project_member(ProjectRole.PM))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DiscoveryScheduleResponseDTO:
    """Reserves the run synchronously (so an overlapping trigger still gets an immediate 409),
    then runs the actual ingest+mining in the background — a real repo's PR history can take
    minutes, and this used to block the whole request for it (CHANGE_LOG.md). The PM polls
    `GET .../discovery-schedule` for the job reaching a terminal status, same pattern
    `GithubSyncCard` already uses for `POST .../github-sync`."""
    project = await _get_project_or_404(db, project_id)
    try:
        job = await start_discovery_run_in_background(
            db,
            project_id,
            trigger_type=IngestionJobTriggerType.MANUAL,
            triggered_by_user_id=current_user.user_id,
        )
    except AlreadyRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return DiscoveryScheduleResponseDTO.from_entity(project, job)
