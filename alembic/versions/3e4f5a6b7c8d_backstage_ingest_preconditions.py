"""Add persistence prerequisites for Backstage Sub-flow A ingestion.

Revision ID: 3e4f5a6b7c8d
Revises: 1b2c3d4e5f6a
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "3e4f5a6b7c8d"
down_revision: str | Sequence[str] | None = "1b2c3d4e5f6a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Bootstrap-only values for existing demo projects. They make the new target
    # fields valid without claiming that legacy Cloudinary documents originated
    # from Backstage. Project admins must replace them before a real sync.
    op.add_column("projects", sa.Column("github_repo", sa.String(), nullable=True))
    op.add_column("projects", sa.Column("default_branch", sa.String(), nullable=True))
    op.execute(
        "UPDATE projects SET github_repo = 'manh/group-project', default_branch = 'master' "
        "WHERE github_repo IS NULL OR default_branch IS NULL"
    )
    op.alter_column("projects", "github_repo", nullable=False)
    op.alter_column("projects", "default_branch", nullable=False)

    op.add_column("knowledge_documents", sa.Column("content_type", sa.String(), nullable=True))
    op.add_column("knowledge_documents", sa.Column("source_repo", sa.String(), nullable=True))
    op.add_column("knowledge_documents", sa.Column("language", sa.String(), nullable=True))
    op.add_column("knowledge_documents", sa.Column("decision_number", sa.String(), nullable=True))
    op.add_column("knowledge_documents", sa.Column("decision_source_pr_url", sa.String(), nullable=True))
    # Legacy PROJECT documents were imported from object storage and cannot have
    # their original type re-derived. REPO_DOC is an explicitly temporary seed.
    op.execute("UPDATE knowledge_documents SET content_type = 'REPO_DOC' WHERE knowledge_domain = 'PROJECT'")
    op.drop_constraint(
        op.f("ck_knowledge_documents_knowledge_domain_category"),
        "knowledge_documents",
        type_="check",
    )
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

    # NULL is valid for POLICY and legacy PROJECT versions. Sub-flow A will
    # always provide a pinned Git commit SHA for newly ingested PROJECT content.
    op.add_column("document_versions", sa.Column("source_ref", sa.String(), nullable=True))
    op.add_column("document_versions", sa.Column("content_status", sa.String(), nullable=True))

    # The other chunk persistence fields were introduced by c4d5e6f7a8b9.
    op.add_column("document_chunks", sa.Column("anchor", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("document_chunks", "anchor")
    op.drop_column("document_versions", "content_status")
    op.drop_column("document_versions", "source_ref")

    op.drop_constraint(op.f("ck_knowledge_documents_content_type_enum"), "knowledge_documents", type_="check")
    op.drop_constraint(
        op.f("ck_knowledge_documents_knowledge_domain_category"), "knowledge_documents", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_knowledge_documents_knowledge_domain_category"),
        "knowledge_documents",
        "(knowledge_domain = 'PROJECT' AND project_id IS NOT NULL "
        "AND document_category IS NOT NULL AND policy_category IS NULL) "
        "OR (knowledge_domain = 'POLICY' AND project_id IS NULL "
        "AND policy_category IS NOT NULL AND document_category IS NULL AND source_key IS NOT NULL)",
    )
    op.drop_column("knowledge_documents", "decision_source_pr_url")
    op.drop_column("knowledge_documents", "decision_number")
    op.drop_column("knowledge_documents", "language")
    op.drop_column("knowledge_documents", "source_repo")
    op.drop_column("knowledge_documents", "content_type")

    op.drop_column("projects", "default_branch")
    op.drop_column("projects", "github_repo")
