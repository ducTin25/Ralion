"""hop nhat hai head: TV4 de xuat E va plan task citations

Merge thuan tuy, khong co thao tac schema nao. Hai nhanh sua hai vung khac han nhau
(users/policy_acknowledgements vs plan_task_citations) nen khong co xung dot that.

Revision ID: a1b2c3d4e5f7
Revises: e4f5a6b7c8d9, f3194e228632
Create Date: 2026-08-21

"""

from typing import Sequence, Union

revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, Sequence[str], None] = ("e4f5a6b7c8d9", "f3194e228632")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
