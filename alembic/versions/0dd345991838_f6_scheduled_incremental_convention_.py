"""F6 Scheduled Incremental Convention Discovery.

Supersedes the one-shot-only cut in F6_RULE_MINING_SPEC.md §4.6 ("không tính lại incremental
khi có PR mới") — see CHANGE_LOG.md for the product decision. Four pieces, all additive:

* `raw_pr_comments`: `github_id` (GitHub's own comment/review id, previously fetched but
  discarded on persist) + a unique constraint on (repo, type, github_id) — the real dedup
  anchor a rerun needs; `mining_processed_at` marks an evidence unit's root comment once F6
  extraction reaches a terminal outcome for it.
* `rule_candidates`: `embedding`/`embedding_model_version` — every eligible candidate's vector
  is now persisted so an incremental run can reuse it instead of re-embedding.
* `ingestion_jobs` (new table): generic run-tracking (`job_type` discriminator, only
  RULE_MINING today) with a partial unique index enforcing at most one RUNNING job per project —
  this IS the overlap-prevention mechanism, no application-level locking.
* `projects`: discovery_* schedule columns (mode/interval/time-of-day/day-of-week/timezone/
  next_run_at/watermark), CHECK-constrained per mode exactly like the existing
  `github_target_paired` pairing idiom.

Revision ID: 0dd345991838
Revises: f9a0b1c2d3e4
Create Date: 2026-08-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import VECTOR

from alembic import op

revision: str = "0dd345991838"
down_revision: str | Sequence[str] | None = "f9a0b1c2d3e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- raw_pr_comments ---------------------------------------------------------------
    op.add_column("raw_pr_comments", sa.Column("github_id", sa.BigInteger(), nullable=True))
    op.add_column(
        "raw_pr_comments", sa.Column("mining_processed_at", sa.DateTime(), nullable=True)
    )
    op.create_unique_constraint(
        op.f("uq_raw_pr_comments_repo_type_github_id"),
        "raw_pr_comments",
        ["repo", "type", "github_id"],
    )

    # ---- rule_candidates ----------------------------------------------------------------
    # pgvector extension already created in b3c4d5e6f7a8; reused, not re-created.
    op.add_column("rule_candidates", sa.Column("embedding", VECTOR(1024), nullable=True))
    op.add_column(
        "rule_candidates", sa.Column("embedding_model_version", sa.String(), nullable=True)
    )
    # Provenance snapshot (same fields RuleEvidence stores) so an eligible-but-orphaned
    # candidate can be reused as a future family member without re-deriving anything from
    # raw_pr_comments/evidence_grouping.
    op.add_column("rule_candidates", sa.Column("evidence_unit_id", sa.String(), nullable=True))
    op.add_column("rule_candidates", sa.Column("pr_number", sa.Integer(), nullable=True))
    op.add_column(
        "rule_candidates", sa.Column("comment_snippet_snapshot", sa.Text(), nullable=True)
    )
    op.add_column("rule_candidates", sa.Column("original_author", sa.String(), nullable=True))
    op.add_column(
        "rule_candidates", sa.Column("evidence_created_at", sa.DateTime(), nullable=True)
    )

    # ---- ingestion_jobs (new) -------------------------------------------------------------
    # Unlike op.add_column, op.create_table DOES auto-issue CREATE TYPE for an inline Postgres
    # enum column — no explicit .create() call here (that would double-create and fail).
    job_type_enum = sa.Enum("RULE_MINING", name="ingestion_job_type")
    trigger_type_enum = sa.Enum("MANUAL", "SCHEDULED", name="ingestion_job_trigger_type")
    status_enum = sa.Enum("PENDING", "RUNNING", "SUCCEEDED", "FAILED", name="ingestion_job_status")

    op.create_table(
        "ingestion_jobs",
        sa.Column("ingestion_job_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("job_type", job_type_enum, nullable=False),
        sa.Column("trigger_type", trigger_type_enum, nullable=False),
        sa.Column("status", status_enum, nullable=False, server_default="PENDING"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("new_raw_evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extraction_failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("eligible_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("families_created_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("families_updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("triggered_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.project_id"], name=op.f("fk_ingestion_jobs_project_id_projects")
        ),
        sa.ForeignKeyConstraint(
            ["triggered_by_user_id"],
            ["users.user_id"],
            name=op.f("fk_ingestion_jobs_triggered_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("ingestion_job_id", name=op.f("pk_ingestion_jobs")),
    )
    op.create_index(
        "uq_ingestion_jobs_one_running_per_project",
        "ingestion_jobs",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status = 'RUNNING'"),
    )

    # ---- projects: discovery schedule ------------------------------------------------------
    discovery_mode_enum = sa.Enum(
        "MANUAL_ONLY", "EVERY_N_HOURS", "DAILY_AT", "WEEKLY_AT", name="discovery_mode"
    )
    discovery_mode_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "projects",
        sa.Column(
            "discovery_mode", discovery_mode_enum, nullable=False, server_default="MANUAL_ONLY"
        ),
    )
    op.add_column("projects", sa.Column("discovery_interval_hours", sa.Integer(), nullable=True))
    op.add_column("projects", sa.Column("discovery_time_of_day", sa.Time(), nullable=True))
    op.add_column("projects", sa.Column("discovery_day_of_week", sa.Integer(), nullable=True))
    op.add_column("projects", sa.Column("discovery_timezone", sa.String(), nullable=True))
    op.add_column("projects", sa.Column("discovery_next_run_at", sa.DateTime(), nullable=True))
    op.add_column(
        "projects", sa.Column("discovery_pr_corpus_watermark_at", sa.DateTime(), nullable=True)
    )
    op.create_check_constraint(
        op.f("ck_projects_discovery_requires_github_repo"),
        "projects",
        "discovery_mode = 'MANUAL_ONLY' OR github_repo IS NOT NULL",
    )
    op.create_check_constraint(
        op.f("ck_projects_discovery_every_n_hours_requires_interval"),
        "projects",
        "discovery_mode != 'EVERY_N_HOURS' OR discovery_interval_hours IS NOT NULL",
    )
    op.create_check_constraint(
        op.f("ck_projects_discovery_interval_hours_min_1"),
        "projects",
        "discovery_interval_hours IS NULL OR discovery_interval_hours >= 1",
    )
    op.create_check_constraint(
        op.f("ck_projects_discovery_daily_weekly_requires_time_and_tz"),
        "projects",
        "discovery_mode NOT IN ('DAILY_AT', 'WEEKLY_AT') OR "
        "(discovery_time_of_day IS NOT NULL AND discovery_timezone IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f("ck_projects_discovery_weekly_requires_day_of_week"),
        "projects",
        "discovery_mode != 'WEEKLY_AT' OR discovery_day_of_week IS NOT NULL",
    )
    op.create_check_constraint(
        op.f("ck_projects_discovery_day_of_week_range"),
        "projects",
        "discovery_day_of_week IS NULL OR (discovery_day_of_week >= 0 AND discovery_day_of_week <= 6)",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_projects_discovery_day_of_week_range"), "projects", type_="check")
    op.drop_constraint(
        op.f("ck_projects_discovery_weekly_requires_day_of_week"), "projects", type_="check"
    )
    op.drop_constraint(
        op.f("ck_projects_discovery_daily_weekly_requires_time_and_tz"), "projects", type_="check"
    )
    op.drop_constraint(
        op.f("ck_projects_discovery_interval_hours_min_1"), "projects", type_="check"
    )
    op.drop_constraint(
        op.f("ck_projects_discovery_every_n_hours_requires_interval"), "projects", type_="check"
    )
    op.drop_constraint(
        op.f("ck_projects_discovery_requires_github_repo"), "projects", type_="check"
    )
    op.drop_column("projects", "discovery_pr_corpus_watermark_at")
    op.drop_column("projects", "discovery_next_run_at")
    op.drop_column("projects", "discovery_timezone")
    op.drop_column("projects", "discovery_day_of_week")
    op.drop_column("projects", "discovery_time_of_day")
    op.drop_column("projects", "discovery_interval_hours")
    op.drop_column("projects", "discovery_mode")
    sa.Enum(name="discovery_mode").drop(op.get_bind(), checkfirst=True)

    op.drop_index("uq_ingestion_jobs_one_running_per_project", table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")
    sa.Enum(name="ingestion_job_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="ingestion_job_trigger_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="ingestion_job_type").drop(op.get_bind(), checkfirst=True)

    op.drop_column("rule_candidates", "evidence_created_at")
    op.drop_column("rule_candidates", "original_author")
    op.drop_column("rule_candidates", "comment_snippet_snapshot")
    op.drop_column("rule_candidates", "pr_number")
    op.drop_column("rule_candidates", "evidence_unit_id")
    op.drop_column("rule_candidates", "embedding_model_version")
    op.drop_column("rule_candidates", "embedding")

    op.drop_constraint(
        op.f("uq_raw_pr_comments_repo_type_github_id"), "raw_pr_comments", type_="unique"
    )
    op.drop_column("raw_pr_comments", "mining_processed_at")
    op.drop_column("raw_pr_comments", "github_id")
