"""Scope PROJECT-domain knowledge_documents uniqueness by project_id.

Bug fix: `uq_knowledge_documents_domain_source_key` was `(knowledge_domain, source_key)` only.
`source_key` for GitHub-sourced PROJECT documents is `github:{repo}:{path}` — repo+path only,
with no project in it. Two projects pointing at the same repo therefore collided on the same
row: `ingest_or_update`'s lookup would find the OTHER project's document and silently update it
in place, leaving the calling project with zero documents of its own.

Split into two partial unique indexes instead of just adding `project_id` to the existing one:
POLICY rows always have `project_id IS NULL` (CHECK `knowledge_domain_category`), and Postgres
treats every NULL as distinct in a unique index, so a plain `(knowledge_domain, project_id,
source_key)` index would silently stop deduplicating POLICY documents. Keeping POLICY's index
exactly as it is today (domain + source_key only) preserves that behavior byte-for-byte; PROJECT
rows always have a real `project_id` (same CHECK), so adding it to their own index is a real,
enforceable per-project constraint.

Revision ID: a3f8c1d29e47
Revises: 0dd345991838
Create Date: 2026-08-23
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a3f8c1d29e47"
down_revision: str | Sequence[str] | None = "0dd345991838"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("uq_knowledge_documents_domain_source_key", table_name="knowledge_documents")
    op.create_index(
        "uq_knowledge_documents_policy_source_key",
        "knowledge_documents",
        ["knowledge_domain", "source_key"],
        unique=True,
        postgresql_where="knowledge_domain = 'POLICY' AND source_key IS NOT NULL",
    )
    op.create_index(
        "uq_knowledge_documents_project_source_key",
        "knowledge_documents",
        ["knowledge_domain", "project_id", "source_key"],
        unique=True,
        postgresql_where="knowledge_domain = 'PROJECT' AND source_key IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index("uq_knowledge_documents_project_source_key", table_name="knowledge_documents")
    op.drop_index("uq_knowledge_documents_policy_source_key", table_name="knowledge_documents")
    op.create_index(
        "uq_knowledge_documents_domain_source_key",
        "knowledge_documents",
        ["knowledge_domain", "source_key"],
        unique=True,
        postgresql_where="source_key IS NOT NULL",
    )
