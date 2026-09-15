/**
 * F6 Rule Mining contract — mirrors `src/dto/response/rule_review_dto.py`.
 *
 * Owned by the `conventions` feature because two actors read the same shape: PM reviews
 * PENDING families (`GET /rule-candidates/pending`) and Member browses APPROVED ones
 * (`GET /conventions`). Backend deliberately returns one shape for both so the frontend
 * renders them with a single evidence component instead of two parallel contracts.
 */

export type RuleFamilyStatus = "PENDING" | "APPROVED" | "REJECTED";

/** "HIGH" | "MEDIUM" | null — derived server-side from the weakest cluster edge, never stored
 * and never recomputed here. The UI only labels it. */
export type FamilyMatchConfidence = "HIGH" | "MEDIUM";

export type RuleEvidenceItemDTO = {
  comment_snippet_snapshot: string;
  original_author: string;
  evidence_created_at: string;
  /** Real GitHub URL captured at ingestion time. Never rebuilt client-side from a PR number. */
  permalink: string;
  /** NULL for the family's anchor evidence (no incoming cluster edge). */
  cluster_edge_cosine_similarity: number | null;
};

export type RuleFamilyItemDTO = {
  rule_family_id: number;
  rule_text: string;
  status: RuleFamilyStatus;
  /** Provenance metadata for PM judgement only — never an eligibility input, never a filter. */
  distinct_reviewer_count: number;
  family_match_confidence: FamilyMatchConfidence | string | null;
  evidence: RuleEvidenceItemDTO[];
};

export type PageMetaDTO = {
  page: number;
  page_size: number;
  total: number;
};

export type RuleFamilyListDTO = {
  items: RuleFamilyItemDTO[];
  meta: PageMetaDTO;
};

export type RuleFamilyActionResultDTO = {
  rule_family_id: number;
  status: RuleFamilyStatus;
  approved_by: number | null;
  approved_at: string | null;
  rejected_by: number | null;
  rejected_at: string | null;
  /** Did the approved rule reach the shared retrieval engine? `false` means the decision
   * stands but F5 cannot answer from it yet — recoverable through the reindex endpoint.
   * Always null for a reject (nothing to index). */
  retrieval_indexed: boolean | null;
};
