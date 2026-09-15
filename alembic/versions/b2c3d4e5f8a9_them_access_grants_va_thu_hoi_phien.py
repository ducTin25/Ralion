"""them bang access_grants va cot users.session_invalid_before

De xuat A (hang doi cap quyen) va de xuat D (thu hoi quyen khi roi du an).

session_invalid_before de nullable va khong backfill: NULL nghia la "khong thu hoi gi",
nen moi phien dang mo van song sau khi chay migration. Backfill bang now() se dang xuat
toan bo nguoi dung ngay giua ca lam viec ma khong duoc gi.

Revision ID: b2c3d4e5f8a9
Revises: a1b2c3d4e5f7
Create Date: 2026-08-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b2c3d4e5f8a9"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("session_invalid_before", sa.DateTime(), nullable=True))
    op.create_table(
        "access_grants",
        sa.Column("grant_id", sa.Integer(), primary_key=True),
        sa.Column("membership_id", sa.Integer(), nullable=False),
        sa.Column(
            "resource_type",
            sa.Enum(
                "REPOSITORY",
                "ISSUE_TRACKER",
                "CI_CD",
                "DATABASE",
                "SECRETS",
                "VPN",
                "OTHER",
                name="access_resource_type",
            ),
            nullable=False,
        ),
        sa.Column("resource_note", sa.String(), nullable=True),
        sa.Column("status", sa.Enum("REQUESTED", "GRANTED", "REVOKED", name="access_grant_status"), nullable=False),
        sa.Column("requested_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("granted_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("granted_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["membership_id"], ["project_memberships.membership_id"]),
        sa.ForeignKeyConstraint(["granted_by_admin_id"], ["users.user_id"]),
    )
    # Partial unique: chi chan trung khi ban ghi con SONG. Da REVOKED thi duoc phep trung
    # vi thu hoi roi cap lai la chuyen binh thuong, va lich su phai giu du.
    op.create_index(
        "uq_access_grant_live_resource",
        "access_grants",
        ["membership_id", "resource_type"],
        unique=True,
        postgresql_where=sa.text("status <> 'REVOKED'"),
        sqlite_where=sa.text("status <> 'REVOKED'"),
    )
    op.create_index("ix_access_grant_membership", "access_grants", ["membership_id"])
    op.create_index("ix_access_grant_status", "access_grants", ["status"])


def downgrade() -> None:
    op.drop_index("uq_access_grant_live_resource", table_name="access_grants")
    op.drop_index("ix_access_grant_status", table_name="access_grants")
    op.drop_index("ix_access_grant_membership", table_name="access_grants")
    op.drop_table("access_grants")
    op.execute("DROP TYPE IF EXISTS access_grant_status")
    op.execute("DROP TYPE IF EXISTS access_resource_type")
    op.drop_column("users", "session_invalid_before")
