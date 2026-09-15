"""hop nhat nhanh access_grants voi develop (f6 rule mining + chatbot)

Merge thuan tuy, khong co thao tac schema nao. Hai nhanh dung vao hai vung khac han:
access_grants/users.session_invalid_before ben nay, rule_* va chat_* ben kia.

Revision ID: c3d4e5f9a0b1
Revises: b2c3d4e5f8a9, 02ad607356fe
Create Date: 2026-08-22
"""

from collections.abc import Sequence

revision: str = "c3d4e5f9a0b1"
down_revision: str | Sequence[str] | None = ("b2c3d4e5f8a9", "02ad607356fe")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
