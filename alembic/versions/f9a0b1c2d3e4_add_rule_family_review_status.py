"""F6 Phase 6 — HITL Review Queue workflow columns on rule_families.

Adds the PENDING/APPROVED/REJECTED status + reviewer attribution that
CLAUDE.md Phase 6 requires and that the Phase 5 migration (d7e8f9a0b1c2)
deliberately left out ("no status/workflow column ... the review-queue/
approval workflow isn't chốt yet" — see CHANGE_LOG.md). No ConfirmedRule
table: approving a family flips this status in place, per the explicit
Phase 6 scope cut (no versioning for approved rules).

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
Create Date: 2026-08-20

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f9a0b1c2d3e4"
down_revision: str | Sequence[str] | None = "e8f9a0b1c2d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # op.add_column (unlike op.create_table) does not auto-issue CREATE TYPE for an inline
    # Postgres enum column — must create the type explicitly first.
    status_enum = sa.Enum("PENDING", "APPROVED", "REJECTED", name="rule_family_status")
    status_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "rule_families",
        sa.Column("status", status_enum, nullable=False, server_default="PENDING"),
    )
    op.add_column("rule_families", sa.Column("approved_by", sa.Integer(), nullable=True))
    op.add_column("rule_families", sa.Column("approved_at", sa.DateTime(), nullable=True))
    op.add_column("rule_families", sa.Column("rejected_by", sa.Integer(), nullable=True))
    op.add_column("rule_families", sa.Column("rejected_at", sa.DateTime(), nullable=True))
    op.create_foreign_key(
        op.f("fk_rule_families_approved_by_users"),
        "rule_families",
        "users",
        ["approved_by"],
        ["user_id"],
    )
    op.create_foreign_key(
        op.f("fk_rule_families_rejected_by_users"),
        "rule_families",
        "users",
        ["rejected_by"],
        ["user_id"],
    )
    op.create_check_constraint(
        op.f("ck_rule_families_approved_requires_approved_at"),
        "rule_families",
        "status != 'APPROVED' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f("ck_rule_families_rejected_requires_rejected_at"),
        "rule_families",
        "status != 'REJECTED' OR (rejected_by IS NOT NULL AND rejected_at IS NOT NULL)",
    )
    # Review Queue's list-PENDING query filters on this column exclusively.
    op.create_index("ix_rule_families_status", "rule_families", ["status"])


def downgrade() -> None:
    op.drop_index("ix_rule_families_status", table_name="rule_families")
    op.drop_constraint(op.f("ck_rule_families_rejected_requires_rejected_at"), "rule_families", type_="check")
    op.drop_constraint(op.f("ck_rule_families_approved_requires_approved_at"), "rule_families", type_="check")
    op.drop_constraint(op.f("fk_rule_families_rejected_by_users"), "rule_families", type_="foreignkey")
    op.drop_constraint(op.f("fk_rule_families_approved_by_users"), "rule_families", type_="foreignkey")
    op.drop_column("rule_families", "rejected_at")
    op.drop_column("rule_families", "rejected_by")
    op.drop_column("rule_families", "approved_at")
    op.drop_column("rule_families", "approved_by")
    op.drop_column("rule_families", "status")
    sa.Enum(name="rule_family_status").drop(op.get_bind(), checkfirst=True)
