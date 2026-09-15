"""Add discovery queue progress and reserve queued jobs per operation.

Revision ID: b9e0f1a2c3d4
Revises: a78c30f7bc98, b8d9e0f1a2b3, c6e7f8a9b0d1
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b9e0f1a2c3d4"
down_revision: str | Sequence[str] | None = ("a78c30f7bc98", "b8d9e0f1a2b3", "c6e7f8a9b0d1")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ingestion_jobs", sa.Column("total_evidence_count", sa.Integer(), nullable=False, server_default="0")
    )
    op.drop_index("uq_ingestion_jobs_one_running_per_project_operation", table_name="ingestion_jobs")
    op.create_index(
        "uq_ingestion_jobs_one_active_per_project_operation",
        "ingestion_jobs",
        ["project_id", "job_type"],
        unique=True,
        postgresql_where=sa.text("status IN ('PENDING', 'RUNNING')"),
    )


def downgrade() -> None:
    op.drop_index("uq_ingestion_jobs_one_active_per_project_operation", table_name="ingestion_jobs")
    op.create_index(
        "uq_ingestion_jobs_one_running_per_project_operation",
        "ingestion_jobs",
        ["project_id", "job_type"],
        unique=True,
        postgresql_where=sa.text("status = 'RUNNING'"),
    )
    op.drop_column("ingestion_jobs", "total_evidence_count")
