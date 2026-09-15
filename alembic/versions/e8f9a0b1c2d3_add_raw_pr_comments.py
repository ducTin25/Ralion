"""F6 ingestion — raw_pr_comments (F2 Sub-flow B corpus staging table).

Minimal fallback schema (Phase 2 of F6 prep): F6_RULE_MINING_SPEC.md §1.2 references
a base-plan §2 design for this table that is not present in this worktree (confirmed
absent — see Phase 0 audit and CHANGE_LOG.md). Shape matches what
scripts/density_check.py's CSV output already validated; no separate PR-level table
(no join-by-PR-metadata use case exists yet — see CHANGE_LOG.md for the reasoning).

Draft only — not applied, not merged.

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-08-20

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e8f9a0b1c2d3"
down_revision: str | Sequence[str] | None = "d7e8f9a0b1c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "raw_pr_comments",
        sa.Column("raw_pr_comment_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("repo", sa.String(), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("pr_author", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("author", sa.String(), nullable=False),
        sa.Column("is_bot_comment", sa.Boolean(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("review_state", sa.String(), nullable=True),
        sa.Column("in_reply_to_id", sa.BigInteger(), nullable=True),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("secret_scanned_at", sa.DateTime(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("raw_pr_comment_id", name=op.f("pk_raw_pr_comments")),
    )
    # F6 mining's two access patterns: scan a repo's whole corpus, and group by PR.
    op.create_index("ix_raw_pr_comments_repo_pr_number", "raw_pr_comments", ["repo", "pr_number"])


def downgrade() -> None:
    op.drop_index("ix_raw_pr_comments_repo_pr_number", table_name="raw_pr_comments")
    op.drop_table("raw_pr_comments")
