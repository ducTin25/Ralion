from __future__ import annotations

from pydantic import BaseModel

from src.services.plan_generation.job_store import GenerationJob, JobStatus, StepStatus


class GenerationStepResponseDTO(BaseModel):
    key: str
    label: str
    status: StepStatus
    # Thời gian THẬT đã chạy của bước đó (ms) — FE dùng số này để hiển thị, không tự bịa animation.
    duration_ms: int | None
    detail: str | None
    progress_done: int | None
    progress_total: int | None
    document_count: int | None


class PlanGenerationJobResponseDTO(BaseModel):
    """Tiến độ 1 lần sinh Candidate Plan. `correlation_id` để tra ngược log/trace khi cần debug."""

    job_id: str
    correlation_id: str
    # Đúng 1 trong 2: membership_id = cấp plan cho kỹ sư, project_id = sinh lộ trình chuẩn dự án.
    membership_id: int | None
    project_id: int | None
    status: JobStatus
    steps: list[GenerationStepResponseDTO]
    plan_id: int | None
    error: str | None
    total_duration_ms: int | None
    warnings: list[str]

    @classmethod
    def from_job(cls, job: GenerationJob) -> PlanGenerationJobResponseDTO:
        return cls(
            job_id=job.job_id,
            correlation_id=job.correlation_id,
            membership_id=job.membership_id,
            project_id=job.project_id,
            status=job.status,
            steps=[
                GenerationStepResponseDTO(
                    key=step.key,
                    label=step.label,
                    status=step.status,
                    duration_ms=step.duration_ms,
                    detail=step.detail,
                    progress_done=step.progress_done,
                    progress_total=step.progress_total,
                    document_count=step.document_count,
                )
                for step in job.steps
            ],
            plan_id=job.plan_id,
            error=job.error,
            total_duration_ms=job.total_duration_ms,
            warnings=job.warnings,
        )
