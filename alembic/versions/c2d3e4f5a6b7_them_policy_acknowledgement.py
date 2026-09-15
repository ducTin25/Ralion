"""them bang policy_acknowledgements va co requires_acknowledgement

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-08-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "knowledge_documents",
        sa.Column(
            "requires_acknowledgement",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.create_table(
        "policy_acknowledgements",
        sa.Column("ack_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "acknowledged_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["version_id"], ["document_versions.version_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("ack_id"),
        # Chan ghi trung o tang DB, khong dua vao kiem tra trong code: hai request song
        # song deu doc thay "chua xac nhan" roi cung ghi.
        sa.UniqueConstraint("version_id", "user_id", name="uq_policy_ack_version_user"),
    )
    op.create_index("ix_policy_ack_version", "policy_acknowledgements", ["version_id"])
    op.create_index("ix_policy_ack_user", "policy_acknowledgements", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_policy_ack_user", table_name="policy_acknowledgements")
    op.drop_index("ix_policy_ack_version", table_name="policy_acknowledgements")
    op.drop_table("policy_acknowledgements")
    op.drop_column("knowledge_documents", "requires_acknowledgement")
