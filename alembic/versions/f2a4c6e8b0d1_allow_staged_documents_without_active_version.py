"""Allow staged project documents to exist before their first active version.

Revision ID: f2a4c6e8b0d1
Revises: 02ad607356fe, d1e2f3a4b5c6
Create Date: 2026-08-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f2a4c6e8b0d1"
down_revision: str | Sequence[str] | None = ("02ad607356fe", "d1e2f3a4b5c6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Keep the at-most-one invariant while permitting zero ready versions.

    PROJECT ingestion deliberately persists AMBIGUOUS document metadata before
    category review.  Those rows have no version or chunks until a PM confirms
    the category and a later GitHub sync ingests the pinned source.  The partial
    unique index ``uq_document_versions_one_active_per_document`` already
    enforces the useful invariant: a document can never have more than one
    ACTIVE version.
    """

    op.execute("DROP TRIGGER IF EXISTS trg_knowledge_documents_one_active ON knowledge_documents")
    op.execute("DROP TRIGGER IF EXISTS trg_document_versions_one_active ON document_versions")
    op.execute("DROP FUNCTION IF EXISTS enforce_one_active_document_version()")


def downgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION enforce_one_active_document_version()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            v_document_id integer;
            v_active_count integer;
        BEGIN
            v_document_id := CASE
                WHEN TG_OP = 'DELETE' THEN OLD.document_id
                ELSE NEW.document_id
            END;
            IF NOT EXISTS (
                SELECT 1 FROM knowledge_documents WHERE document_id = v_document_id
            ) THEN
                RETURN NULL;
            END IF;
            SELECT count(*) INTO v_active_count
            FROM document_versions
            WHERE document_id = v_document_id AND status = 'ACTIVE';
            IF v_active_count <> 1 THEN
                RAISE EXCEPTION
                    'Document % must have exactly one ACTIVE version, found %',
                    v_document_id, v_active_count;
            END IF;
            RETURN NULL;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_document_versions_one_active
        AFTER INSERT OR UPDATE OR DELETE ON document_versions
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION enforce_one_active_document_version();
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_knowledge_documents_one_active
        AFTER INSERT OR UPDATE ON knowledge_documents
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION enforce_one_active_document_version();
        """
    )
