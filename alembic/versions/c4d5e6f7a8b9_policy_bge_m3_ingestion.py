"""Add policy ingestion metadata and migrate pgvector to BGE-M3 (1024d)."""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import VECTOR

from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: str | Sequence[str] | None = "b3c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("document_chunks", sa.Column("embedding_text", sa.Text(), nullable=True))
    op.add_column("document_chunks", sa.Column("section_path", sa.String(), nullable=True))
    op.add_column("document_chunks", sa.Column("content_hash", sa.String(), nullable=True))
    op.add_column("document_chunks", sa.Column("embedding_model_version", sa.String(), nullable=True))
    op.execute("UPDATE document_chunks SET embedding_text = content WHERE embedding_text IS NULL")
    op.execute("UPDATE document_chunks SET content_hash = md5(embedding_text) WHERE content_hash IS NULL")
    op.execute("UPDATE document_chunks SET embedding_model_version = 'legacy' WHERE embedding_model_version IS NULL")
    op.alter_column("document_chunks", "embedding_text", nullable=False)
    op.alter_column("document_chunks", "content_hash", nullable=False)
    op.alter_column("document_chunks", "embedding_model_version", nullable=False)

    # Existing 1536d vectors cannot be compared with BGE-M3 vectors. They are
    # intentionally invalidated; the next embedding run repopulates them.
    op.execute("UPDATE document_chunks SET embedding = NULL")
    op.drop_index("ix_document_chunks_embedding_hnsw", table_name="document_chunks")
    op.alter_column(
        "document_chunks",
        "embedding",
        type_=VECTOR(1024),
        existing_type=VECTOR(1536),
        postgresql_using="embedding::vector(1024)",
    )
    op.create_index(
        "ix_document_chunks_embedding_hnsw",
        "document_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_embedding_hnsw", table_name="document_chunks")
    op.execute("UPDATE document_chunks SET embedding = NULL")
    op.alter_column(
        "document_chunks",
        "embedding",
        type_=VECTOR(1536),
        existing_type=VECTOR(1024),
        postgresql_using="embedding::vector(1536)",
    )
    op.create_index(
        "ix_document_chunks_embedding_hnsw",
        "document_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.drop_column("document_chunks", "embedding_model_version")
    op.drop_column("document_chunks", "content_hash")
    op.drop_column("document_chunks", "section_path")
    op.drop_column("document_chunks", "embedding_text")
