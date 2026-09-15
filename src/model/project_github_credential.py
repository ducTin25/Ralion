from datetime import datetime

from sqlalchemy import Enum, ForeignKey, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base
from src.model.enums import GithubCredentialValidationStatus


class ProjectGithubCredential(Base):
    """Encrypted per-project GitHub PAT — a narrow sibling of `Project`, not a general
    "connection" object. `Project.github_repo`/`default_branch` stay the single source of truth
    for *what* to sync; this table only answers *how to authenticate* for that project, kept
    separate so credential ciphertext never rides along with `Project` reads/responses.

    1:1 with `Project` via `project_id` as its own primary key — no surrogate id, no unique
    constraint needed. Absence of a row means "no credential connected yet", not an error state.
    """

    __tablename__ = "project_github_credentials"

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.project_id"), primary_key=True)
    token_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    validation_status: Mapped[GithubCredentialValidationStatus] = mapped_column(
        Enum(GithubCredentialValidationStatus, name="github_credential_validation_status"),
        nullable=False,
        default=GithubCredentialValidationStatus.UNVALIDATED,
    )
    last_validated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # Short, operator-facing only (never the raw GitHub response body) — see
    # github_credential_provider.mark_invalid.
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )
