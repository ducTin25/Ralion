"""Persist final grounding status and enforce claim/message citation ownership."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: str | Sequence[str] | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "answer_claims",
        sa.Column("redacted", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.alter_column("answer_claims", "redacted", server_default=None)
    op.add_column("chat_messages", sa.Column("answer_status", sa.String(length=32), nullable=True))
    op.add_column(
        "chat_messages", sa.Column("validator_outcome", sa.String(length=32), nullable=True)
    )
    op.add_column("chat_messages", sa.Column("conflict", sa.Text(), nullable=True))
    op.execute(
        """
        UPDATE chat_messages
        SET answer_status = CASE
                WHEN role = 'ASSISTANT' AND fallback_reason IS NOT NULL THEN 'fallback'
                WHEN role = 'ASSISTANT' AND grounded THEN 'verified'
                ELSE NULL
            END,
            validator_outcome = CASE
                WHEN role = 'ASSISTANT' AND fallback_reason = 'validator_fail' THEN 'failed'
                WHEN role = 'ASSISTANT' AND grounded THEN 'passed'
                ELSE NULL
            END
        """
    )

    op.create_unique_constraint(
        op.f("uq_answer_claims_claim_id"),
        "answer_claims",
        ["claim_id", "message_id"],
    )

    op.drop_constraint(op.f("uq_citations_claim_id"), "citations", type_="unique")
    op.create_unique_constraint(
        op.f("uq_citations_claim_id"),
        "citations",
        ["claim_id", "chunk_id", "quote"],
    )
    op.drop_constraint(
        op.f("fk_citations_claim_id_answer_claims"), "citations", type_="foreignkey"
    )
    op.create_foreign_key(
        op.f("fk_citations_claim_id_answer_claims"),
        "citations",
        "answer_claims",
        ["claim_id", "message_id"],
        ["claim_id", "message_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # The predecessor allowed only one citation per (claim, chunk). Task 6 intentionally allows
    # multiple distinct verified spans in the same chunk, so fail before DDL rather than dropping
    # or collapsing those anchors during downgrade.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM citations
                WHERE claim_id IS NOT NULL
                GROUP BY claim_id, chunk_id
                HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade final claim persistence: a claim has multiple citations in one chunk. Reconcile those anchors before downgrade.';
            END IF;
        END $$;
        """
    )
    op.drop_constraint(
        op.f("fk_citations_claim_id_answer_claims"), "citations", type_="foreignkey"
    )
    op.create_foreign_key(
        op.f("fk_citations_claim_id_answer_claims"),
        "citations",
        "answer_claims",
        ["claim_id"],
        ["claim_id"],
        ondelete="CASCADE",
    )
    op.drop_constraint(op.f("uq_citations_claim_id"), "citations", type_="unique")
    op.create_unique_constraint(
        op.f("uq_citations_claim_id"), "citations", ["claim_id", "chunk_id"]
    )
    op.drop_constraint(op.f("uq_answer_claims_claim_id"), "answer_claims", type_="unique")
    op.drop_column("answer_claims", "redacted")

    op.drop_column("chat_messages", "conflict")
    op.drop_column("chat_messages", "validator_outcome")
    op.drop_column("chat_messages", "answer_status")
