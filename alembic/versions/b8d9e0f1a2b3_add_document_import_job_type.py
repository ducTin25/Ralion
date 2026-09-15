"""Add document-folder import to the shared background-job discriminator.

Revision ID: b8d9e0f1a2b3
Revises: a7c8d9e0f1a2
Create Date: 2026-08-27
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b8d9e0f1a2b3"
down_revision: str | Sequence[str] | None = "a7c8d9e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE ingestion_job_type ADD VALUE IF NOT EXISTS 'DOCUMENT_IMPORT'")


def downgrade() -> None:
    # PostgreSQL cannot remove one enum value without rebuilding the type. Keeping the unused
    # value is safe and makes downgrade non-destructive.
    pass
