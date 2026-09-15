"""Resolves a per-project GitHub credential into a usable token/client. This is the single
place that reads `project_github_credentials` — `github_sync_worker.sync_docs`, F6's
`project_discovery_router` ("Run now") and `convention_discovery_scheduler` (scheduled tick) all
go through `build_client_for_project` instead of each constructing `GithubClient` from settings
directly, so a later swap to GitHub App installation tokens only touches this module.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.core.security.credential_encryption import decrypt_token, encrypt_token
from src.model.enums import GithubCredentialValidationStatus
from src.model.project_github_credential import ProjectGithubCredential
from src.modules.knowledge.ingestion.github_client import GithubClient


class GithubCredentialError(RuntimeError):
    """No usable GitHub credential for this project — connect or reconnect required."""


async def get_status(session: AsyncSession, project_id: int) -> GithubCredentialValidationStatus | None:
    """Read-only lookup for API responses (`ProjectResponseDTO`) — `None` means no credential
    row exists yet (never connected, or a legacy project from before per-project credentials
    existed), never a state the FE has to distinguish from an error."""
    row = await session.get(ProjectGithubCredential, project_id)
    return row.validation_status if row is not None else None


async def get_token(session: AsyncSession, project_id: int) -> str:
    row = await session.get(ProjectGithubCredential, project_id)
    if row is not None:
        if row.validation_status == GithubCredentialValidationStatus.INVALID:
            raise GithubCredentialError(
                f"GitHub credential của project {project_id} không còn hợp lệ "
                "(có thể đã bị thu hồi/hết hạn) — cần kết nối lại repo kèm token mới."
            )
        return decrypt_token(row.token_ciphertext)

    settings = get_settings()
    # Dev/test-only fallback: a project with no connected credential can still sync locally
    # against the single shared PAT from .env, matching the pre-per-project-credential setup.
    # Gated on app_env, not just presence of the row, so this can never be reached in
    # production — there, a missing row always means "not connected yet", full stop.
    if settings.app_env != "production" and settings.github_token:
        return settings.github_token

    raise GithubCredentialError(
        f"Project {project_id} chưa kết nối GitHub credential. PM cần connect repo kèm "
        "Personal Access Token (Contents: Read-only) trước khi đồng bộ."
    )


async def build_client_for_project(session: AsyncSession, project_id: int) -> GithubClient:
    settings = get_settings()
    if settings.app_env == "test" and not settings.github_token:
        # Keep API/worker tests hermetic when no credential is configured anywhere, matching the
        # shortcut project_discovery_router/convention_discovery_scheduler used before this
        # module existed.
        return GithubClient("", transport=lambda _url: [])
    return GithubClient(await get_token(session, project_id))


async def store_validated_token(session: AsyncSession, project_id: int, token: str) -> None:
    """Persist a token the caller has already proven grants read access to the target
    repo/branch (see `project_service.connect_github_repo`). Upserts by `project_id`."""
    row = await session.get(ProjectGithubCredential, project_id)
    if row is None:
        row = ProjectGithubCredential(project_id=project_id)
        session.add(row)
    row.token_ciphertext = encrypt_token(token)
    row.validation_status = GithubCredentialValidationStatus.VALID
    row.last_validated_at = datetime.now(UTC).replace(tzinfo=None)
    row.last_error = None
    await session.commit()


async def mark_invalid(session: AsyncSession, project_id: int, error: str) -> None:
    """Best-effort: flips a connected credential to INVALID after GitHub itself rejects it
    (401/403) during a sync/discovery run, so the next attempt fails fast with a clear
    reconnect message instead of repeating the same failed call. No-op if nothing is connected
    (e.g. the dev-only settings.github_token fallback was used — there is no row to flag)."""
    row = await session.get(ProjectGithubCredential, project_id)
    if row is None:
        return
    row.validation_status = GithubCredentialValidationStatus.INVALID
    row.last_error = error[:500]
    await session.commit()
