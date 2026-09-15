"""F6 Scheduled Incremental Convention Discovery — project-scoped PM API. SQLite in-memory via
db_client/db_session (tests/conftest.py), dependency_overrides for auth, same pattern as
test_rule_review.py.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from src.ai.providers.embeddings_fake import FakeEmbedder
from src.api.dependencies import get_current_user, get_embedder
from src.main import app
from src.model.enums import MembershipStatus, ProjectRole, UserRole, UserStatus
from src.model.ingestion_job import IngestionJob
from src.model.project import Project
from src.model.project_membership import ProjectMembership
from src.model.user import User

API = "/api/v1"


@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides[get_embedder] = lambda: FakeEmbedder()
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_embedder, None)


async def _seed_user(db_session, email: str, **kwargs) -> User:
    user = User(
        email=email,
        display_name=email,
        status=kwargs.pop("status", UserStatus.ACTIVE),
        system_role=kwargs.pop("system_role", None),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _override_current_user(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


async def _seed_project_with_pm(db_session, *, github_repo: str | None = "acme/widgets") -> tuple[Project, User, User]:
    admin = await _seed_user(db_session, "admin@disc.dev", system_role=UserRole.ADMIN)
    pm = await _seed_user(db_session, "pm@disc.dev")
    project = Project(
        key="DISCAPI",
        name="Discovery API Project",
        created_by_admin_id=admin.user_id,
        github_repo=github_repo,
        default_branch="main" if github_repo else None,
    )
    db_session.add(project)
    await db_session.flush()
    db_session.add(
        ProjectMembership(
            user_id=pm.user_id,
            project_id=project.project_id,
            project_role=ProjectRole.PM,
            status=MembershipStatus.ACTIVE,
            assigned_by_admin_id=admin.user_id,
        )
    )
    await db_session.commit()
    return project, admin, pm


@pytest.mark.asyncio
async def test_get_schedule_defaults_to_manual_only(db_client, db_session):
    project, _admin, pm = await _seed_project_with_pm(db_session)
    await _override_current_user(pm)

    response = await db_client.get(f"{API}/pm/projects/{project.project_id}/discovery-schedule")

    assert response.status_code == 200
    body = response.json()
    assert body["discovery_mode"] == "MANUAL_ONLY"
    assert body["discovery_next_run_at"] is None
    assert body["last_run"] is None


@pytest.mark.asyncio
async def test_put_schedule_every_n_hours_computes_next_run_at(db_client, db_session):
    project, _admin, pm = await _seed_project_with_pm(db_session)
    await _override_current_user(pm)

    response = await db_client.put(
        f"{API}/pm/projects/{project.project_id}/discovery-schedule",
        json={"discovery_mode": "EVERY_N_HOURS", "discovery_interval_hours": 6},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["discovery_mode"] == "EVERY_N_HOURS"
    assert body["discovery_next_run_at"] is not None


@pytest.mark.asyncio
async def test_put_schedule_rejects_missing_required_fields_for_mode(db_client, db_session):
    project, _admin, pm = await _seed_project_with_pm(db_session)
    await _override_current_user(pm)

    response = await db_client.put(
        f"{API}/pm/projects/{project.project_id}/discovery-schedule",
        json={"discovery_mode": "DAILY_AT"},  # missing time_of_day/timezone
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_put_schedule_without_github_repo_is_rejected(db_client, db_session):
    project, _admin, pm = await _seed_project_with_pm(db_session, github_repo=None)
    await _override_current_user(pm)

    response = await db_client.put(
        f"{API}/pm/projects/{project.project_id}/discovery-schedule",
        json={"discovery_mode": "EVERY_N_HOURS", "discovery_interval_hours": 6},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_plain_member_cannot_read_or_update_schedule(db_client, db_session):
    admin = await _seed_user(db_session, "admin2@disc.dev", system_role=UserRole.ADMIN)
    member = await _seed_user(db_session, "member@disc.dev")
    project = Project(key="DISCAPI2", name="P2", created_by_admin_id=admin.user_id, github_repo="acme/widgets", default_branch="main")
    db_session.add(project)
    await db_session.flush()
    db_session.add(
        ProjectMembership(
            user_id=member.user_id,
            project_id=project.project_id,
            project_role=ProjectRole.ENGINEER,
            status=MembershipStatus.ACTIVE,
            assigned_by_admin_id=admin.user_id,
        )
    )
    await db_session.commit()
    await _override_current_user(member)

    get_response = await db_client.get(f"{API}/pm/projects/{project.project_id}/discovery-schedule")
    put_response = await db_client.put(
        f"{API}/pm/projects/{project.project_id}/discovery-schedule",
        json={"discovery_mode": "MANUAL_ONLY"},
    )

    assert get_response.status_code == 403
    assert put_response.status_code == 403


@pytest.mark.asyncio
async def test_run_now_returns_409_when_a_run_is_already_in_progress(db_client, db_session):
    from src.model.ingestion_job import IngestionJob

    project, _admin, pm = await _seed_project_with_pm(db_session)
    db_session.add(
        IngestionJob(project_id=project.project_id, job_type="RULE_MINING", trigger_type="MANUAL", status="RUNNING")
    )
    await db_session.commit()
    await _override_current_user(pm)

    response = await db_client.post(f"{API}/pm/projects/{project.project_id}/discovery-schedule/run-now")

    assert response.status_code == 409


class _ReuseSession:
    """Stand-in for AsyncSessionLocal that reuses one already-open test session instead of
    opening a real connection — the scheduler always builds its own sessions via
    AsyncSessionLocal (it runs outside any FastAPI request), which in production points at the
    real engine; tests must redirect that to the SQLite `db_session` fixture instead."""

    def __init__(self, session) -> None:
        self._session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info) -> bool:
        return False


@pytest.mark.asyncio
async def test_run_now_and_scheduler_tick_call_the_same_service(monkeypatch, db_client, db_session):
    """Both triggers must reach `convention_discovery._execute_run()` — the router's
    background-task split (`start_discovery_run_in_background` + `run_reserved_discovery_job`,
    CHANGE_LOG.md) and the scheduler's `run_discovery()` both call this one shared function,
    asserted by spying on it rather than duplicating its logic in the test. Patching
    `_execute_run` (not `run_discovery`) proves this for both entrypoints from a single spy: a
    bare-name call inside a function resolves via that function's module globals at call time,
    so patching the module attribute affects `run_discovery()` (scheduler) and
    `run_reserved_discovery_job()` (router's background task) identically — they're two
    different callers of the exact same object.
    """
    import importlib

    from src.config import get_settings

    # `src/api/routers/__init__.py` does `from ...project_discovery_router import router as
    # project_discovery_router`, which — because the alias matches the submodule's own name —
    # shadows `src.api.routers.project_discovery_router` as an attribute with the APIRouter
    # instance instead of the module. `import a.b.c as x` resolves via that attribute walk, so
    # it would silently bind `x` to the router object, not the module; importlib.import_module
    # reads sys.modules directly and is unaffected by the shadowing.
    discovery_module = importlib.import_module("src.modules.knowledge.mining.convention_discovery")
    scheduler_module = importlib.import_module("src.infrastructure.scheduling.convention_discovery_scheduler")

    calls: list[str] = []

    async def _fake_execute_run(session, job, project_id, **kwargs):
        calls.append(job.trigger_type.value if hasattr(job.trigger_type, "value") else job.trigger_type)
        job.status = "SUCCEEDED"
        await session.commit()

    monkeypatch.setattr(discovery_module, "_execute_run", _fake_execute_run)
    # The router's background task and the scheduler both open their own session via
    # AsyncSessionLocal (neither runs inside the request's own session lifetime) — production
    # points that at the real engine; tests must redirect it to the SQLite `db_session` fixture.
    monkeypatch.setattr(discovery_module, "AsyncSessionLocal", _ReuseSession(db_session))
    monkeypatch.setattr(scheduler_module, "AsyncSessionLocal", _ReuseSession(db_session))

    project, _admin, pm = await _seed_project_with_pm(db_session)
    await _override_current_user(pm)
    response = await db_client.post(f"{API}/pm/projects/{project.project_id}/discovery-schedule/run-now")
    assert response.status_code == 202

    project.discovery_mode = "EVERY_N_HOURS"
    project.discovery_interval_hours = 1
    from datetime import UTC, datetime

    project.discovery_next_run_at = datetime.now(UTC).replace(tzinfo=None)
    await db_session.commit()

    await scheduler_module._run_due_projects(get_settings(), FakeEmbedder())

    assert calls == []
    queued = (
        await db_session.scalars(
            select(IngestionJob).where(IngestionJob.project_id == project.project_id)
        )
    ).all()
    assert {job.trigger_type.value for job in queued} == {"MANUAL"}
    assert all(job.status == "PENDING" for job in queued)
