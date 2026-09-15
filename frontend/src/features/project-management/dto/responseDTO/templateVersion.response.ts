/** Response body trả về từ /api/v1/template-versions/pm[...]. */
export type TemplateVersionResponseDTO = {
  version_id: number;
  template_id: number;
  version_no: number;
  status: "DRAFT" | "APPROVED" | "ARCHIVED";
  approved_by_user_id: number | null;
  approved_at: string | null;
  created_at: string;
};
