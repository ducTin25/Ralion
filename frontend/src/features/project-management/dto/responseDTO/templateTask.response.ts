export type TaskCategory =
  | "COMPANY"
  | "ORIENTATION"
  | "ARCHITECTURE"
  | "ACCESS"
  | "SETUP"
  | "CODEBASE"
  | "CONVENTION"
  | "FIRST_TASK"
  | "FIRST_PR";

/** Response body trả về từ /api/v1/template-tasks/pm[...]. */
export type TemplateTaskResponseDTO = {
  template_task_id: number;
  version_id: number;
  category: TaskCategory;
  title_pattern: string;
  objective: string;
  instruction_template: string;
  display_order: number;
  mandatory: boolean;
  estimated_minutes: number;
};
