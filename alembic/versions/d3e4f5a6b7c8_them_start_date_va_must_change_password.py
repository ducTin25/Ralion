"""them start_date va must_change_password vao bang users

Gop hai cot vao mot migration: ca hai deu them vao bang users, tach ra chi lam dai
lich su va tang nguy co dung head voi nguoi khac.

server_default cua must_change_password la false nen moi tai khoan DANG CO deu khong
bi chan — khong co rui ro khoa admin ra ngoai sau khi chay migration.

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-08-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("start_date", sa.Date(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
    op.drop_column("users", "start_date")
