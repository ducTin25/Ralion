from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base
from src.model.enums import DocumentCategory, DocumentDomain, DocumentStatus, PolicyCategory


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        CheckConstraint(
            "(knowledge_domain = 'PROJECT' AND project_id IS NOT NULL "
            "AND policy_category IS NULL) "
            "OR (knowledge_domain = 'POLICY' AND project_id IS NULL "
            "AND policy_category IS NOT NULL AND document_category IS NULL "
            "AND source_key IS NOT NULL)",
            name="knowledge_domain_category",
        ),
        CheckConstraint(
            "knowledge_domain = 'POLICY' OR "
            "(category_classification_status = 'CLASSIFIED' AND document_category IS NOT NULL "
            "AND category_confirmed = true) OR "
            "(category_classification_status = 'AMBIGUOUS' AND document_category IS NULL "
            "AND category_confirmed = false)",
            name="project_category_classification",
        ),
        # Split in two, not a single `(knowledge_domain, project_id, source_key)` index: POLICY
        # rows always have `project_id IS NULL` (see the CHECK above), and Postgres treats every
        # NULL as distinct in a unique index, so folding project_id into one shared index would
        # silently stop deduplicating POLICY documents. PROJECT rows always have a real
        # project_id under the same CHECK, so their own index is a real per-project constraint —
        # this is what makes the same GitHub repo/path safe to sync into two different projects.
        #
        # `sqlite_where` alongside `postgresql_where`: without it, SQLite (tests/conftest.py's
        # db_session) silently drops the WHERE clause and compiles each of these as an
        # unconditional unique index — the policy index would then also forbid two PROJECT rows
        # sharing a source_key, defeating the exact scenario this fix exists to allow. Same
        # reasoning as `IngestionJob.__table_args__`.
        Index(
            "uq_knowledge_documents_policy_source_key",
            "knowledge_domain",
            "source_key",
            unique=True,
            postgresql_where=text("knowledge_domain = 'POLICY' AND source_key IS NOT NULL"),
            sqlite_where=text("knowledge_domain = 'POLICY' AND source_key IS NOT NULL"),
        ),
        Index(
            "uq_knowledge_documents_project_source_key",
            "knowledge_domain",
            "project_id",
            "source_key",
            unique=True,
            postgresql_where=text("knowledge_domain = 'PROJECT' AND source_key IS NOT NULL"),
            sqlite_where=text("knowledge_domain = 'PROJECT' AND source_key IS NOT NULL"),
        ),
    )

    document_id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.project_id"), nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    knowledge_domain: Mapped[DocumentDomain] = mapped_column(
        Enum(DocumentDomain, name="document_domain"), nullable=False
    )
    # Chỉ 1 trong 2 field dưới có giá trị, tuỳ theo knowledge_domain (xem CHECK constraint).
    document_category: Mapped[DocumentCategory | None] = mapped_column(
        Enum(DocumentCategory, name="document_category"), nullable=True
    )
    # A deterministic winner is immediately confirmed.  Ambiguous PROJECT
    # documents keep this field NULL and are excluded from retrieval until HITL.
    # Manually created PROJECT documents are explicit human classifications;
    # ingestion overrides these defaults with AMBIGUOUS when needed.
    category_confirmed: Mapped[bool] = mapped_column(nullable=False, default=True)
    category_classification_status: Mapped[str | None] = mapped_column(
        String, nullable=True, default="CLASSIFIED"
    )
    category_review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_category_classifier_version: Mapped[str | None] = mapped_column(String, nullable=True)
    policy_category: Mapped[PolicyCategory | None] = mapped_column(
        Enum(PolicyCategory, name="policy_category"), nullable=True
    )
    # Stable identity from the source system (Policy uses normalized document_code).
    source_key: Mapped[str | None] = mapped_column(nullable=True)
    source_repo: Mapped[str | None] = mapped_column(String, nullable=True)
    language: Mapped[str | None] = mapped_column(String, nullable=True)
    decision_number: Mapped[str | None] = mapped_column(String, nullable=True)
    # Reserved for ADR provenance; Sub-flow A does not populate it yet.
    decision_source_pr_url: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(nullable=False)
    source_url: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status"), nullable=False, default=DocumentStatus.ACTIVE
    )
    # Chỉ tài liệu POLICY dùng cờ này: có bắt người dùng xác nhận đã đọc hay không.
    # Mặc định False có chủ ý — quy định bảo mật thì cần ký nhận, bảng phụ cấp ăn trưa
    # thì không. Mặc định True sẽ tạo danh sách "cần xác nhận" dài vô nghĩa ngay ngày
    # đầu, và người dùng học được thói quen bấm cho xong; cảnh báo ai cũng bỏ qua thì
    # tệ hơn không có cảnh báo.
    requires_acknowledgement: Mapped[bool] = mapped_column(
        nullable=False, server_default=text("false"), default=False
    )
    last_ingest_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_ingest_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )
