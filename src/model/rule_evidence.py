from datetime import datetime

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base


class RuleEvidence(Base):
    """One evidence unit's immutable snapshot as a member of a RuleFamily.

    Snapshot, never a live FK to the source GitHub comment/review — the content
    captured here is exactly what mining saw at cluster time (F6_RULE_MINING_SPEC.md
    §5.2, plan §0 snapshot invariant).
    """

    __tablename__ = "rule_evidences"
    __table_args__ = (
        UniqueConstraint("evidence_unit_id", name="uq_rule_evidences_evidence_unit_id"),
    )

    rule_evidence_id: Mapped[int] = mapped_column(primary_key=True)
    rule_candidate_id: Mapped[int] = mapped_column(
        ForeignKey("rule_candidates.rule_candidate_id"), nullable=False, index=True
    )
    rule_family_id: Mapped[int] = mapped_column(
        ForeignKey("rule_families.rule_family_id"), nullable=False, index=True
    )
    # Khoá nghiệp vụ định danh đúng 1 comment/review gốc trên GitHub (vd
    # "review_comment(diff):<github id>") — định dạng cụ thể do F6 mining code quyết
    # định; cột này chỉ giữ chỗ cho tính duy nhất dùng trong eligibility query
    # (COUNT(DISTINCT evidence_unit_id), F6_RULE_MINING_SPEC.md §5.3).
    evidence_unit_id: Mapped[str] = mapped_column(nullable=False)
    pr_number: Mapped[int] = mapped_column(nullable=False)
    comment_snippet_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    original_author: Mapped[str] = mapped_column(nullable=False)
    evidence_created_at: Mapped[datetime] = mapped_column(nullable=False)
    # Cosine similarity giữa embedding rule_text_draft của evidence unit này và
    # evidence "đối tác" đầu tiên khiến nó được merge vào family — trọng số cạnh
    # trong đồ thị connected-components (F6_RULE_MINING_SPEC.md §4.1). NULL nếu đây
    # là node đầu tiên của family (không có cạnh vào).
    cluster_edge_cosine_similarity: Mapped[float | None] = mapped_column(nullable=True)
