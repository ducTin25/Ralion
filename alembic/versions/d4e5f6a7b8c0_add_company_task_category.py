"""add COMPANY task category

Lộ trình onboarding chuẩn gồm 1 phần công ty ("Tìm hiểu công ty" — đọc chính sách chung, domain
POLICY) + 5 phần dự án. Trước đây khối "Tìm hiểu công ty" chỉ là UI ở trang Master Template đọc
thẳng danh sách `KnowledgeDocument` POLICY, KHÔNG phải `TemplateTask` thật — nên nó không bao giờ
chảy vào `generate_candidate_plan`, và plan sinh ra thiếu hẳn phần công ty.

`TaskCategory.COMPANY` biến nhóm đó thành task thật, đi qua đúng pipeline sinh plan như 5 nhóm còn
lại. `TASK_CATEGORY_POLICY_MAP[COMPANY] = None` (steps.py) cho nhóm này đọc toàn bộ policy;
`TASK_CATEGORY_DOCUMENT_MAP` cố tình KHÔNG có COMPANY vì nhóm này không đọc tài liệu riêng của dự án.

Revision ID: d4e5f6a7b8c0
Revises: c3d4e5f6a7b8
Create Date: 2026-08-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "d4e5f6a7b8c0"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # PG16 hỗ trợ ALTER TYPE ... ADD VALUE trong transaction — cùng cách migration
    # 766d77208fd9_add_architecture_task_category.py đã làm.
    op.execute("ALTER TYPE task_category ADD VALUE IF NOT EXISTS 'COMPANY'")


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres không hỗ trợ xoá 1 value khỏi enum type trực tiếp (phải recreate cả type, rủi ro cao
    # hơn giá trị mang lại cho 1 lần downgrade) — chấp nhận no-op, đúng hạn chế đã biết.
    pass
