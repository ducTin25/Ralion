/** Response body trả về từ GET/POST/PATCH/DELETE /api/v1/projects/pm[...]. */
import type { IngestionJobResponseDTO } from "@/features/project-management/dto/responseDTO/discoverySchedule.response";

export type ProjectResponseDTO = {
  project_id: number;
  key: string;
  name: string;
  primary_pm_membership_id: number | null;
  created_by_admin_id: number;
  status: "ACTIVE" | "ARCHIVED";
  /** Trạng thái đồng bộ dữ liệu project (thêm bởi teammate ở nhánh develop, xem migration a1b2c3d4e5f6). */
  sync_status: "NOT_STARTED" | "SYNCING" | "SUCCESS" | "PARTIAL" | "FAILED";
  last_synced_at: string | null;
  created_at: string;
  github_repo: string | null;
  default_branch: string | null;
  /** null = no credential connected yet (never connected, or a legacy project from before
   * per-project GitHub credentials existed) — distinct from an error, not just "unknown". */
  github_credential_status: "VALID" | "INVALID" | null;
  github_sync_job?: IngestionJobResponseDTO | null;
};
