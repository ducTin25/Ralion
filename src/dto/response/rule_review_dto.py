from datetime import datetime

from pydantic import BaseModel

from src.dto.admin_console_dto import PageMetaDTO
from src.model.enums import RuleFamilyStatus


class RuleEvidenceItemDTO(BaseModel):
    comment_snippet_snapshot: str
    original_author: str
    evidence_created_at: datetime
    # Real GitHub URL from raw_pr_comments.url captured at ingestion time — never
    # reconstructed from pr_number (CLAUDE.md Phase 6 §1).
    permalink: str
    # NULL for the family's anchor evidence (no incoming cluster edge).
    cluster_edge_cosine_similarity: float | None


class RuleFamilyItemDTO(BaseModel):
    """One reviewable rule (a RuleFamily). Same shape for the pending Review Queue and the
    approved-only Conventions list — CLAUDE.md Phase 6 §3 asks for one shared shape so the
    frontend can reuse a single render component for both."""

    rule_family_id: int
    rule_text: str
    status: RuleFamilyStatus
    distinct_reviewer_count: int
    # "HIGH" | "MEDIUM" | None — derived from the weakest cluster edge in the family
    # (src.modules.knowledge.mining.clustering.confidence_from_cosine), never stored.
    family_match_confidence: str | None
    evidence: list[RuleEvidenceItemDTO]


class RuleFamilyListDTO(BaseModel):
    items: list[RuleFamilyItemDTO]
    meta: PageMetaDTO


class MemberConventionEvidenceDTO(BaseModel):
    """Immutable review evidence, deliberately without mining metadata."""

    comment_snippet_snapshot: str
    # Provider-neutral code context captured with the original review comment. These remain
    # nullable because conversation comments and evidence created before diff snapshots do not
    # have a code range.
    code_snippet_snapshot: str | None = None
    code_before_snapshot: str | None = None
    code_after_snapshot: str | None = None
    original_author: str
    pr_number: int
    evidence_created_at: datetime
    permalink: str


class MemberConventionExampleDTO(BaseModel):
    """A fenced code block copied verbatim from an evidence snapshot."""

    code: str
    pr_number: int
    original_author: str
    permalink: str


class MemberConventionItemDTO(BaseModel):
    """Read-only handbook projection of an approved F6 rule family.

    Guidance fields are intentionally nullable until the approved family has persisted
    enrichment. The handbook must remain useful when that asynchronous enrichment fails.
    """

    rule_family_id: int
    rule_text: str
    short_explanation: str | None = None
    how_to_apply: str | None = None
    rationale: str | None = None
    illustrative_bad_example: str | None = None
    illustrative_good_example: str | None = None
    actual_examples: list[MemberConventionExampleDTO]
    evidence: list[MemberConventionEvidenceDTO]


class MemberConventionListDTO(BaseModel):
    items: list[MemberConventionItemDTO]
    meta: PageMetaDTO


class RuleFamilyActionResultDTO(BaseModel):
    rule_family_id: int
    status: RuleFamilyStatus
    approved_by: int | None
    approved_at: datetime | None
    rejected_by: int | None
    rejected_at: datetime | None
    # Phase 10 — did the approved rule reach the shared retrieval engine? False means the
    # decision stands but F5 cannot answer from it yet; the reviewer can retry via
    # POST /rule-candidates/{id}/reindex. Always None for a reject (nothing to index).
    retrieval_indexed: bool | None = None
