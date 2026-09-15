"""Add reviewable PROJECT document category classification metadata.

Revision ID: 5a6b7c8d9e0f
Revises: 4f5a6b7c8d9e
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "5a6b7c8d9e0f"
down_revision: str | Sequence[str] | None = "4f5a6b7c8d9e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_documents",
        sa.Column("category_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("category_classification_status", sa.String(), nullable=True),
    )
    op.add_column("knowledge_documents", sa.Column("category_review_reason", sa.Text(), nullable=True))
    op.add_column(
        "knowledge_documents",
        sa.Column("document_category_classifier_version", sa.String(), nullable=True),
    )
    op.drop_constraint(
        op.f("ck_knowledge_documents_knowledge_domain_category"),
        "knowledge_documents",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_knowledge_documents_knowledge_domain_category"),
        "knowledge_documents",
        "(knowledge_domain = 'PROJECT' AND project_id IS NOT NULL AND policy_category IS NULL) "
        "OR (knowledge_domain = 'POLICY' AND project_id IS NULL "
        "AND policy_category IS NOT NULL AND document_category IS NULL AND source_key IS NOT NULL)",
    )
    op.execute(
        "UPDATE knowledge_documents SET category_confirmed = true, "
        "category_classification_status = 'CLASSIFIED' "
        "WHERE knowledge_domain = 'PROJECT' AND document_category IS NOT NULL"
    )
    op.create_check_constraint(
        op.f("ck_knowledge_documents_project_category_classification"),
        "knowledge_documents",
        "knowledge_domain = 'POLICY' OR "
        "(category_classification_status = 'CLASSIFIED' AND document_category IS NOT NULL "
        "AND category_confirmed = true) OR "
        "(category_classification_status = 'AMBIGUOUS' AND document_category IS NULL "
        "AND category_confirmed = false)",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_knowledge_documents_project_category_classification"),
        "knowledge_documents",
        type_="check",
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
    op.drop_column("knowledge_documents", "document_category_classifier_version")
    op.drop_column("knowledge_documents", "category_review_reason")
    op.drop_column("knowledge_documents", "category_classification_status")
    op.drop_column("knowledge_documents", "category_confirmed")
