"""merge nhanh TV4 (password_hash) vao nhanh chinh

Migration `d4e5f6a7b8c9_add_user_password_hash` tach ra tu `a1b2c3d4e5f6` va khong duoc
noi lai vao nhanh chinh sau khi merge develop. Hau qua: repo co 2 head, `alembic upgrade
head` bao "Multiple head revisions are present" va khong the them migration moi.

File nay chi gop hai nhanh, khong doi schema.

Revision ID: b1c2d3e4f5a6
Revises: 781ee9706e41, d4e5f6a7b8c9
Create Date: 2026-08-15

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = ("781ee9706e41", "d4e5f6a7b8c9")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
