from uuid import uuid4

import pytest

from src.config import get_settings
from src.model.enums import GithubCredentialValidationStatus, ProjectStatus, UserStatus
from src.model.project import Project
from src.model.project_github_credential import ProjectGithubCredential
from src.model.user import User
from src.modules.knowledge.ingestion import github_credential_provider


async def _make_project(db_session) -> Project:
    user = User(
        email=f"cred-{uuid4().hex}@example.test",
        display_name="Credential Test PM",
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    await db_session.flush()
    project = Project(
        key=f"CRED{uuid4().hex[:8].upper()}",
        name="Credential Test Project",
        created_by_admin_id=user.user_id,
        status=ProjectStatus.ACTIVE,
        github_repo="owner/repo",
        default_branch="main",
    )
    db_session.add(project)
    await db_session.commit()
    return project


@pytest.mark.asyncio
async def test_store_validated_token_roundtrips_through_encryption(db_session) -> None:
    project = await _make_project(db_session)

    await github_credential_provider.store_validated_token(db_session, project.project_id, "ghp_secret123")

    row = await db_session.get(ProjectGithubCredential, project.project_id)
    assert row is not None
    assert row.token_ciphertext != b"ghp_secret123"  # never stored as plaintext
    assert row.validation_status == GithubCredentialValidationStatus.VALID
    assert row.last_validated_at is not None

    token = await github_credential_provider.get_token(db_session, project.project_id)
    assert token == "ghp_secret123"


@pytest.mark.asyncio
async def test_get_token_without_connected_credential_uses_dev_fallback(db_session) -> None:
    project = await _make_project(db_session)
    settings = get_settings()
    original_env, original_token = settings.app_env, settings.github_token
    settings.app_env = "development"
    settings.github_token = "fallback-token"
    try:
        token = await github_credential_provider.get_token(db_session, project.project_id)
        assert token == "fallback-token"
    finally:
        settings.app_env, settings.github_token = original_env, original_token


@pytest.mark.asyncio
async def test_get_token_without_credential_or_fallback_raises_clear_error(db_session) -> None:
    project = await _make_project(db_session)
    settings = get_settings()
    original_env, original_token = settings.app_env, settings.github_token
    settings.app_env = "production"
    settings.github_token = ""
    try:
        with pytest.raises(github_credential_provider.GithubCredentialError, match="chưa kết nối"):
            await github_credential_provider.get_token(db_session, project.project_id)
    finally:
        settings.app_env, settings.github_token = original_env, original_token


@pytest.mark.asyncio
async def test_dev_fallback_never_used_in_production_even_when_set(db_session) -> None:
    project = await _make_project(db_session)
    settings = get_settings()
    original_env, original_token = settings.app_env, settings.github_token
    settings.app_env = "production"
    settings.github_token = "should-not-be-used"
    try:
        with pytest.raises(github_credential_provider.GithubCredentialError):
            await github_credential_provider.get_token(db_session, project.project_id)
    finally:
        settings.app_env, settings.github_token = original_env, original_token


@pytest.mark.asyncio
async def test_invalid_credential_raises_reconnect_error_instead_of_returning_stale_token(db_session) -> None:
    project = await _make_project(db_session)
    await github_credential_provider.store_validated_token(db_session, project.project_id, "ghp_old")
    await github_credential_provider.mark_invalid(db_session, project.project_id, "HTTP 401")

    with pytest.raises(github_credential_provider.GithubCredentialError, match="kết nối lại"):
        await github_credential_provider.get_token(db_session, project.project_id)


@pytest.mark.asyncio
async def test_mark_invalid_is_a_noop_when_no_credential_row_exists(db_session) -> None:
    project = await _make_project(db_session)
    # Should not raise even though nothing was ever connected for this project.
    await github_credential_provider.mark_invalid(db_session, project.project_id, "HTTP 403")
    assert await db_session.get(ProjectGithubCredential, project.project_id) is None


@pytest.mark.asyncio
async def test_reconnecting_overwrites_the_previous_ciphertext_and_clears_invalid_status(db_session) -> None:
    project = await _make_project(db_session)
    await github_credential_provider.store_validated_token(db_session, project.project_id, "ghp_old")
    await github_credential_provider.mark_invalid(db_session, project.project_id, "HTTP 401")

    await github_credential_provider.store_validated_token(db_session, project.project_id, "ghp_new")

    token = await github_credential_provider.get_token(db_session, project.project_id)
    assert token == "ghp_new"
    row = await db_session.get(ProjectGithubCredential, project.project_id)
    assert row.validation_status == GithubCredentialValidationStatus.VALID
    assert row.last_error is None
