from datetime import datetime

from sqlalchemy import BigInteger, Index, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base


class RawPrComment(Base):
    """One row per GitHub PR review-comment / issue-comment / review, as fetched by
    GithubClient.fetch_pr_comments()/fetch_pr_reviews() (F2 Sub-flow B corpus staging
    for F6). Flat, denormalized shape matching what density_check.py's CSV output
    already validated — no separate PR-level table; that design isn't needed until an
    actual join-by-PR-metadata use case exists.

    ``F6_RULE_MINING_SPEC.md`` §1.2 references a base plan §2 for this table's design
    that is not present in this worktree (confirmed absent in the Phase 0 audit); this
    schema is the minimal fallback agreed for the schema-migration phase, not a
    reconstruction of that missing document.
    """

    __tablename__ = "raw_pr_comments"
    __table_args__ = (
        Index("ix_raw_pr_comments_repo_pr_number", "repo", "pr_number"),
        # Postgres UNIQUE constraints already treat NULL as distinct from every other NULL, so
        # the 762 rows ingested before this column existed (github_id NULL) never collide with
        # each other — this is the real dedup/idempotency anchor for F6 Scheduled Incremental
        # Convention Discovery: a rerun over an overlapping window is a plain
        # `INSERT ... ON CONFLICT (repo, type, github_id) DO NOTHING` against this constraint,
        # not a duplicate insert.
        UniqueConstraint(
            "repo", "type", "github_id", name="uq_raw_pr_comments_repo_type_github_id"
        ),
    )

    raw_pr_comment_id: Mapped[int] = mapped_column(primary_key=True)
    repo: Mapped[str] = mapped_column(nullable=False)
    # GitHub's own id for this comment/review (PrComment.id/PrReview.id in github_client.py) —
    # stable across reruns, unlike the surrogate PK above. NULL only for rows ingested before
    # this column existed.
    github_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    pr_number: Mapped[int] = mapped_column(nullable=False)
    pr_author: Mapped[str] = mapped_column(nullable=False)
    # 'review_comment(diff)' | 'issue_comment(conversation)' | 'review(summary)' —
    # same three values density_check.py's 'type' column already carries.
    type: Mapped[str] = mapped_column(nullable=False)
    author: Mapped[str] = mapped_column(nullable=False)
    is_bot_comment: Mapped[bool] = mapped_column(nullable=False)
    # Không truncate khi persist (F6_RULE_MINING_SPEC.md §1.2) — cùng nguyên tắc vừa
    # sửa ở CSV writer của density_check.py, không lặp lại lỗi đó ở tầng DB.
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Context from a GitHub diff review comment.  These remain nullable because issue
    # comments and review summaries do not necessarily point to a code range.
    code_snippet_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    code_path_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    code_before_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    code_after_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_state: Mapped[str | None] = mapped_column(nullable=True)
    in_reply_to_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    url: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    # Set khi secret_scan_and_redact() đã chạy qua dòng này — NULL nghĩa là chưa scan,
    # không phải "đã scan và sạch" (F2 ingestion, Phase 3, phải phân biệt 2 trạng thái
    # này trước khi cho phép dòng này đi tiếp vào bước embed/cluster).
    secret_scanned_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    # Set on an evidence unit's ROOT comment (EvidenceUnit.comments[0], same row
    # evidence_unit_id derives from — evidence_grouping.py) once F6 mining reaches a terminal
    # classification (eligible or filtered_out) for that unit. NULL means "not yet processed OR
    # provider/extraction failed and must retry" — deliberately the same nullable-marker
    # convention as secret_scanned_at, not a new enum, and deliberately never set for
    # extraction_failed/invalid_output so those units retry on the next incremental run instead
    # of being silently skipped forever.
    mining_processed_at: Mapped[datetime | None] = mapped_column(nullable=True)
