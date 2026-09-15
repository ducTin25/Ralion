"""Include embedding model in document version identity."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: str | Sequence[str] | None = "e6f7a8b9c0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("document_versions", sa.Column("embedding_model_version", sa.String(), nullable=True))
    op.execute(
        "UPDATE document_versions AS version SET embedding_model_version = COALESCE("
        "(SELECT min(chunk.embedding_model_version) FROM document_chunks AS chunk "
        "WHERE chunk.version_id = version.version_id), 'legacy')"
    )
    op.execute("SET CONSTRAINTS ALL IMMEDIATE")
    op.alter_column("document_versions", "embedding_model_version", nullable=False)
    op.drop_constraint(op.f("uq_document_versions_document_id"), "document_versions", type_="unique")
    op.create_unique_constraint(
        "uq_document_versions_document_model_version",
        "document_versions",
        ["document_id", "version_no", "embedding_model_version"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_document_versions_document_model_version", "document_versions", type_="unique")
    op.create_unique_constraint(op.f("uq_document_versions_document_id"), "document_versions", ["document_id", "version_no"])
    op.drop_column("document_versions", "embedding_model_version")
