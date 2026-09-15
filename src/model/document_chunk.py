from pgvector.sqlalchemy import VECTOR
from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("version_id", "chunk_index"),
        Index(
            "ix_document_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    chunk_id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("document_versions.version_id"), nullable=False)
    heading: Mapped[str | None] = mapped_column(nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Deterministic identifiers extracted at ingest (policy IDs, RFCs, symbols).
    # The ParadeDB BM25 index gives this field literal-normalized semantics.
    lexical_identifiers: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Separate physical field: ParadeDB permits distinct analyzers per field,
    # but does not permit the same attribute twice in one index definition.
    lexical_technical: Mapped[str] = mapped_column(Text, nullable=False, default="")
    section_path: Mapped[str | None] = mapped_column(nullable=True)
    anchor: Mapped[str | None] = mapped_column(nullable=True)
    content_hash: Mapped[str] = mapped_column(nullable=False)
    embedding_model_version: Mapped[str] = mapped_column(nullable=False)
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    token_count: Mapped[int] = mapped_column(nullable=False)
    # Embedding được lưu cùng metadata trong PostgreSQL/pgvector.
    # Canonical embedding contract: pinned BAAI/bge-m3, normalized, 1024 dimensions.
    embedding: Mapped[list[float] | None] = mapped_column(VECTOR(1024), nullable=True)
