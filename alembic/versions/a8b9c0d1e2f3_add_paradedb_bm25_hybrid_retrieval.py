"""Add ParadeDB BM25 lexical retrieval for the shared RetrievalEngine."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a8b9c0d1e2f3"
down_revision: str | Sequence[str] | None = "f7a8b9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The ParadeDB PostgreSQL 16 image preinstalls pg_search and pgvector.
    # CREATE EXTENSION is deliberately in the migration: a standard pgvector
    # image must fail here instead of silently serving dense-only retrieval.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_search")
    op.add_column(
        "document_chunks",
        sa.Column("lexical_identifiers", sa.Text(), nullable=False, server_default=""),
    )
    op.alter_column("document_chunks", "lexical_identifiers", server_default=None)
    op.add_column(
        "document_chunks",
        sa.Column("lexical_technical", sa.Text(), nullable=False, server_default=""),
    )
    op.execute("UPDATE document_chunks SET lexical_technical = embedding_text")
    op.alter_column("document_chunks", "lexical_technical", server_default=None)

    op.create_table(
        "retrieval_index_configurations",
        sa.Column("configuration_key", sa.String(), primary_key=True),
        sa.Column("configuration_version", sa.String(), nullable=False),
        sa.Column("backend", sa.String(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("configuration_key = 'lexical'", name="ck_retrieval_index_configuration_key"),
    )
    op.execute(
        """
        INSERT INTO retrieval_index_configurations
            (configuration_key, configuration_version, backend, configuration, is_active)
        VALUES (
            'lexical', 'paradedb-bm25-v1', 'paradedb_pg_search',
            json_build_object(
                'main_tokenizer', 'unicode_words',
                'lowercase', true,
                'english_stemming', false,
                'ascii_folding', false,
                'technical_identifier_tokenizer', 'source_code',
                'exact_identifier_tokenizer', 'literal_normalized'
            ),
            true
        )
        """
    )
    # `unicode_words` is the multilingual content field; source_code indexes
    # symbols/camelCase/snake_case; literal_normalized preserves exact IDs.
    # `bm25` is the pg_search access-method alias provided by the pinned image.
    op.execute(
        """
        CREATE INDEX ix_document_chunks_lexical_bm25
        ON document_chunks USING bm25 (
            chunk_id,
            (embedding_text::pdb.unicode_words),
            (lexical_technical::pdb.source_code),
            (lexical_identifiers::pdb.literal_normalized)
        ) WITH (key_field = 'chunk_id', search_tokenizer = 'unicode_words')
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_lexical_bm25")
    op.drop_table("retrieval_index_configurations")
    op.drop_column("document_chunks", "lexical_technical")
    op.drop_column("document_chunks", "lexical_identifiers")
    # pg_search may serve other indexes; leave extension ownership to platform.
