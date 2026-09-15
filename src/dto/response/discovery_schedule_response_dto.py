from __future__ import annotations

from datetime import datetime, time

from pydantic import BaseModel

from src.model.enums import DiscoveryMode, IngestionJobStatus, IngestionJobTriggerType
from src.model.ingestion_job import IngestionJob
from src.model.project import Project


class IngestionJobResponseDTO(BaseModel):
    """No model/concurrency/embedding-batch/retry-policy field — only run status and counts."""

    ingestion_job_id: int
    status: IngestionJobStatus
    trigger_type: IngestionJobTriggerType
    started_at: datetime | None
    finished_at: datetime | None
    new_raw_evidence_count: int
    total_evidence_count: int
    processed_evidence_count: int
    extraction_failure_count: int
    eligible_count: int
    families_created_count: int
    families_updated_count: int
    error_summary: str | None

    @classmethod
    def from_entity(cls, job: IngestionJob) -> IngestionJobResponseDTO:
        return cls(
            ingestion_job_id=job.ingestion_job_id,
            status=job.status,
            trigger_type=job.trigger_type,
            started_at=job.started_at,
            finished_at=job.finished_at,
            new_raw_evidence_count=job.new_raw_evidence_count,
            total_evidence_count=job.total_evidence_count,
            processed_evidence_count=job.processed_evidence_count,
            extraction_failure_count=job.extraction_failure_count,
            eligible_count=job.eligible_count,
            families_created_count=job.families_created_count,
            families_updated_count=job.families_updated_count,
            error_summary=job.error_summary,
        )


class DiscoveryScheduleResponseDTO(BaseModel):
    project_id: int
    discovery_mode: DiscoveryMode
    discovery_interval_hours: int | None
    discovery_time_of_day: time | None
    discovery_day_of_week: int | None
    discovery_timezone: str | None
    discovery_next_run_at: datetime | None
    last_run: IngestionJobResponseDTO | None

    @classmethod
    def from_entity(cls, project: Project, last_run: IngestionJob | None) -> DiscoveryScheduleResponseDTO:
        return cls(
            project_id=project.project_id,
            discovery_mode=project.discovery_mode,
            discovery_interval_hours=project.discovery_interval_hours,
            discovery_time_of_day=project.discovery_time_of_day,
            discovery_day_of_week=project.discovery_day_of_week,
            discovery_timezone=project.discovery_timezone,
            discovery_next_run_at=project.discovery_next_run_at,
            last_run=IngestionJobResponseDTO.from_entity(last_run) if last_run is not None else None,
        )
