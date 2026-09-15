from __future__ import annotations

import asyncio
import importlib
import threading
from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks

from src.ai.providers.embeddings_fake import FakeEmbedder
from src.dto.request.knowledge_document_request_dto import (
    ImportScanSelectionRequestDTO,
    ScanSelectionItemDTO,
)
from src.model.enums import (
    IngestionJobStatus,
    IngestionJobTriggerType,
    IngestionJobType,
    SyncStatus,
    UserRole,
    UserStatus,
)
from src.model.project import Project
from src.model.user import User
from src.modules.knowledge.ingestion.pr_corpus_ingestion import ingest_pr_corpus
from src.services import knowledge_document_service, operation_job_service, pm_dashboard_service

knowledge_document_router = importlib.import_module("src.api.routers.knowledge_document_router")


async def _seed_project(db_session) -> tuple[Project, User]:
    admin = User(
        email="jobs-admin@example.test",
        display_name="Jobs Admin",
        system_role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
    )
    db_session.add(admin)
    await db_session.flush()
    project = Project(
        key="JOBS",
        name="Job Lifecycle",
        created_by_admin_id=admin.user_id,
        github_repo="acme/widgets",
        default_branch="main",
    )
    db_session.add(project)
    await db_session.commit()
    return project, admin


class _BlockingGithubClient:
    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()

    def list_merged_prs(self, _repo, _since, _until):
        self.entered.set()
        self.release.wait(timeout=5)
        return []


@pytest.mark.asyncio
async def test_document_import_progresses_while_convention_scan_waits_on_github(
    db_session, monkeypatch
) -> None:
    project, admin = await _seed_project(db_session)
    client = _BlockingGithubClient()
    monkeypatch.setattr(
        knowledge_document_service.storage_service,
        "upload_document_bytes",
        lambda *_args, **_kwargs: "memory://architecture.md",
    )

    scan = asyncio.create_task(
        ingest_pr_corpus(
            db_session,
            client,
            repo=project.github_repo,
            since=datetime(2026, 1, 1).date(),
            until=datetime(2026, 1, 2).date(),
        )
    )
    assert await asyncio.to_thread(client.entered.wait, 1)
    try:
        document, version = await asyncio.wait_for(
            knowledge_document_service.import_single_file(
                db_session,
                project_id=project.project_id,
                category="ARCHITECTURE",
                title="architecture.md",
                filename="architecture.md",
                content=b"# Architecture\n\nServices communicate through documented APIs.",
                created_by_user_id=admin.user_id,
                embedder=FakeEmbedder(),
            ),
            timeout=1,
        )
        assert document.document_id is not None
        assert version.version_id is not None
    finally:
        client.release.set()
        await scan


@pytest.mark.asyncio
async def test_approve_import_handler_returns_before_ingestion_runs(db_session, monkeypatch) -> None:
    project, admin = await _seed_project(db_session)
    ingest = AsyncMock()
    monkeypatch.setattr(knowledge_document_router.knowledge_document_service, "import_scan_selection", ingest)
    background = BackgroundTasks()

    response = await knowledge_document_router.import_scan_selection(
        project_id=project.project_id,
        scan_session_id="scan-kept-for-background",
        dto=ImportScanSelectionRequestDTO(
            selections=[
                ScanSelectionItemDTO(
                    candidate_id="candidate-1",
                    include=True,
                    category="ARCHITECTURE",
                )
            ]
        ),
        current_user=admin,
        background_tasks=background,
        _membership=None,
        db=db_session,
        embedder=FakeEmbedder(),
    )

    assert response.status == IngestionJobStatus.RUNNING
    assert len(background.tasks) == 1
    ingest.assert_not_awaited()


@pytest.mark.asyncio
async def test_background_job_reservations_are_scoped_by_project_and_operation(db_session) -> None:
    project, admin = await _seed_project(db_session)
    mining = await operation_job_service.reserve(
        db_session,
        project.project_id,
        job_type=IngestionJobType.RULE_MINING,
        trigger_type=IngestionJobTriggerType.MANUAL,
        triggered_by_user_id=admin.user_id,
    )
    sync = await operation_job_service.reserve(
        db_session,
        project.project_id,
        job_type=IngestionJobType.GITHUB_SYNC,
        trigger_type=IngestionJobTriggerType.MANUAL,
        triggered_by_user_id=admin.user_id,
    )
    assert mining.status == IngestionJobStatus.RUNNING
    assert sync.status == IngestionJobStatus.RUNNING

    with pytest.raises(operation_job_service.AlreadyRunningError):
        await operation_job_service.reserve(
            db_session,
            project.project_id,
            job_type=IngestionJobType.GITHUB_SYNC,
            trigger_type=IngestionJobTriggerType.MANUAL,
            triggered_by_user_id=admin.user_id,
        )


class _ReuseSession:
    def __init__(self, session) -> None:
        self.session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *_exc_info):
        return False


@pytest.mark.asyncio
async def test_github_job_finishes_only_after_document_indexing_returns(db_session, monkeypatch) -> None:
    project, admin = await _seed_project(db_session)
    job = await operation_job_service.reserve(
        db_session,
        project.project_id,
        job_type=IngestionJobType.GITHUB_SYNC,
        trigger_type=IngestionJobTriggerType.MANUAL,
        triggered_by_user_id=admin.user_id,
    )
    indexing_started = asyncio.Event()
    allow_indexing_to_finish = asyncio.Event()

    async def fake_sync_docs(_session, synced_project, _embedder):
        synced_project.sync_status = SyncStatus.SYNCING
        indexing_started.set()
        await allow_indexing_to_finish.wait()
        synced_project.sync_status = SyncStatus.SUCCESS
        await _session.commit()
        return 5

    monkeypatch.setattr(knowledge_document_router, "AsyncSessionLocal", _ReuseSession(db_session))
    monkeypatch.setattr(knowledge_document_router.github_sync_worker, "sync_docs", fake_sync_docs)

    running = asyncio.create_task(
        knowledge_document_router._run_github_sync(
            job.ingestion_job_id, project.project_id, FakeEmbedder()
        )
    )
    await indexing_started.wait()
    assert job.status == IngestionJobStatus.RUNNING
    assert not running.done()

    allow_indexing_to_finish.set()
    await running
    assert job.status == IngestionJobStatus.SUCCEEDED
    assert job.finished_at is not None
    assert job.processed_evidence_count == 5


@pytest.mark.asyncio
async def test_success_notifications_have_stable_unique_job_ids(db_session) -> None:
    project, admin = await _seed_project(db_session)
    for job_type in (IngestionJobType.GITHUB_SYNC, IngestionJobType.RULE_MINING):
        job = await operation_job_service.reserve(
            db_session,
            project.project_id,
            job_type=job_type,
            trigger_type=IngestionJobTriggerType.MANUAL,
            triggered_by_user_id=admin.user_id,
        )
        await operation_job_service.succeed(db_session, job)

    first = await pm_dashboard_service.list_notifications(db_session, project.project_id)
    second = await pm_dashboard_service.list_notifications(db_session, project.project_id)

    first_ids = [item.notification_id for item in first]
    assert len(first_ids) == len(set(first_ids)) == 2
    assert first_ids == [item.notification_id for item in second]
    assert {item.kind for item in first} == {
        "GITHUB_SYNC_COMPLETED",
        "CONVENTION_SCAN_COMPLETED",
    }
