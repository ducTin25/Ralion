"""backfill source_key cho tai lieu PROJECT tao truoc khi dung lo i ingest chung

Luồng "PM tải tay / quét thư mục" giờ gọi chung lõi
`modules/knowledge/ingestion/versioning.ingest_or_update()` với luồng đồng bộ GitHub. Lõi này nhận
ra "cùng 1 tài liệu" bằng `source_key`, trong khi tài liệu PROJECT tạo bằng đường cũ có
`source_key = NULL` — nếu không backfill, PM tải lại đúng file cũ sẽ ra 1 document TRÙNG thay vì
version mới của document đang có.

Công thức phải khớp tuyệt đối với `knowledge_document_service.build_upload_source_key()`:
    upload:{project_id}:{document_category}:{title}

Index `uq_knowledge_documents_domain_source_key` là UNIQUE (knowledge_domain, source_key) — bộ ba
(project, category, title) vốn đã là duy nhất theo cách `_find_or_create_document` cũ tìm tài liệu,
nên backfill không thể đụng unique. Tài liệu POLICY không bị ảnh hưởng (đã có `source_key` riêng từ
`document_code`, và mệnh đề WHERE dưới đây chỉ lấy domain PROJECT).

Revision ID: c3d4e5f6a7b8
Revises: b1c2d3e4f5a6
Create Date: 2026-08-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b7d2f4a19c53"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        UPDATE knowledge_documents
        SET source_key = 'upload:' || project_id || ':' || document_category || ':' || title
        WHERE knowledge_domain = 'PROJECT' AND source_key IS NULL
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Chỉ xoá đúng những giá trị do migration này sinh ra (tiền tố 'upload:'), giữ nguyên
    # `source_key` của tài liệu đến từ GitHub sync.
    op.execute(
        """
        UPDATE knowledge_documents
        SET source_key = NULL
        WHERE knowledge_domain = 'PROJECT' AND source_key LIKE 'upload:%'
        """
    )
