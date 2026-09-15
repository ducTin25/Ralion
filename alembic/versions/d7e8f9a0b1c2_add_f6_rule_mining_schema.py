"""F6 rule mining schema — rule_families, rule_candidates, rule_evidences.

Lays down exactly the storage F6_RULE_MINING_SPEC.md §5 requires for eligibility
computation and evidence snapshotting: nothing beyond that (no status/workflow
column, no Rule/ConfirmedRule table, no project/repo scoping — §4.6 scopes this
MVP to a single fixed repo, and the review-queue/approval workflow isn't chốt yet).
See CHANGE_LOG.md for the reasoning.

Revision ID: d7e8f9a0b1c2
Revises: b2c3d4e5f6a7
Create Date: 2026-08-20

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d7e8f9a0b1c2"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rule_families",
        sa.Column("rule_family_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("distinct_reviewer_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("rule_family_id", name=op.f("pk_rule_families")),
    )

    op.create_table(
        "rule_candidates",
        sa.Column("rule_candidate_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "evidence_type",
            sa.Enum(
                "REUSABLE_CORRECTION",
                "CONVENTION",
                "LOCAL_CORRECTION",
                "RATIONALE",
                "QUESTION_DISCUSSION",
                "NOISE_OTHER",
                name="rule_evidence_type",
            ),
            nullable=False,
        ),
        sa.Column("reuse_scope", sa.Integer(), nullable=False),
        sa.Column("rule_text_draft", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("rule_candidate_id", name=op.f("pk_rule_candidates")),
    )

    op.create_table(
        "rule_evidences",
        sa.Column("rule_evidence_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rule_candidate_id", sa.Integer(), nullable=False),
        sa.Column("rule_family_id", sa.Integer(), nullable=False),
        sa.Column("evidence_unit_id", sa.String(), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("comment_snippet_snapshot", sa.Text(), nullable=False),
        sa.Column("original_author", sa.String(), nullable=False),
        sa.Column("evidence_created_at", sa.DateTime(), nullable=False),
        sa.Column("cluster_edge_cosine_similarity", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["rule_candidate_id"],
            ["rule_candidates.rule_candidate_id"],
            name=op.f("fk_rule_evidences_rule_candidate_id_rule_candidates"),
        ),
        sa.ForeignKeyConstraint(
            ["rule_family_id"],
            ["rule_families.rule_family_id"],
            name=op.f("fk_rule_evidences_rule_family_id_rule_families"),
        ),
        sa.PrimaryKeyConstraint("rule_evidence_id", name=op.f("pk_rule_evidences")),
        sa.UniqueConstraint("evidence_unit_id", name="uq_rule_evidences_evidence_unit_id"),
    )
    # Supports the eligibility query's GROUP BY rule_family_id and the join on
    # rule_candidate_id (F6_RULE_MINING_SPEC.md §5.3).
    op.create_index("ix_rule_evidences_rule_family_id", "rule_evidences", ["rule_family_id"])
    op.create_index("ix_rule_evidences_rule_candidate_id", "rule_evidences", ["rule_candidate_id"])


def downgrade() -> None:
    op.drop_index("ix_rule_evidences_rule_candidate_id", table_name="rule_evidences")
    op.drop_index("ix_rule_evidences_rule_family_id", table_name="rule_evidences")
    op.drop_table("rule_evidences")
    op.drop_table("rule_candidates")
    op.drop_table("rule_families")
    sa.Enum(name="rule_evidence_type").drop(op.get_bind(), checkfirst=True)
