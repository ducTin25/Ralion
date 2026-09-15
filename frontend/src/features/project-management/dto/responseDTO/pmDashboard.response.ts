import type { PmBlockerResponseDTO } from "@/features/project-management/dto/responseDTO/blocker.response";

export type PmDashboardEngineerOverdueDTO = {
  membership_id: number;
  engineer_name: string;
  overdue_count: number;
};

/** Trang "Tổng quan" — tổng hợp số liệu đã có ở các trang khác (Thành viên/Blocker Engineer/Tài
 * liệu dự án/Master Template) vào 1 màn hình, không phải chỉ số tính riêng cho dashboard. */
export type PmDashboardResponseDTO = {
  project_id: number;
  project_key: string;
  project_name: string;

  engineer_count: number;
  with_plan_count: number;
  active_count: number;
  done_count: number;

  open_blocker_count: number;
  overdue_task_count: number;

  document_group_count: number;
  document_group_total: number;

  template_approved: boolean;
  template_task_count: number;

  oldest_open_blockers: PmBlockerResponseDTO[];
  engineers_with_most_overdue: PmDashboardEngineerOverdueDTO[];

  /** `null` = chưa có dữ liệu (Langfuse chưa cấu hình, lỗi mạng, hoặc dự án chưa sinh plan sau khi
   * tính năng gắn tag cost tồn tại) — KHÁC `0`, hiện "—" chứ không phải "$0". */
  total_ai_cost_usd: number | null;
};
