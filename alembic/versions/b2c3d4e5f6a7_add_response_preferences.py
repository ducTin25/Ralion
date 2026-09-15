"""Add response_length/response_tone chat personalization columns to users.

See PERSONALIZE_CHATBOT_SPEC.md §1. Presentation-layer preference only — no other
table or relationship is touched.
"""

import sqlalchemy as sa

from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a9b0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    response_length_enum = sa.Enum("CONCISE", "STANDARD", "DETAILED", name="response_length")
    response_tone_enum = sa.Enum("NEUTRAL", "GUIDE", "MENTOR", "BUDDY", name="response_tone")
    response_length_enum.create(op.get_bind(), checkfirst=True)
    response_tone_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "users",
        sa.Column(
            "response_length", response_length_enum, nullable=False, server_default="STANDARD"
        ),
    )
    op.add_column(
        "users",
        sa.Column("response_tone", response_tone_enum, nullable=False, server_default="NEUTRAL"),
    )


def downgrade() -> None:
    op.drop_column("users", "response_tone")
    op.drop_column("users", "response_length")
    sa.Enum(name="response_tone").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="response_length").drop(op.get_bind(), checkfirst=True)
