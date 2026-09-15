from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base


class PlanTaskSource(Base):
    __tablename__ = "plan_task_sources"
    __table_args__ = (UniqueConstraint("plan_task_id", "version_id"),)

    task_source_id: Mapped[int] = mapped_column(primary_key=True)
    plan_task_id: Mapped[int] = mapped_column(ForeignKey("plan_tasks.plan_task_id"), nullable=False)
    version_id: Mapped[int] = mapped_column(ForeignKey("document_versions.version_id"), nullable=False)
    # Đoạn tài liệu ĐÚNG đã dùng để viết nội dung task. Trỏ tới chunk (không chỉ tới cả file) để
    # trích dẫn mở đúng chỗ: `DocumentChunk` có sẵn `anchor`/`section_path` từ lõi ingest chung.
    # Nullable vì plan sinh TRƯỚC khi có cột này chỉ lưu được `version_id`, và vì baseline/no-hit
    # gắn tài liệu làm nguồn tham chiếu mà không trích đoạn cụ thể nào.
    chunk_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_chunks.chunk_id"), nullable=True
    )
    citation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
