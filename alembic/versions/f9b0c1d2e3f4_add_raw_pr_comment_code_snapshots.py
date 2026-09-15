"""Persist GitHub diff context alongside raw PR comments.

Revision ID: f9b0c1d2e3f4
Revises: f2a4c6e8b0d1
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f9b0c1d2e3f4"
down_revision: str | Sequence[str] | None = "f2a4c6e8b0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("raw_pr_comments", sa.Column("code_snippet_snapshot", sa.Text(), nullable=True))
    op.add_column("raw_pr_comments", sa.Column("code_path_snapshot", sa.Text(), nullable=True))
    op.add_column("raw_pr_comments", sa.Column("code_before_snapshot", sa.Text(), nullable=True))
    op.add_column("raw_pr_comments", sa.Column("code_after_snapshot", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("raw_pr_comments", "code_after_snapshot")
    op.drop_column("raw_pr_comments", "code_before_snapshot")
    op.drop_column("raw_pr_comments", "code_path_snapshot")
    op.drop_column("raw_pr_comments", "code_snippet_snapshot")
