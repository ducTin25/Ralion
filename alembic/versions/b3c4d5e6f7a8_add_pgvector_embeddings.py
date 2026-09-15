"""Store document embeddings in PostgreSQL using pgvector.

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import VECTOR

from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("document_chunks", sa.Column("embedding", VECTOR(1536), nullable=True))
    op.drop_column("document_chunks", "vector_id")
    op.create_index(
        "ix_document_chunks_embedding_hnsw",
        "document_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_embedding_hnsw", table_name="document_chunks")
    op.add_column("document_chunks", sa.Column("vector_id", sa.String(), nullable=True))
    op.execute(
        "UPDATE document_chunks "
        "SET vector_id = 'legacy-' || chunk_id::text "
        "WHERE vector_id IS NULL"
    )
    op.alter_column("document_chunks", "vector_id", nullable=False)
    op.create_unique_constraint(
        "uq_document_chunks_vector_id", "document_chunks", ["vector_id"]
    )
    op.drop_column("document_chunks", "embedding")
