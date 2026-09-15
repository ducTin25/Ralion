"""F6 Scheduled Incremental Convention Discovery — in-process scheduler.

An `asyncio.create_task` loop started in `src/main.py`'s `lifespan()`, not a new infrastructure
service (no Kafka/Redis/Celery). Safe only because this deployment is single-process uvicorn
(no `--workers`, confirmed in `docker-compose.yml`/`Dockerfile`) — a second process would
double-trigger a project's run; the DB-level overlap lock
(`uq_ingestion_jobs_one_running_per_project`) would still stop a genuine double-run, but a
second process was never a target deployment shape here.

Every tick finds due projects and calls the exact same `run_discovery()` application service
"Run now" calls — this file adds scheduling only, no mining/ingestion logic of its own.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from src.config import Settings
from src.model.enums import DiscoveryMode, IngestionJobTriggerType
from src.model.project import Project
from src.model.session import AsyncSessionLocal
from src.modules.knowledge.mining.convention_discovery import AlreadyRunningError, start_discovery_run_in_background

logger = logging.getLogger(__name__)


def compute_next_run_at(project: Project, *, after: datetime) -> datetime | None:
    """Deterministic, timezone-aware next fire time strictly after `after` (naive UTC in,
    naive UTC out — matching this codebase's persist convention). Uses stdlib `zoneinfo`, so
    DST transitions are handled by real IANA rules, not manual offset math.
    """
    if project.discovery_mode == DiscoveryMode.MANUAL_ONLY:
        return None
    if project.discovery_mode == DiscoveryMode.EVERY_N_HOURS:
        assert project.discovery_interval_hours is not None
        return after + timedelta(hours=project.discovery_interval_hours)

    assert project.discovery_timezone is not None
    assert project.discovery_time_of_day is not None
    tz = ZoneInfo(project.discovery_timezone)
    after_local = after.replace(tzinfo=UTC).astimezone(tz)
    time_of_day = project.discovery_time_of_day

    if project.discovery_mode == DiscoveryMode.DAILY_AT:
        candidate = datetime.combine(after_local.date(), time_of_day, tzinfo=tz)
        if candidate <= after_local:
            candidate = datetime.combine(after_local.date() + timedelta(days=1), time_of_day, tzinfo=tz)
        return candidate.astimezone(UTC).replace(tzinfo=None)

    # WEEKLY_AT — discovery_day_of_week: 0=Monday..6=Sunday, matching date.weekday().
    assert project.discovery_day_of_week is not None
    days_ahead = (project.discovery_day_of_week - after_local.weekday()) % 7
    candidate = datetime.combine(
        after_local.date() + timedelta(days=days_ahead), time_of_day, tzinfo=tz
    )
    if candidate <= after_local:
        candidate = datetime.combine(
            after_local.date() + timedelta(days=days_ahead + 7), time_of_day, tzinfo=tz
        )
    return candidate.astimezone(UTC).replace(tzinfo=None)


async def _run_due_projects(settings: Settings, _embedder: object | None = None) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    async with AsyncSessionLocal() as session:
        due_project_ids = (
            await session.scalars(
                select(Project.project_id).where(
                    Project.discovery_mode != DiscoveryMode.MANUAL_ONLY,
                    Project.discovery_next_run_at.is_not(None),
                    Project.discovery_next_run_at <= now,
                )
            )
        ).all()

    for project_id in due_project_ids:
        try:
            async with AsyncSessionLocal() as session:
                try:
                    await start_discovery_run_in_background(
                        session,
                        project_id,
                        trigger_type=IngestionJobTriggerType.SCHEDULED,
                        triggered_by_user_id=None,
                    )
                except AlreadyRunningError:
                    # Another trigger (Run now, or a slow previous tick) already holds this
                    # project's run — lost the race, not an error.
                    logger.info("convention_discovery_skip_already_running project_id=%s", project_id)

                project = await session.get(Project, project_id)
                if project is not None and project.discovery_mode != DiscoveryMode.MANUAL_ONLY:
                    # Recomputed from now() (not the stale next_run_at) so a period of
                    # downtime skips missed executions instead of catching up in a burst.
                    project.discovery_next_run_at = compute_next_run_at(
                        project, after=datetime.now(UTC).replace(tzinfo=None)
                    )
                    await session.commit()
        except Exception:  # noqa: BLE001 - one project's failure must never stop the loop
            logger.error(
                "convention_discovery_scheduler_tick_failed project_id=%s", project_id, exc_info=True
            )


async def convention_discovery_scheduler_loop(settings: Settings, _embedder: object | None = None) -> None:
    """Runs until cancelled (src/main.py cancels this task on shutdown)."""
    while True:
        try:
            await _run_due_projects(settings)
        except Exception:  # noqa: BLE001 - the loop itself must never die
            logger.error("convention_discovery_scheduler_loop_failed", exc_info=True)
        await asyncio.sleep(settings.convention_discovery_poll_seconds)
