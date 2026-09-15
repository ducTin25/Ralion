"""merge nhanh TV4 (policy ack + user fields) voi nhanh develop

Nhanh develop da tu gop head d4e5f6a7b8c9 bang 1b2c3d4e5f6a, song song voi ban gop
b1c2d3e4f5a6 cua TV4. Hai duong di deu hop le, chi can noi lai o day.

File nay chi gop nhanh, khong doi schema.

Revision ID: e4f5a6b7c8d9
Revises: 5a6b7c8d9e0f, d3e4f5a6b7c8
Create Date: 2026-08-15

"""

from typing import Sequence, Union

revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, Sequence[str], None] = ("5a6b7c8d9e0f", "d3e4f5a6b7c8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
