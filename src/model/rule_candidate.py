from datetime import datetime

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import Enum, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base
from src.model.enums import RuleEvidenceType


class RuleCandidate(Base):
    """One LLM-extraction result for one PR comment/review evidence unit
    (F6_RULE_MINING_SPEC.md §4.2 step 3): {rule_text_draft, rationale, evidence_type,
    reuse_scope}. Only rows with evidence_type IN (REUSABLE_CORRECTION, CONVENTION)
    and reuse_scope >= 1 are eligible to gain a member RuleEvidence row — that
    threshold is enforced at query time (§5.3), not by a schema constraint here.
    """

    __tablename__ = "rule_candidates"

    rule_candidate_id: Mapped[int] = mapped_column(primary_key=True)
    evidence_type: Mapped[RuleEvidenceType] = mapped_column(
        Enum(RuleEvidenceType, name="rule_evidence_type"), nullable=False
    )
    reuse_scope: Mapped[int] = mapped_column(nullable=False)
    rule_text_draft: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    # Persisted embedding of rule_text_draft (same BGE-M3/1024d space as DocumentChunk.embedding)
    # + the model version it was embedded with. F6 Scheduled Incremental Convention Discovery
    # reuses this to re-cluster an "orphan" (eligible but not yet in any family) candidate
    # against new evidence WITHOUT calling the embedder again — the whole point of persisting it.
    # NULL only for rows created before this column existed; embedding_model_version lets a
    # later run detect a stale vector (embedder changed since) and re-embed just that one row on
    # demand instead of silently clustering incompatible vector spaces together.
    embedding: Mapped[list[float] | None] = mapped_column(VECTOR(1024), nullable=True)
    embedding_model_version: Mapped[str | None] = mapped_column(nullable=True)
    # Provenance snapshot, same fields RuleEvidence would need if this candidate ever joins a
    # family — persisted here too because an "orphan" candidate (eligible, no family yet) has no
    # RuleEvidence row to hold them. F6 Scheduled Incremental Convention Discovery reuses this to
    # attach an orphan to a family discovered in a LATER run without re-deriving anything from
    # raw_pr_comments/evidence_grouping. NULL for every row created before this column existed —
    # those legacy orphans simply cannot be reused as a future family member (documented gap, not
    # a crash: mine_new_evidence() filters them out via `evidence_unit_id IS NOT NULL`).
    evidence_unit_id: Mapped[str | None] = mapped_column(nullable=True)
    pr_number: Mapped[int | None] = mapped_column(nullable=True)
    comment_snippet_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_author: Mapped[str | None] = mapped_column(nullable=True)
    evidence_created_at: Mapped[datetime | None] = mapped_column(nullable=True)
