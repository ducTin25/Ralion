"""them bang plan_task_citations (nhieu trich dan tren 1 tai lieu)

Vì sao thêm bảng mới thay vì nới `plan_task_sources`:
- `plan_task_sources` mang ngữ nghĩa "1 dòng = 1 tài liệu task cần đọc", có
  `UniqueConstraint(plan_task_id, version_id)` ép đúng điều đó, và ĐANG được Member Portal
  (`member_onboarding_service._task_sources()`, module của ducTin25) đọc trực tiếp.
- Nới constraint ở đó để cho phép nhiều đoạn/tài liệu sẽ khiến Member Portal hiện trùng lặp cùng 1
  file nhiều lần — hồi quy thật ở module người khác, buộc phải sửa kèm.
- Bảng con này giữ nguyên hợp đồng cũ (không ALTER bảng nào), phần chi tiết theo từng đoạn nằm riêng.

Migration thuần `create_table`: KHÔNG alter/drop bảng nào khác, không đụng `document_chunks` hay bất
kỳ bảng nào của luồng ingestion/retrieval/Chat.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | Sequence[str] | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "plan_task_citations",
        sa.Column("citation_id", sa.Integer(), nullable=False),
        sa.Column("plan_task_id", sa.Integer(), nullable=False),
        sa.Column("task_source_id", sa.Integer(), nullable=False),
        sa.Column("chunk_id", sa.Integer(), nullable=False),
        sa.Column("citation_order", sa.Integer(), nullable=False),
        sa.Column("citation_note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["plan_task_id"],
            ["plan_tasks.plan_task_id"],
            name=op.f("fk_plan_task_citations_plan_task_id_plan_tasks"),
        ),
        sa.ForeignKeyConstraint(
            ["task_source_id"],
            ["plan_task_sources.task_source_id"],
            name=op.f("fk_plan_task_citations_task_source_id_plan_task_sources"),
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["document_chunks.chunk_id"],
            name=op.f("fk_plan_task_citations_chunk_id_document_chunks"),
        ),
        sa.PrimaryKeyConstraint("citation_id", name=op.f("pk_plan_task_citations")),
        sa.UniqueConstraint(
            "task_source_id", "chunk_id", name=op.f("uq_plan_task_citations_task_source_id")
        ),
        sa.UniqueConstraint(
            "plan_task_id", "citation_order", name=op.f("uq_plan_task_citations_plan_task_id")
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("plan_task_citations")
