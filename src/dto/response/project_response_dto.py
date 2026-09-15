from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from src.dto.response.discovery_schedule_response_dto import IngestionJobResponseDTO
from src.model.enums import GithubCredentialValidationStatus, ProjectStatus, SyncStatus
from src.model.ingestion_job import IngestionJob
from src.model.project import Project


class ProjectResponseDTO(BaseModel):
    project_id: int
    key: str
    name: str
    primary_pm_membership_id: int | None
    created_by_admin_id: int
    status: ProjectStatus
    sync_status: SyncStatus
    last_synced_at: datetime | None
    created_at: datetime
    github_repo: str | None
    default_branch: str | None
    # None = no `project_github_credentials` row (never connected, or a legacy project from
    # before per-project credentials existed) — a distinct, non-error state the FE renders on
    # its own, not folded into VALID/INVALID. See github_credential_provider.get_status.
    github_credential_status: Literal["VALID", "INVALID"] | None
    github_sync_job: IngestionJobResponseDTO | None = None

    @classmethod
    def from_entity(
        cls,
        project: Project,
        credential_status: GithubCredentialValidationStatus | None,
        github_sync_job: IngestionJob | None = None,
    ) -> ProjectResponseDTO:
        return cls(
            project_id=project.project_id,
            key=project.key,
            name=project.name,
            primary_pm_membership_id=project.primary_pm_membership_id,
            created_by_admin_id=project.created_by_admin_id,
            status=project.status,
            sync_status=project.sync_status,
            last_synced_at=project.last_synced_at,
            created_at=project.created_at,
            github_repo=project.github_repo,
            default_branch=project.default_branch,
            github_credential_status=(
                credential_status.value
                if credential_status
                in (GithubCredentialValidationStatus.VALID, GithubCredentialValidationStatus.INVALID)
                else None
            ),
            github_sync_job=(
                IngestionJobResponseDTO.from_entity(github_sync_job)
                if github_sync_job is not None
                else None
            ),
        )
