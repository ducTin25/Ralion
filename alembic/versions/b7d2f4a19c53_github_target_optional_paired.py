"""projects: github_repo/default_branch optional nhung phai di theo cap

Migration `3e4f5a6b7c8d` (nhánh Backstage Sub-flow A) đặt `projects.github_repo`/`default_branch`
NOT NULL và backfill placeholder cho project CŨ, nhưng API tạo project của PM
(`POST /api/v1/projects/pm`) không gửi 2 field này — nên mọi project TẠO MỚI đều vi phạm NOT NULL
(bị `IntegrityError` bắt nhầm thành 409 "Project key already exists").

Quyết định: giữ nguyên 2 cột và hướng đồng bộ GitHub, chỉ nới thành optional — PM tạo project rồi
tự quét thư mục/tải tài liệu tay là luồng chính hiện tại, không bắt buộc gắn repo. CHECK constraint
ép 2 cột đi theo CẶP: nửa vời (có repo mà thiếu branch) sẽ làm `github_sync_worker.sync_docs` không
biết lấy nhánh nào để đọc.

`github_sync_worker.resolve_github_token()` đã có guard tương ứng: project chưa cấu hình GitHub thì
báo lỗi rõ ràng thay vì crash `.partition()` trên None.

Revision ID: b7d2f4a19c53
Revises: 97a9cd973ca6
Create Date: 2026-08-15

LƯU Ý: ID cũ của migration này là `b1c2d3e4f5a6` — TRÙNG với
`b1c2d3e4f5a6_merge_tv4_password_hash_vao_nhanh_chinh.py` bên `develop` (2 file khác nhau cùng khai
1 revision). Alembic khi đó cảnh báo "Revision b1c2d3e4f5a6 is present more than once" và
`upgrade head` không chạy được. Đã đổi sang `b7d2f4a19c53`; migration phụ thuộc
(`c3d4e5f6a7b8_backfill_upload_source_key.py`) cập nhật `down_revision` theo.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7d2f4a19c53"
down_revision: str | Sequence[str] | None = "97a9cd973ca6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("projects", "github_repo", existing_type=sa.String(), nullable=True)
    op.alter_column("projects", "default_branch", existing_type=sa.String(), nullable=True)
    # Tên truyền vào là phần đuôi: naming convention trong alembic/env.py tự thêm tiền tố
    # "ck_projects_" (truyền cả tên đầy đủ sẽ bị lặp prefix).
    op.create_check_constraint(
        "github_target_paired",
        "projects",
        "(github_repo IS NULL AND default_branch IS NULL) OR "
        "(github_repo IS NOT NULL AND default_branch IS NOT NULL)",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f("ck_projects_github_target_paired"), "projects", type_="check")
    # Project tạo sau migration này có thể chưa cấu hình GitHub — điền lại placeholder giống
    # `3e4f5a6b7c8d` để cột trở lại NOT NULL được, giữ đúng cách nhánh gốc xử lý dữ liệu cũ.
    op.execute(
        "UPDATE projects SET github_repo = 'manh/group-project', default_branch = 'master' "
        "WHERE github_repo IS NULL OR default_branch IS NULL"
    )
    op.alter_column("projects", "default_branch", existing_type=sa.String(), nullable=False)
    op.alter_column("projects", "github_repo", existing_type=sa.String(), nullable=False)
