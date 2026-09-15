export type DocumentCategory =
  | "OVERVIEW"
  | "ARCHITECTURE"
  | "SETUP"
  | "ACCESS_SECURITY"
  | "CODEBASE_GUIDE"
  | "CONVENTION"
  | "FIRST_TASK";

export type VersionStatus = "PROCESSING" | "ACTIVE" | "FAILED" | "ARCHIVED";

/** `version_no` là nhãn dạng CHUỖI (schema chung với pipeline POLICY từ nhánh develop — POLICY
 * dùng nhãn version lấy từ tài liệu nguồn, VD "3.2"). Tài liệu PROJECT (Phase 3) không có nhãn
 * nguồn riêng nên backend tự mirror `revision_no` (số đếm thật, dùng để sort/hiển thị) sang chuỗi. */
export type DocumentVersionResponseDTO = {
  version_id: number;
  document_id: number;
  version_no: string;
  revision_no: number;
  storage_uri: string;
  checksum: string;
  status: VersionStatus;
  created_at: string;
};

/** Response body trả về từ /api/v1/knowledge-documents/pm/projects/{project_id} và các endpoint
 * upload/import — tài liệu dự án thật (domain PROJECT), khác KnowledgeDocumentResponseDTO (policy). */
export type CategoryClassificationStatus = "CLASSIFIED" | "AMBIGUOUS";

export type ProjectDocumentResponseDTO = {
  document_id: number;
  project_id: number;
  // Null khi đồng bộ tự động (GitHub sync) chưa đủ tin cậy để xếp nhóm — xem `category_confirmed`.
  document_category: DocumentCategory | null;
  category_confirmed: boolean;
  category_classification_status: CategoryClassificationStatus | null;
  title: string;
  status: "ACTIVE" | "ARCHIVED";
  latest_version: DocumentVersionResponseDTO | null;
  created_at: string;
};

/** Nội dung tài liệu dự án đã chuẩn hoá về markdown để đọc NGAY TRONG app (GET .../{id}/content).
 *
 * Backend làm hết phần phụ thuộc định dạng (`.md/.txt/.docx/.pdf`, GitHub hay PM tải tay) và trả
 * về đúng một dạng — frontend chỉ render markdown, không parse file nhị phân trong trình duyệt và
 * không phải fetch thẳng link storage (vướng CORS, và với tài liệu GitHub thì link là trang blob
 * HTML chứ không phải nội dung).
 *
 * `source_url` giữ nguyên ngữ nghĩa cũ: link tới bản gốc, nay chỉ là lối thoát phụ. */
export type ProjectDocumentContentResponseDTO = {
  document_id: number;
  title: string;
  source_url: string;
  version_no: string;
  revision_no: number;
  content: string;
};
