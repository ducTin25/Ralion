"""Pin persisted BGE-M3 metadata to the deployed Hugging Face revision.

Revision ID: a4c6e8f0b2d3
Revises: f2a4c6e8b0d1
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a4c6e8f0b2d3"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = "f2a4c6e8b0d1"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOGICAL_MODEL = "BAAI/bge-m3"
_PINNED_MODEL = "BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181"


def _rename_model_version(source: str, target: str) -> None:
    connection = op.get_bind()
    for table_name in ("document_versions", "document_chunks", "rule_candidates"):
        connection.execute(
            sa.text(
                f"UPDATE {table_name} "  # noqa: S608 - table names are migration constants
                "SET embedding_model_version = :target "
                "WHERE embedding_model_version = :source"
            ),
            {"source": source, "target": target},
        )


def upgrade() -> None:
    """Relabel existing vectors; the pinned revision is the same immutable weight set."""

    _rename_model_version(_LOGICAL_MODEL, _PINNED_MODEL)


def downgrade() -> None:
    _rename_model_version(_PINNED_MODEL, _LOGICAL_MODEL)
