"""Restrict document versions to the persisted retrieval lifecycle.

Revision ID: 0c1d2e3f4a5b
Revises: 781ee9706e41
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0c1d2e3f4a5b"
down_revision: str | Sequence[str] | None = "781ee9706e41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Test/legacy PROCESSING and FAILED rows must be removed before this migration.
    # Refuse to silently reclassify them as ARCHIVED because that loses failure meaning.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM document_versions
                WHERE status::text IN ('PROCESSING', 'FAILED')
            ) THEN
                RAISE EXCEPTION
                    'Remove test/legacy PROCESSING or FAILED document_versions before migration';
            END IF;
        END;
        $$;
        """
    )
    # The partial index predicate is typed against the old enum, so PostgreSQL
    # cannot alter the column while that index exists.
    op.drop_index("uq_document_versions_one_active_per_document", table_name="document_versions")
    op.execute("ALTER TYPE version_status RENAME TO version_status_legacy")
    op.execute("CREATE TYPE version_status AS ENUM ('ACTIVE', 'ARCHIVED')")
    op.execute(
        "ALTER TABLE document_versions ALTER COLUMN status TYPE version_status "
        "USING status::text::version_status"
    )
    op.execute("DROP TYPE version_status_legacy")
    op.create_index(
        "uq_document_versions_one_active_per_document",
        "document_versions",
        ["document_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.add_column("knowledge_documents", sa.Column("last_ingest_error", sa.Text(), nullable=True))
    op.add_column("knowledge_documents", sa.Column("last_ingest_error_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_one_active_document_version()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            v_document_id integer;
            v_active_count integer;
        BEGIN
            v_document_id := CASE WHEN TG_OP = 'DELETE' THEN OLD.document_id ELSE NEW.document_id END;
            IF NOT EXISTS (SELECT 1 FROM knowledge_documents WHERE document_id = v_document_id) THEN
                RETURN NULL;
            END IF;
            SELECT count(*) INTO v_active_count
            FROM document_versions
            WHERE document_id = v_document_id AND status = 'ACTIVE';
            IF v_active_count <> 1 THEN
                RAISE EXCEPTION 'Document % must have exactly one ACTIVE version, found %',
                    v_document_id, v_active_count;
            END IF;
            RETURN NULL;
        END;
        $$;
        """
    )


def downgrade() -> None:
    op.drop_column("knowledge_documents", "last_ingest_error_at")
    op.drop_column("knowledge_documents", "last_ingest_error")
    op.drop_index("uq_document_versions_one_active_per_document", table_name="document_versions")
    op.execute("ALTER TYPE version_status RENAME TO version_status_active_archived")
    op.execute("CREATE TYPE version_status AS ENUM ('PROCESSING', 'ACTIVE', 'FAILED', 'ARCHIVED')")
    op.execute(
        "ALTER TABLE document_versions ALTER COLUMN status TYPE version_status "
        "USING status::text::version_status"
    )
    op.execute("DROP TYPE version_status_active_archived")
    op.create_index(
        "uq_document_versions_one_active_per_document",
        "document_versions",
        ["document_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_one_active_document_version()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            v_document_id integer;
            v_active_count integer;
        BEGIN
            v_document_id := CASE WHEN TG_OP = 'DELETE' THEN OLD.document_id ELSE NEW.document_id END;
            IF NOT EXISTS (SELECT 1 FROM knowledge_documents WHERE document_id = v_document_id) THEN
                RETURN NULL;
            END IF;
            SELECT count(*) INTO v_active_count
            FROM document_versions
            WHERE document_id = v_document_id AND status = 'ACTIVE';
            IF v_active_count > 1 THEN
                RAISE EXCEPTION 'Document % must have at most one ACTIVE version, found %',
                    v_document_id, v_active_count;
            END IF;
            RETURN NULL;
        END;
        $$;
        """
    )
