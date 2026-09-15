import type { DocumentCategory } from "./document.response";

export type CandidateStatus = "FOUND" | "UNCLASSIFIED" | "DUPLICATE_OR_STALE";

export type ScanCandidateResponseDTO = {
  candidate_id: string;
  relative_path: string;
  filename: string;
  size_bytes: number;
  suggested_category: DocumentCategory | null;
  confidence: number;
  reason: string;
  status: CandidateStatus;
};

/** Response body trả về từ POST /knowledge-documents/pm/projects/{project_id}/scan — chưa ghi DB,
 * chỉ để PM xem/sửa trước khi bấm "Approve & Import". */
export type CoverageReportResponseDTO = {
  scan_session_id: string;
  candidates: ScanCandidateResponseDTO[];
  missing_categories: DocumentCategory[];
};
