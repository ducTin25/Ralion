"""Scope background-job reservations by project and operation.

Revision ID: a7c8d9e0f1a2
Revises: 0dd345991838
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a7c8d9e0f1a2"
down_revision: str | Sequence[str] | None = "0dd345991838"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PostgreSQL enums are append-only in normal deployments. The value is committed before
    # application code can reserve a GITHUB_SYNC row; SQLite test metadata uses a VARCHAR enum.
    op.execute("ALTER TYPE ingestion_job_type ADD VALUE IF NOT EXISTS 'GITHUB_SYNC'")
    op.drop_index("uq_ingestion_jobs_one_running_per_project", table_name="ingestion_jobs")
    op.create_index(
        "uq_ingestion_jobs_one_running_per_project_operation",
        "ingestion_jobs",
        ["project_id", "job_type"],
        unique=True,
        postgresql_where=sa.text("status = 'RUNNING'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_ingestion_jobs_one_running_per_project_operation", table_name="ingestion_jobs"
    )
    op.create_index(
        "uq_ingestion_jobs_one_running_per_project",
        "ingestion_jobs",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status = 'RUNNING'"),
    )
    # PostgreSQL cannot remove one enum value without rebuilding the type. Keeping the unused
    # value is safe and makes downgrade non-destructive.
