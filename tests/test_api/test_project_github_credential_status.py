"""`ProjectResponseDTO.github_credential_status` end-to-end through the real router/DTO wiring —
`tests/test_modules/test_github_credential_provider.py` already covers the provider's own
encrypt/decrypt/status logic in isolation; this pins that the API surface actually exposes it.
"""

from uuid import uuid4

import pytest

from src.model.enums import ProjectStatus, UserRole, UserStatus
from src.model.project import Project
from src.model.user import User
from src.modules.knowledge.ingestion import github_credential_provider
from src.services import project_service


class _FakeGithubClient:
    should_succeed = True

    def __init__(self, token: str) -> None:
        pass

    def get_branch_head_sha(self, repo: str, branch: str) -> str:
        if not type(self).should_succeed:
            raise RuntimeError("GitHub GET /repos/owner/repo/git/ref/heads/main failed with HTTP 401")
        return "abc123"


@pytest.fixture(autouse=True)
def _reset_fake_client():
    _FakeGithubClient.should_succeed = True
    yield


async def _seed_admin_and_project(db_session) -> tuple[int, int]:
    admin = User(
        email=f"admin-{uuid4().hex}@example.test",
        display_name="Admin",
        system_role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
    )
    db_session.add(admin)
    await db_session.flush()
    project = Project(
        key=f"CRED{uuid4().hex[:8].upper()}",
        name="Credential Status Project",
        created_by_admin_id=admin.user_id,
        status=ProjectStatus.ACTIVE,
        github_repo="owner/repo",
        default_branch="main",
    )
    db_session.add(project)
    await db_session.commit()
    return admin.user_id, project.project_id


@pytest.mark.asyncio
async def test_get_project_reports_none_when_no_credential_connected(db_client, db_session) -> None:
    admin_id, project_id = await _seed_admin_and_project(db_session)

    response = await db_client.get(
        f"/api/v1/projects/pm/{project_id}", headers={"X-User-Id": str(admin_id)}
    )

    assert response.status_code == 200
    assert response.json()["github_credential_status"] is None


@pytest.mark.asyncio
async def test_get_project_reports_invalid_after_mark_invalid(db_client, db_session) -> None:
    admin_id, project_id = await _seed_admin_and_project(db_session)
    await github_credential_provider.store_validated_token(db_session, project_id, "ghp_token")
    await github_credential_provider.mark_invalid(db_session, project_id, "HTTP 401")

    response = await db_client.get(
        f"/api/v1/projects/pm/{project_id}", headers={"X-User-Id": str(admin_id)}
    )

    assert response.status_code == 200
    assert response.json()["github_credential_status"] == "INVALID"


@pytest.mark.asyncio
async def test_connect_github_repo_response_reports_valid_immediately(
    db_client, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(project_service, "GithubClient", _FakeGithubClient)
    admin = User(
        email=f"admin-{uuid4().hex}@example.test",
        display_name="Admin",
        system_role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
    )
    db_session.add(admin)
    await db_session.flush()
    project = Project(
        key=f"CONN{uuid4().hex[:8].upper()}",
        name="Connect Credential Status Project",
        created_by_admin_id=admin.user_id,
        status=ProjectStatus.ACTIVE,
    )
    db_session.add(project)
    await db_session.commit()

    response = await db_client.patch(
        f"/api/v1/knowledge-documents/pm/projects/{project.project_id}/github-repo",
        headers={"X-User-Id": str(admin.user_id)},
        json={"github_repo": "octocat/Hello-World", "default_branch": "main", "github_token": "ghp_x"},
    )

    assert response.status_code == 200
    assert response.json()["github_credential_status"] == "VALID"
