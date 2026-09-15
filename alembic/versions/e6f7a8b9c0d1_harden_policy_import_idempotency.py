"""Add stable document identity and internal version revisions."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e6f7a8b9c0d1"
down_revision: str | Sequence[str] | None = "d5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("knowledge_documents", sa.Column("source_key", sa.String(), nullable=True))
    # Historical POLICY rows may not have an available document code. Give each
    # one a deterministic legacy key so the new POLICY identity invariant holds.
    op.execute(
        "UPDATE knowledge_documents "
        "SET source_key = 'legacy-policy-' || document_id::text "
        "WHERE knowledge_domain = 'POLICY' AND source_key IS NULL"
    )
    op.drop_constraint(
        op.f("ck_knowledge_documents_knowledge_domain_category"),
        "knowledge_documents",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_knowledge_documents_knowledge_domain_category"),
        "knowledge_documents",
        "(knowledge_domain = 'PROJECT' AND project_id IS NOT NULL "
        "AND document_category IS NOT NULL AND policy_category IS NULL) "
        "OR (knowledge_domain = 'POLICY' AND project_id IS NULL "
        "AND policy_category IS NOT NULL AND document_category IS NULL AND source_key IS NOT NULL)",
    )
    op.create_index(
        "uq_knowledge_documents_domain_source_key",
        "knowledge_documents",
        ["knowledge_domain", "source_key"],
        unique=True,
        postgresql_where=sa.text("source_key IS NOT NULL"),
    )

    op.add_column("document_versions", sa.Column("revision_no", sa.Integer(), nullable=True))
    op.execute(
        "WITH numbered AS ("
        " SELECT version_id, row_number() OVER (PARTITION BY document_id ORDER BY created_at, version_id) AS revision_no"
        " FROM document_versions"
        ") UPDATE document_versions AS version "
        "SET revision_no = numbered.revision_no FROM numbered WHERE version.version_id = numbered.version_id"
    )
    # The deferred active-version trigger observes the metadata update above.
    # Flush it before altering the same table in this migration transaction.
    op.execute("SET CONSTRAINTS ALL IMMEDIATE")
    op.alter_column("document_versions", "revision_no", nullable=False)
    op.create_unique_constraint("uq_document_versions_document_revision", "document_versions", ["document_id", "revision_no"])


def downgrade() -> None:
    op.drop_constraint("uq_document_versions_document_revision", "document_versions", type_="unique")
    op.drop_column("document_versions", "revision_no")
    op.drop_index("uq_knowledge_documents_domain_source_key", table_name="knowledge_documents")
    op.drop_constraint(
        op.f("ck_knowledge_documents_knowledge_domain_category"),
        "knowledge_documents",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_knowledge_documents_knowledge_domain_category"),
        "knowledge_documents",
        "(knowledge_domain = 'PROJECT' AND project_id IS NOT NULL "
        "AND document_category IS NOT NULL AND policy_category IS NULL) "
        "OR (knowledge_domain = 'POLICY' AND project_id IS NULL "
        "AND policy_category IS NOT NULL AND document_category IS NULL)",
    )
    op.drop_column("knowledge_documents", "source_key")
