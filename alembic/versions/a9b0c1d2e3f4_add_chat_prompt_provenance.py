"""Persist prompt and retrieval provenance for grounded chat calls."""

import sqlalchemy as sa

from alembic import op

revision = "a9b0c1d2e3f4"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("llm_call_logs", sa.Column("prompt_version", sa.String(length=64), nullable=True))
    op.add_column("llm_call_logs", sa.Column("retrieval_config_version", sa.String(length=64), nullable=True))
    op.add_column("llm_call_logs", sa.Column("generation_config", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("llm_call_logs", "generation_config")
    op.drop_column("llm_call_logs", "retrieval_config_version")
    op.drop_column("llm_call_logs", "prompt_version")
