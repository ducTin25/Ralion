"""F6 Scheduled Incremental Convention Discovery — the one application service both the
scheduler tick and the "Run now" API endpoint call (`run_discovery`, one function, two callers,
so "scheduled and manual execution must go through the same service" holds by construction, not
by convention).

Product decision (spec was silent, resolved in the approved plan — CLAUDE.md §10): APPROVED/
REJECTED RuleFamily rows are frozen from automatic reinforcement. `mine_new_evidence()`'s
clustering pool only ever includes PENDING families' anchors — a PENDING family is still
"awaiting review" by definition; an APPROVED/REJECTED one is a decided, live artifact that must
not be silently mutated by new evidence arriving later. If new evidence would have matched an
already-approved convention's content, it simply finds no PENDING representative to merge with
and surfaces as its own new PENDING family (or stays an orphan candidate) for a PM to notice —
never rewrites the approved snapshot.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from langchain_openai import ChatOpenAI
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.providers.embeddings import Embedder
from src.ai.retrieval_engine.chunking_config import rule_mining_params
from src.model.enums import IngestionJobStatus, IngestionJobTriggerType, IngestionJobType
from src.model.ingestion_job import IngestionJob
from src.model.project import Project
from src.model.session import AsyncSessionLocal
from src.modules.knowledge.ingestion.github_client import GithubClient
from src.modules.knowledge.ingestion.pr_corpus_ingestion import ingest_pr_corpus
from src.modules.knowledge.mining.rule_mining_worker import mine_new_evidence

logger = logging.getLogger(__name__)

_DEFAULT_OVERLAP_BUFFER_DAYS = 3
_DEFAULT_COLD_START_LOOKBACK_DAYS = 365


class AlreadyRunningError(Exception):
    """A discovery run is already RUNNING for this project — mapped to 409 at the router.

    Raised from the partial-unique-index violation on `ingestion_jobs`
    (`uq_ingestion_jobs_one_running_per_project`) — that index IS the overlap-prevention
    mechanism (CLAUDE.md's "idempotency at the DB boundary"), there is no application-level
    lock to bypass or get out of sync with it.
    """

    def __init__(self, project_id: int) -> None:
        self.project_id = project_id
        super().__init__(f"A discovery run is already in progress for project {project_id}")


def _discovery_config() -> dict:
    config = rule_mining_params().get("discovery")
    return config if isinstance(config, dict) else {}


async def _reserve_run(
    session: AsyncSession,
    project_id: int,
    *,
    trigger_type: IngestionJobTriggerType,
    triggered_by_user_id: int | None,
) -> IngestionJob:
    """The overlap-prevention insert (`AlreadyRunningError`'s docstring) — always synchronous,
    in every caller, so a concurrent run is rejected immediately rather than after the slow
    ingest+mining work has already started."""
    job = IngestionJob(
        project_id=project_id,
        job_type=IngestionJobType.RULE_MINING,
        trigger_type=trigger_type,
        status=IngestionJobStatus.PENDING,
        triggered_by_user_id=triggered_by_user_id,
    )
    session.add(job)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AlreadyRunningError(project_id) from exc
    return job


def _safe_error_summary(exc: Exception) -> str:
    """Format an exception for `IngestionJob.error_summary` without leaking raw SQL text, bound
    parameters, or (for the evidence-collision bug this guards against) PR comment bodies.
    `StatementError.__str__` (IntegrityError's base) appends a `[SQL: ...]`/`[parameters: ...]`
    dump; `.orig` — the driver-level exception — does not."""
    if isinstance(exc, StatementError):
        detail = str(exc.orig) if exc.orig is not None else exc.__class__.__name__
    else:
        detail = str(exc)
    return f"{type(exc).__name__}: {detail}"[:2000]


def _discovery_since(
    *,
    watermark: datetime | None,
    repo_created_at: datetime | None,
    now: datetime,
    overlap_buffer: timedelta,
    cold_start_lookback: timedelta,
) -> datetime:
    """Select the incremental or first-run PR discovery boundary.

    A project can be created long after its GitHub repository.  On the initial
    run, bound the configured lookback by the repository's real creation time;
    later runs remain driven solely by the persisted watermark and overlap.
    """
    if watermark is not None:
        return watermark - overlap_buffer
    if repo_created_at is None:
        raise ValueError("Repository creation timestamp is required for initial discovery")
    return max(repo_created_at, now - cold_start_lookback)


async def _execute_run(
    session: AsyncSession,
    job: IngestionJob,
    project_id: int,
    *,
    github_client: GithubClient,
    llm: ChatOpenAI,
    embedder: Embedder,
) -> None:
    """Incremental ingest (watermarked, ON CONFLICT-idempotent) -> incremental mining
    (mine_new_evidence(), unprocessed evidence only) -> IngestionJob finalized SUCCEEDED/FAILED.

    Never raises past this function — a run that fails midway is an observable FAILED job
    (error_summary + counts of whatever *did* commit before the failure), not a crash of the
    caller (scheduler loop, or the background task the router schedules). Nothing already
    committed by ingestion or mining is rolled back on a later failure — only this function's
    own uncommitted job-field updates are discarded.
    """
    try:
        project = await session.get(Project, project_id)
        if project is None or not project.github_repo:
            raise ValueError(f"Project {project_id} has no configured GitHub repository")
        repo = project.github_repo

        config = _discovery_config()
        overlap_buffer = timedelta(
            days=int(config.get("overlap_buffer_days", _DEFAULT_OVERLAP_BUFFER_DAYS))
        )
        cold_start_lookback = timedelta(
            days=int(config.get("cold_start_lookback_days", _DEFAULT_COLD_START_LOOKBACK_DAYS))
        )

        now = datetime.now(UTC).replace(tzinfo=None)
        watermark = project.discovery_pr_corpus_watermark_at
        repo_created_at = None if watermark is not None else await asyncio.to_thread(
            github_client.get_repository_created_at, repo
        )
        since_dt = _discovery_since(
            watermark=watermark,
            repo_created_at=repo_created_at,
            now=now,
            overlap_buffer=overlap_buffer,
            cold_start_lookback=cold_start_lookback,
        )
        until_dt = now

        ingest_summary = await ingest_pr_corpus(
            session, github_client, repo=repo, since=since_dt.date(), until=until_dt.date()
        )
        job.new_raw_evidence_count = ingest_summary.rows_inserted
        # Advanced only after ingestion has fully committed above — a failure before this line
        # leaves the watermark untouched, so the next run re-covers the same window (idempotent
        # via ON CONFLICT, not a duplicate).
        project.discovery_pr_corpus_watermark_at = until_dt
        await session.commit()

        mining_summary = await mine_new_evidence(
            session, llm, embedder, repo=repo, trace_id_prefix=f"f6-discovery:{project_id}"
        )
        job.total_evidence_count = mining_summary.evidence_units_total
        job.processed_evidence_count = mining_summary.evidence_units_total - len(
            mining_summary.evidence_units_extraction_failed
        )
        job.extraction_failure_count = len(mining_summary.evidence_units_extraction_failed)
        job.eligible_count = mining_summary.evidence_units_eligible
        job.families_created_count = mining_summary.families_created
        job.families_updated_count = mining_summary.families_reinforced

        job.status = IngestionJobStatus.SUCCEEDED
        job.finished_at = datetime.now(UTC).replace(tzinfo=None)
        await session.commit()
    except Exception as exc:  # noqa: BLE001 - a run's failure must surface as FAILED, never crash the caller
        await session.rollback()
        logger.error(
            "convention_discovery_run_failed project_id=%s error=%s", project_id, exc, exc_info=True
        )
        job.status = IngestionJobStatus.FAILED
        job.finished_at = datetime.now(UTC).replace(tzinfo=None)
        job.error_summary = _safe_error_summary(exc)
        session.add(job)
        await session.commit()


async def run_discovery(
    session: AsyncSession,
    project_id: int,
    *,
    trigger_type: IngestionJobTriggerType,
    triggered_by_user_id: int | None,
    github_client: GithubClient,
    llm: ChatOpenAI,
    embedder: Embedder,
) -> IngestionJob:
    """Scheduler-loop entrypoint: reserve + execute in the caller's own session, in one call.
    No HTTP request is involved here, so blocking for the whole run is fine — the router uses
    `start_discovery_run_in_background` + `run_reserved_discovery_job` instead, precisely so a
    real repo's ingest+mining time (minutes, for a repo with a large PR history) never blocks a
    PM's request (CHANGE_LOG.md — this used to be one blocking call here too).
    """
    job = await _reserve_run(
        session, project_id, trigger_type=trigger_type, triggered_by_user_id=triggered_by_user_id
    )
    await _execute_run(session, job, project_id, github_client=github_client, llm=llm, embedder=embedder)
    return job


async def start_discovery_run_in_background(
    session: AsyncSession,
    project_id: int,
    *,
    trigger_type: IngestionJobTriggerType,
    triggered_by_user_id: int | None,
) -> IngestionJob:
    """Router-facing half: reserve only, so `AlreadyRunningError` (-> 409) is still an immediate
    response. The caller (the `run-now` endpoint) must schedule `run_reserved_discovery_job` —
    e.g. via `BackgroundTasks.add_task` — to do the slow part. Same split as
    `knowledge_document_router.sync_project_from_github`/`_run_github_sync`.
    """
    return await _reserve_run(
        session, project_id, trigger_type=trigger_type, triggered_by_user_id=triggered_by_user_id
    )


async def claim_next_discovery_job(session: AsyncSession) -> IngestionJob | None:
    """Atomically claim one queued convention-discovery job for a worker."""
    job = await session.scalar(
        select(IngestionJob)
        .where(IngestionJob.job_type == IngestionJobType.RULE_MINING, IngestionJob.status == IngestionJobStatus.PENDING)
        .order_by(IngestionJob.created_at, IngestionJob.ingestion_job_id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        return None
    job.status = IngestionJobStatus.RUNNING
    job.started_at = datetime.now(UTC).replace(tzinfo=None)
    await session.commit()
    return job


async def fail_stale_discovery_jobs(session: AsyncSession, *, before: datetime) -> int:
    """Mark work abandoned by a terminated worker as retryable on the next trigger."""
    result = await session.execute(
        update(IngestionJob)
        .where(
            IngestionJob.job_type == IngestionJobType.RULE_MINING,
            IngestionJob.status == IngestionJobStatus.RUNNING,
            IngestionJob.started_at < before,
        )
        .values(status=IngestionJobStatus.FAILED, finished_at=datetime.now(UTC).replace(tzinfo=None), error_summary="worker_interrupted")
    )
    await session.commit()
    return result.rowcount or 0


async def run_reserved_discovery_job(
    ingestion_job_id: int,
    project_id: int,
    *,
    github_client: GithubClient,
    llm: ChatOpenAI,
    embedder: Embedder,
) -> None:
    """Runs after the 202 response, with a session that outlives the request — mirrors
    `knowledge_document_router._run_github_sync` exactly."""
    async with AsyncSessionLocal() as session:
        job = await session.get(IngestionJob, ingestion_job_id)
        if job is None:
            logger.warning("discovery_job_missing", extra={"ingestion_job_id": ingestion_job_id})
            return
        await _execute_run(session, job, project_id, github_client=github_client, llm=llm, embedder=embedder)
