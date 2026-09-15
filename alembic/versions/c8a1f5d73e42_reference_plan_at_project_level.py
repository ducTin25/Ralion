"""onboarding plan: cho phep ban chuan cap project (khong gan ky su)

Phase 4 bổ sung khái niệm "lộ trình chuẩn của dự án": PM soạn 1 lần ở cấp PROJECT, mỗi kỹ sư khi
được cấp plan thì nhận 1 BẢN SAO để chạy tiến độ riêng. Trước đây `membership_id` NOT NULL nên mọi
plan buộc phải thuộc 1 kỹ sư — không có chỗ chứa bản chuẩn, và khi plan của kỹ sư đầu tiên được
duyệt thì PM mất luôn quyền sửa nội dung chuẩn (`plan_task_service.update_task` chặn khi khác DRAFT).

Sau migration này, `onboarding_plans` chứa 2 loại row phân biệt bằng cột nào có giá trị:
  - Bản chuẩn dự án : project_id NOT NULL, membership_id NULL  -> luôn DRAFT, PM sửa tự do
  - Plan của kỹ sư  : project_id NULL,     membership_id NOT NULL -> DRAFT -> APPROVED -> ...
CHECK `ck_onboarding_plans_owner` ép đúng 1 trong 2, không cho row lai.

Không đụng index `uq_onboarding_plans_one_open_per_membership` sẵn có: index đó không khai báo
NULLS NOT DISTINCT nên Postgres coi mỗi NULL là khác nhau — nhiều bản chuẩn (membership_id NULL)
không đụng nhau, ràng buộc "1 plan mở / kỹ sư" vẫn nguyên vẹn.

Dữ liệu cũ đều có `membership_id` (project_id để trống) nên tự thoả CHECK, không cần backfill.
`scripts/seed_dev_data.py` tạo plan theo đúng dạng đó nên cũng không phải sửa.

Xem docs/PM/Phase-4/plan-fix-reference-plan-reuse.md.

Revision ID: c8a1f5d73e42
Revises: 781ee9706e41
Create Date: 2026-08-14
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "c8a1f5d73e42"
down_revision: Union[str, None] = "781ee9706e41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("onboarding_plans", sa.Column("project_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_onboarding_plans_project_id_projects"),
        "onboarding_plans",
        "projects",
        ["project_id"],
        ["project_id"],
    )
    op.alter_column("onboarding_plans", "membership_id", existing_type=sa.Integer(), nullable=True)

    # Đúng 1 trong 2 cột sở hữu được set. Biểu thức boolean thuần (không dùng num_nonnulls() — hàm
    # riêng của Postgres) để cùng định nghĩa này còn tạo được bảng qua SQLite trong
    # tests/conftest.py (Base.metadata.create_all cho test nghiệp vụ), không phải bảo trì 2 bản.
    # Tên truyền vào là phần đuôi: naming convention trong alembic/env.py tự thêm tiền tố
    # "ck_onboarding_plans_" nên kết quả là "ck_onboarding_plans_owner" (truyền cả tên đầy đủ sẽ bị
    # lặp prefix thành ck_onboarding_plans_ck_onboarding_plans_owner).
    op.create_check_constraint(
        "owner",
        "onboarding_plans",
        "(project_id IS NOT NULL AND membership_id IS NULL) OR "
        "(project_id IS NULL AND membership_id IS NOT NULL)",
    )

    # Mỗi project chỉ có đúng 1 bản chuẩn. Partial index (WHERE membership_id IS NULL) để không ảnh
    # hưởng plan của kỹ sư — những row đó có project_id NULL nên vốn không nằm trong index này.
    op.create_index(
        "uq_onboarding_plans_one_reference_per_project",
        "onboarding_plans",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("membership_id IS NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Xoá bản chuẩn trước: chúng có membership_id NULL nên không thể tồn tại khi cột trở lại NOT NULL.
    op.execute("DELETE FROM plan_task_sources WHERE plan_task_id IN (SELECT plan_task_id FROM plan_tasks WHERE plan_id IN (SELECT plan_id FROM onboarding_plans WHERE membership_id IS NULL))")
    op.execute("DELETE FROM plan_tasks WHERE plan_id IN (SELECT plan_id FROM onboarding_plans WHERE membership_id IS NULL)")
    op.execute("DELETE FROM onboarding_plans WHERE membership_id IS NULL")

    op.drop_index("uq_onboarding_plans_one_reference_per_project", table_name="onboarding_plans")
    op.drop_constraint(op.f("ck_onboarding_plans_owner"), "onboarding_plans", type_="check")
    op.alter_column("onboarding_plans", "membership_id", existing_type=sa.Integer(), nullable=False)
    op.drop_constraint(
        op.f("fk_onboarding_plans_project_id_projects"), "onboarding_plans", type_="foreignkey"
    )
    op.drop_column("onboarding_plans", "project_id")
