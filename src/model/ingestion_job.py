from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base
from src.model.enums import IngestionJobStatus, IngestionJobTriggerType, IngestionJobType


class IngestionJob(Base):
    """One run of a background ingestion/mining pipeline (F6 Scheduled Incremental Convention
    Discovery). Generic run-tracking table, not a framework: `job_type` is a discriminator so a
    future job kind (F1/F2 doc sync, digest — see src/workers/README.md) can reuse this same
    table instead of a parallel one, matching the "one shared log/table, not a second one"
    spirit already applied to llm_call_logs elsewhere in this codebase.

    The partial unique index below IS the overlap-prevention mechanism (CLAUDE.md's
    "idempotency at the DB boundary"): starting a run is a plain INSERT with status=RUNNING; a
    concurrent attempt on the same project hits a unique-violation, mapped to 409 at the router —
    no explicit locking code, no Redis.
    """

    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        # `sqlite_where` alongside `postgresql_where`: without it, SQLAlchemy silently drops the
        # WHERE clause on SQLite (tests/conftest.py::db_session), compiling this as an
        # unconditional unique index on project_id instead of a partial one — that would wrongly
        # forbid a second job (any status) for the same project, breaking every test that runs
        # discovery twice for one project. Both dialects need the same partial-index semantics
        # for this overlap lock to mean the same thing in tests as in production.
        Index(
            "uq_ingestion_jobs_one_active_per_project_operation",
            "project_id",
            "job_type",
            unique=True,
            postgresql_where=text("status IN ('PENDING', 'RUNNING')"),
            sqlite_where=text("status IN ('PENDING', 'RUNNING')"),
        ),
    )

    ingestion_job_id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.project_id"), nullable=False)
    job_type: Mapped[IngestionJobType] = mapped_column(
        Enum(IngestionJobType, name="ingestion_job_type"), nullable=False
    )
    trigger_type: Mapped[IngestionJobTriggerType] = mapped_column(
        Enum(IngestionJobTriggerType, name="ingestion_job_trigger_type"), nullable=False
    )
    status: Mapped[IngestionJobStatus] = mapped_column(
        Enum(IngestionJobStatus, name="ingestion_job_status"),
        nullable=False,
        default=IngestionJobStatus.PENDING,
    )
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    new_raw_evidence_count: Mapped[int] = mapped_column(nullable=False, default=0)
    total_evidence_count: Mapped[int] = mapped_column(nullable=False, default=0)
    processed_evidence_count: Mapped[int] = mapped_column(nullable=False, default=0)
    extraction_failure_count: Mapped[int] = mapped_column(nullable=False, default=0)
    eligible_count: Mapped[int] = mapped_column(nullable=False, default=0)
    families_created_count: Mapped[int] = mapped_column(nullable=False, default=0)
    families_updated_count: Mapped[int] = mapped_column(nullable=False, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # NULL for a SCHEDULED trigger — nobody to attribute a scheduler tick to.
    triggered_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
