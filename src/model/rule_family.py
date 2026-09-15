from datetime import datetime

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base
from src.model.enums import RuleFamilyStatus


class RuleFamily(Base):
    """A connected component of >=2 RuleEvidence, clustered by cosine similarity on
    their rule_text_draft embeddings (F6_RULE_MINING_SPEC.md §4.1).
    """

    __tablename__ = "rule_families"
    __table_args__ = (
        CheckConstraint(
            "status != 'APPROVED' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)",
            name="approved_requires_approved_at",
        ),
        CheckConstraint(
            "status != 'REJECTED' OR (rejected_by IS NOT NULL AND rejected_at IS NOT NULL)",
            name="rejected_requires_rejected_at",
        ),
        # Review Queue's list-PENDING query filters on this column exclusively.
        Index("ix_rule_families_status", "status"),
    )

    rule_family_id: Mapped[int] = mapped_column(primary_key=True)
    # COUNT(DISTINCT original_author) trên các RuleEvidence thành viên tại thời điểm
    # tạo family. Provenance/display only (Review Queue badge) — KHÔNG tham gia
    # eligibility hay guardrail (F6_RULE_MINING_SPEC.md §2.3, §5.1).
    distinct_reviewer_count: Mapped[int] = mapped_column(nullable=False)
    # HITL Review Queue workflow (CLAUDE.md Phase 6) — forward-only PENDING -> APPROVED|
    # REJECTED, one reviewer, no versioning. Every row that reaches this table already
    # passed the Phase 5 eligibility guardrail (>=2 distinct evidence_unit_id AND >=2
    # distinct pr_number) at insert time, so this status is purely the human decision on
    # top of that, not a second eligibility check.
    status: Mapped[RuleFamilyStatus] = mapped_column(
        Enum(RuleFamilyStatus, name="rule_family_status"),
        nullable=False,
        default=RuleFamilyStatus.PENDING,
    )
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    rejected_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(nullable=True)
