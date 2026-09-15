export type GenerationStepStatus = "PENDING" | "RUNNING" | "DONE" | "FAILED";
export type GenerationJobStatus = "RUNNING" | "DONE" | "FAILED";

export type GenerationStepResponseDTO = {
  key: string;
  label: string;
  status: GenerationStepStatus;
  /** Thời gian THẬT bước đó đã chạy (ms) — UI hiển thị số này, không tự bịa animation. */
  duration_ms: number | null;
  detail: string | null;
  progress_done: number | null;
  progress_total: number | null;
  document_count: number | null;
};

/** Tiến độ 1 lần sinh Candidate Plan. FE poll GET /onboarding-plans/pm/generate/{job_id} cho tới
 * khi status khác RUNNING. `correlation_id` để tra ngược log/trace Langfuse khi cần debug. */
export type PlanGenerationJobResponseDTO = {
  job_id: string;
  correlation_id: string;
  /** Đúng 1 trong 2 có giá trị: `membership_id` = cấp plan cho kỹ sư (sao chép bản chuẩn),
   * `project_id` = sinh/tạo lại lộ trình chuẩn của dự án (bước duy nhất gọi AI). */
  membership_id: number | null;
  project_id: number | null;
  status: GenerationJobStatus;
  steps: GenerationStepResponseDTO[];
  plan_id: number | null;
  error: string | null;
  total_duration_ms: number | null;
  warnings: string[];
};
