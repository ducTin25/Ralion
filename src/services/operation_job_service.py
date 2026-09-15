"""Small persistent lifecycle for project-scoped background operations."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.ext.asyncio import AsyncSession

from src.model.enums import IngestionJobStatus, IngestionJobTriggerType, IngestionJobType
from src.model.ingestion_job import IngestionJob


class AlreadyRunningError(Exception):
    """The same operation is already running for this project."""

    def __init__(self, project_id: int, job_type: IngestionJobType) -> None:
        self.project_id = project_id
        self.job_type = job_type
        super().__init__(f"{job_type.value} is already in progress for project {project_id}")


def safe_error_summary(exc: Exception) -> str:
    if isinstance(exc, StatementError):
        detail = str(exc.orig) if exc.orig is not None else exc.__class__.__name__
    else:
        detail = str(exc)
    return f"{type(exc).__name__}: {detail}"[:2000]


async def reserve(
    session: AsyncSession,
    project_id: int,
    *,
    job_type: IngestionJobType,
    trigger_type: IngestionJobTriggerType,
    triggered_by_user_id: int | None,
) -> IngestionJob:
    """Atomically reserve ``project + operation`` through the partial unique index."""
    job = IngestionJob(
        project_id=project_id,
        job_type=job_type,
        trigger_type=trigger_type,
        status=IngestionJobStatus.RUNNING,
        started_at=datetime.now(UTC).replace(tzinfo=None),
        triggered_by_user_id=triggered_by_user_id,
    )
    session.add(job)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AlreadyRunningError(project_id, job_type) from exc
    return job


async def succeed(session: AsyncSession, job: IngestionJob) -> None:
    job.status = IngestionJobStatus.SUCCEEDED
    job.finished_at = datetime.now(UTC).replace(tzinfo=None)
    await session.commit()


async def fail(session: AsyncSession, job: IngestionJob, exc: Exception) -> None:
    await session.rollback()
    job.status = IngestionJobStatus.FAILED
    job.finished_at = datetime.now(UTC).replace(tzinfo=None)
    job.error_summary = safe_error_summary(exc)
    session.add(job)
    await session.commit()
