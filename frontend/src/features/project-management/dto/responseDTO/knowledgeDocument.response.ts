export type PolicyCategory =
  "COMPANY_POLICY" | "HR_POLICY" | "SECURITY_POLICY" | "BENEFIT" | "WORKING_RULE" | "GENERAL";

/** Response body trả về từ /api/v1/knowledge-documents/policy. */
export type KnowledgeDocumentResponseDTO = {
  document_id: number;
  title: string;
  source_url: string;
  policy_category: PolicyCategory;
  status: "ACTIVE" | "ARCHIVED";
  created_at: string;
};
