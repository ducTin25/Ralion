/** Response body trả về từ GET /api/v1/onboarding-plans/pm/by-project|by-membership. Chỉ đọc. */
export type OnboardingPlanResponseDTO = {
  plan_id: number;
  /** Đúng 1 trong 2 có giá trị: `membership_id` = plan đã cấp cho 1 kỹ sư,
   * `project_id` = lộ trình chuẩn của dự án (chưa cấp cho ai). */
  membership_id: number | null;
  project_id: number | null;
  template_version_id: number;
  revision: number;
  status: "DRAFT" | "APPROVED" | "ACTIVE" | "PROJECT_READY" | "ONBOARDING_CLOSED";
  approved_by_user_id: number | null;
  approved_at: string | null;
  created_at: string;
  closed_at: string | null;
  first_pr_url: string | null;
  first_pr_merged_at: string | null;
  first_pr_confirmed_by_user_id: number | null;
};
