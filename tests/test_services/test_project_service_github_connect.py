from uuid import uuid4

import pytest

from src.model.enums import GithubCredentialValidationStatus, ProjectStatus, UserStatus
from src.model.project import Project
from src.model.project_github_credential import ProjectGithubCredential
from src.model.user import User
from src.services import project_service


class _FakeGithubClient:
    """Stands in for `GithubClient` in `project_service.connect_github_repo` — records the token
    it was built with and either succeeds or raises like the real HTTP call would on a bad
    token/repo/branch."""

    should_succeed = True
    last_token: str | None = None

    def __init__(self, token: str) -> None:
        type(self).last_token = token

    def get_branch_head_sha(self, repo: str, branch: str) -> str:
        if not type(self).should_succeed:
            raise RuntimeError("GitHub GET /repos/owner/repo/git/ref/heads/main failed with HTTP 401")
        return "abc123"


@pytest.fixture(autouse=True)
def _reset_fake_client():
    _FakeGithubClient.should_succeed = True
    _FakeGithubClient.last_token = None
    yield


async def _make_project(db_session) -> Project:
    user = User(
        email=f"connect-{uuid4().hex}@example.test",
        display_name="Connect Test PM",
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    await db_session.flush()
    project = Project(
        key=f"CONN{uuid4().hex[:8].upper()}",
        name="Connect Test Project",
        created_by_admin_id=user.user_id,
        status=ProjectStatus.ACTIVE,
    )
    db_session.add(project)
    await db_session.commit()
    return project


@pytest.mark.asyncio
async def test_connect_github_repo_validates_before_persisting(db_session, monkeypatch) -> None:
    monkeypatch.setattr(project_service, "GithubClient", _FakeGithubClient)
    project = await _make_project(db_session)

    updated = await project_service.connect_github_repo(
        db_session, project.project_id, "octocat/Hello-World", "main", "ghp_realtoken"
    )

    assert updated is not None
    assert updated.github_repo == "octocat/Hello-World"
    assert updated.default_branch == "main"
    assert _FakeGithubClient.last_token == "ghp_realtoken"

    credential = await db_session.get(ProjectGithubCredential, project.project_id)
    assert credential is not None
    assert credential.validation_status == GithubCredentialValidationStatus.VALID
    assert credential.token_ciphertext != b"ghp_realtoken"


@pytest.mark.asyncio
async def test_connect_github_repo_rejects_bad_token_without_touching_project_or_storing_it(
    db_session, monkeypatch
) -> None:
    monkeypatch.setattr(project_service, "GithubClient", _FakeGithubClient)
    _FakeGithubClient.should_succeed = False
    project = await _make_project(db_session)

    with pytest.raises(project_service.GithubCredentialValidationError):
        await project_service.connect_github_repo(
            db_session, project.project_id, "octocat/Hello-World", "main", "ghp_badtoken"
        )

    await db_session.refresh(project)
    assert project.github_repo is None
    assert project.default_branch is None
    assert await db_session.get(ProjectGithubCredential, project.project_id) is None


@pytest.mark.asyncio
async def test_connect_github_repo_missing_project_returns_none(db_session, monkeypatch) -> None:
    monkeypatch.setattr(project_service, "GithubClient", _FakeGithubClient)

    result = await project_service.connect_github_repo(
        db_session, 999_999, "octocat/Hello-World", "main", "ghp_token"
    )

    assert result is None
