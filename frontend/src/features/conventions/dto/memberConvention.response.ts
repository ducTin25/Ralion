export type MemberConventionEvidenceDTO = {
  comment_snippet_snapshot: string;
  /** Optional to support evidence created before diff snapshots were persisted. */
  code_snippet_snapshot?: string | null;
  code_before_snapshot?: string | null;
  code_after_snapshot?: string | null;
  original_author: string;
  pr_number: number;
  evidence_created_at: string;
  permalink: string;
};

/** This is rendered only from an exact fenced block persisted in RuleEvidence. */
export type MemberConventionExampleDTO = {
  code: string;
  pr_number: number;
  original_author: string;
  permalink: string;
};

export type MemberConventionItemDTO = {
  rule_family_id: number;
  rule_text: string;
  short_explanation: string | null;
  how_to_apply: string | null;
  rationale: string | null;
  illustrative_bad_example: string | null;
  illustrative_good_example: string | null;
  actual_examples: MemberConventionExampleDTO[];
  evidence: MemberConventionEvidenceDTO[];
};

export type MemberConventionListDTO = {
  items: MemberConventionItemDTO[];
  meta: { page: number; page_size: number; total: number };
};
