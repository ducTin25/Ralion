"""add architecture task category

Revision ID: 766d77208fd9
Revises: 87d27e78a497
Create Date: 2026-08-12 22:22:40.317667

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '766d77208fd9'
down_revision: str | Sequence[str] | None = '87d27e78a497'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # PG16 hỗ trợ ALTER TYPE ... ADD VALUE trong transaction — không cần kiểu recreate-enum
    # phức tạp như migration 087bc97c54cf cũ (chỉ cần khi đổi/xoá value, không phải khi thêm mới).
    op.execute("ALTER TYPE task_category ADD VALUE 'ARCHITECTURE'")


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres không hỗ trợ xoá 1 value khỏi enum type trực tiếp (phải recreate cả type, rủi ro
    # cao hơn giá trị mang lại cho 1 lần downgrade) — chấp nhận no-op, đúng hạn chế đã biết.
    pass
