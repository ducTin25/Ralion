"""plan_task_sources: tro trich dan toi dung chunk, khong chi toi ca file

Trước đây `PlanTaskSource` chỉ lưu `version_id` + `citation_note` (chuỗi heading tự do), nên khi PM
bấm vào trích dẫn thì chỉ mở được NGUYÊN file rồi tự dò — đúng vấn đề "nguồn tài liệu dồn 1 đống"
PM nêu khi test thật.

Từ khi tài liệu PROJECT đi qua lõi ingest chung (`ingest_or_update`), mỗi `DocumentChunk` đã có
`anchor`/`section_path` thật, nên trích dẫn trỏ thẳng `chunk_id` là mở đúng đoạn được. Cột để
nullable vì:
  - Plan sinh trước migration này chỉ có `version_id`.
  - Nhánh baseline / "có tài liệu nhưng không tìm được đoạn khớp" vẫn gắn tài liệu làm nguồn tham
    chiếu mà không trích đoạn cụ thể nào.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c0
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | Sequence[str] | None = "d4e5f6a7b8c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("plan_task_sources", sa.Column("chunk_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_plan_task_sources_chunk_id_document_chunks"),
        "plan_task_sources",
        "document_chunks",
        ["chunk_id"],
        ["chunk_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f("fk_plan_task_sources_chunk_id_document_chunks"), "plan_task_sources", type_="foreignkey"
    )
    op.drop_column("plan_task_sources", "chunk_id")
