"""Add first-class answer claims and claim-aware citation ownership.

Existing citations cannot be truthfully backfilled to a claim because their source schema has
no claim text, order, support type, or verdict. They are therefore retained with ``claim_id``
NULL until the F-14 generation/persistence contract is introduced.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | Sequence[str] | None = "a7c4e91b2d38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    support_type = sa.Enum("direct", "inferred", name="claim_support_type")
    op.create_table(
        "answer_claims",
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("claim_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("support_type", support_type, nullable=False),
        sa.Column("verdict", sa.String(length=32), server_default="pending", nullable=False),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["chat_messages.message_id"],
            name=op.f("fk_answer_claims_message_id_chat_messages"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("claim_id", name=op.f("pk_answer_claims")),
        sa.UniqueConstraint(
            "message_id", "claim_index", name=op.f("uq_answer_claims_message_id")
        ),
    )

    # Keep this nullable and do not invent claims for historical citation rows. Dropping the
    # old message-level uniqueness permits one chunk to support more than one future claim.
    op.add_column("citations", sa.Column("claim_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_citations_claim_id_answer_claims"),
        "citations",
        "answer_claims",
        ["claim_id"],
        ["claim_id"],
        ondelete="CASCADE",
    )
    op.drop_constraint(op.f("uq_citations_message_id"), "citations", type_="unique")
    op.create_unique_constraint(
        op.f("uq_citations_claim_id"), "citations", ["claim_id", "chunk_id"]
    )


def downgrade() -> None:
    # A downgrade must not silently discard valid F-14 data. The predecessor's uniqueness rule
    # cannot represent one chunk cited by multiple claims in one message, so stop before any DDL
    # if such rows exist.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM citations
                GROUP BY message_id, chunk_id
                HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade answer-claim persistence: citations contain message/chunk pairs belonging to multiple claims. Reconcile them before downgrade.';
            END IF;
        END $$;
        """
    )

    op.drop_constraint(op.f("uq_citations_claim_id"), "citations", type_="unique")
    op.create_unique_constraint(
        op.f("uq_citations_message_id"), "citations", ["message_id", "chunk_id"]
    )
    op.drop_constraint(
        op.f("fk_citations_claim_id_answer_claims"), "citations", type_="foreignkey"
    )
    op.drop_column("citations", "claim_id")
    op.drop_table("answer_claims")
    sa.Enum(name="claim_support_type").drop(op.get_bind(), checkfirst=True)
