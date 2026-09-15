"""Store policy source version labels and effective dates."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d5e6f7a8b9c0"
down_revision: str | Sequence[str] | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("document_versions", sa.Column("effective_date", sa.Date(), nullable=True))
    op.alter_column(
        "document_versions",
        "version_no",
        existing_type=sa.Integer(),
        type_=sa.String(),
        postgresql_using="version_no::text",
    )


def downgrade() -> None:
    op.alter_column(
        "document_versions",
        "version_no",
        existing_type=sa.String(),
        type_=sa.Integer(),
        postgresql_using="version_no::numeric::integer",
    )
    op.drop_column("document_versions", "effective_date")
