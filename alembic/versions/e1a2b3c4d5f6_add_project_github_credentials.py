"""project_github_credentials: per-project encrypted GitHub PAT.

Replaces the single global GITHUB_TOKEN/GITHUB_TOKEN_OWNER pair (one fine-grained PAT, one
resource owner) for the production project-sync path. That pairing only ever worked when every
project's repo happened to live under the same GitHub owner — a real user hit exactly that wall
connecting a repo under a different owner ('Repo belongs to X, not configured owner Y').

`project_id` is both PK and FK: this table is 1:1 with `projects`, deliberately not modelled as
a general "connection" object — `projects.github_repo`/`default_branch` (see
`b7d2f4a19c53_github_target_optional_paired`) stay the only source of truth for *what* to sync;
this table only answers *how to authenticate*, kept separate so ciphertext never rides along
with a `Project` read/response. See CHANGE_LOG.md for the full design discussion.

Revision ID: e1a2b3c4d5f6
Revises: c5d7e9f1a3b4
Create Date: 2026-08-24

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e1a2b3c4d5f6"
down_revision: str | Sequence[str] | None = "c5d7e9f1a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_github_credentials",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("token_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column(
            "validation_status",
            sa.Enum("UNVALIDATED", "VALID", "INVALID", name="github_credential_validation_status"),
            nullable=False,
        ),
        sa.Column("last_validated_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.project_id"],
            name=op.f("fk_project_github_credentials_project_id_projects"),
        ),
        sa.PrimaryKeyConstraint("project_id", name=op.f("pk_project_github_credentials")),
    )


def downgrade() -> None:
    op.drop_table("project_github_credentials")
    sa.Enum(name="github_credential_validation_status").drop(op.get_bind(), checkfirst=True)
