import type { TaskCategory } from "@/features/project-management/dto/responseDTO/templateTask.response";

export type TaskStatus = "NOT_STARTED" | "IN_PROGRESS" | "DONE" | "BLOCKED";

/** 1 nguồn trích dẫn của task — trỏ tới đúng 1 ĐOẠN trong 1 file tài liệu.
 * `document_title`/`document_url` được backend join sẵn để mở DocumentPreviewModal ngay, không phải
 * gọi thêm API. `section_path`/`anchor` join từ DocumentChunk để cuộn/tô sáng đúng đoạn.
 * `chunk_id`/`section_path`/`anchor` = null khi nguồn chỉ tham chiếu cả file: plan sinh trước khi
 * lưu chunk_id, hoặc nhánh baseline / "có tài liệu nhưng không tìm được đoạn khớp". */
export type PlanTaskSourceResponseDTO = {
  task_source_id: number;
  plan_task_id: number;
  version_id: number;
  document_id: number;
  document_title: string;
  document_url: string;
  citation_note: string | null;
  chunk_id: number | null;
  section_path: string | null;
  anchor: string | null;
};

/** 1 trích dẫn `[n]` — trỏ tới đúng 1 ĐOẠN trong tài liệu.
 * Khác `PlanTaskSourceResponseDTO` (mức tài liệu, 1 dòng/file): 1 tài liệu có thể có nhiều dòng ở
 * đây, mỗi dòng ứng với 1 mục trong file. Số `[n]` trong `instruction` khớp `citation_order`.
 * `content_snippet` là văn bản thuần (đã bỏ cú pháp markdown) để dò trong nội dung đã render. */
export type PlanTaskCitationResponseDTO = {
  citation_id: number;
  plan_task_id: number;
  citation_order: number;
  version_id: number;
  document_id: number;
  document_title: string;
  document_url: string;
  chunk_id: number;
  citation_note: string | null;
  section_path: string | null;
  content_snippet: string | null;
};

/** `category` và `estimated_minutes` backend join từ TemplateTask — PlanTask không lưu 2 field này
 * (SoT §24.4 "không trộn TemplateTask với PlanTask"), nhưng FE cần để gom nhóm hiển thị. */
export type PlanTaskResponseDTO = {
  plan_task_id: number;
  plan_id: number;
  template_task_id: number;
  category: TaskCategory;
  title: string;
  instruction: string;
  display_order: number;
  mandatory: boolean;
  /** Suy ra từ due_at của task đứng trước — không phải cột DB, xem backend plan_task_service. */
  start_at: string | null;
  due_at: string | null;
  status: TaskStatus;
  estimated_minutes: number;
  sources: PlanTaskSourceResponseDTO[];
  /** Rỗng với plan sinh trước khi có bảng citation — khi đó chỉ hiện danh sách tài liệu. */
  citations: PlanTaskCitationResponseDTO[];
};
