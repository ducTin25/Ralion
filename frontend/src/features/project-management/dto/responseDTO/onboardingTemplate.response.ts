/** Response body trả về từ /api/v1/onboarding-templates/pm[...]. */
export type OnboardingTemplateResponseDTO = {
  template_id: number;
  project_id: number | null;
  source_template_id: number | null;
  scope: "GLOBAL" | "PROJECT";
  name: string;
  description: string;
  status: "DRAFT" | "APPROVED" | "NEEDS_REVIEW" | "ARCHIVED";
  created_at: string;
  updated_at: string;
};
