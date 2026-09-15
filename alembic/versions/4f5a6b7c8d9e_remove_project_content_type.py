"""Replace PROJECT content-type dispatch with structural chunking.

Revision ID: 4f5a6b7c8d9e
Revises: 3e4f5a6b7c8d
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "4f5a6b7c8d9e"
down_revision: str | Sequence[str] | None = "3e4f5a6b7c8d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_knowledge_documents_content_type_enum"), "knowledge_documents", type_="check")
    op.drop_constraint(op.f("ck_knowledge_documents_knowledge_domain_category"), "knowledge_documents", type_="check")
    op.create_check_constraint(
        op.f("ck_knowledge_documents_knowledge_domain_category"),
        "knowledge_documents",
        "(knowledge_domain = 'PROJECT' AND project_id IS NOT NULL "
        "AND document_category IS NOT NULL AND policy_category IS NULL) "
        "OR (knowledge_domain = 'POLICY' AND project_id IS NULL "
        "AND policy_category IS NOT NULL AND document_category IS NULL "
        "AND source_key IS NOT NULL)",
    )
    op.drop_column("knowledge_documents", "content_type")


def downgrade() -> None:
    op.add_column("knowledge_documents", sa.Column("content_type", sa.String(), nullable=True))
    op.execute("UPDATE knowledge_documents SET content_type = 'REPO_DOC' WHERE knowledge_domain = 'PROJECT'")
    op.drop_constraint(op.f("ck_knowledge_documents_knowledge_domain_category"), "knowledge_documents", type_="check")
    op.create_check_constraint(
        op.f("ck_knowledge_documents_knowledge_domain_category"),
        "knowledge_documents",
        "(knowledge_domain = 'PROJECT' AND project_id IS NOT NULL "
        "AND document_category IS NOT NULL AND content_type IS NOT NULL "
        "AND policy_category IS NULL) "
        "OR (knowledge_domain = 'POLICY' AND project_id IS NULL "
        "AND policy_category IS NOT NULL AND document_category IS NULL "
        "AND content_type IS NULL AND source_key IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f("ck_knowledge_documents_content_type_enum"),
        "knowledge_documents",
        "content_type IS NULL OR content_type IN "
        "('ADR', 'PRODUCT_DOC', 'CONTRIB_GUIDE', 'REPO_DOC', 'CODE_DOC')",
    )
