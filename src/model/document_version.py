from datetime import date, datetime

from sqlalchemy import Enum, ForeignKey, Index, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base
from src.model.enums import VersionStatus


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "version_no",
            "embedding_model_version",
            name="uq_document_versions_document_model_version",
        ),
        UniqueConstraint("document_id", "revision_no", name="uq_document_versions_document_revision"),
        Index(
            "uq_document_versions_one_active_per_document",
            "document_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            # Thiếu `sqlite_where` thì SQLite bỏ qua điều kiện và dựng unique index trên
            # riêng document_id — tức là test in-memory chỉ cho phép MỘT version mỗi tài
            # liệu, chặt hơn hẳn production. Hệ quả: không viết được test nào cho luồng
            # lên phiên bản mới, đúng thứ cần kiểm nhất.
            sqlite_where=text("status = 'ACTIVE'"),
        ),
    )

    version_id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("knowledge_documents.document_id"), nullable=False)
    # Policy versions are labels from the source document (for example 3.2),
    # not an application-generated ordinal.
    version_no: Mapped[str] = mapped_column(nullable=False)
    embedding_model_version: Mapped[str] = mapped_column(nullable=False)
    # Internal monotonic ordering; never use source labels such as "3.2" for ordering.
    revision_no: Mapped[int] = mapped_column(nullable=False)
    storage_uri: Mapped[str] = mapped_column(nullable=False)
    checksum: Mapped[str] = mapped_column(nullable=False)
    # Git commit SHA for PROJECT versions. POLICY and unverifiable legacy rows use NULL.
    source_ref: Mapped[str | None] = mapped_column(nullable=True)
    content_status: Mapped[str | None] = mapped_column(nullable=True)
    effective_date: Mapped[date | None] = mapped_column(nullable=True)
    status: Mapped[VersionStatus] = mapped_column(
        Enum(VersionStatus, name="version_status"), nullable=False, default=VersionStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
