import type { PmBlockerResponseDTO } from "@/features/project-management/dto/responseDTO/blocker.response";
import type { TaskCategory } from "@/features/project-management/dto/responseDTO/templateTask.response";
import type { TaskStatus } from "@/features/project-management/dto/responseDTO/planTask.response";
import type { OnboardingPlanResponseDTO } from "@/features/project-management/dto/responseDTO/onboardingPlan.response";

export type PmProgressTaskDTO = {
  plan_task_id: number;
  title: string;
  category: TaskCategory;
  mandatory: boolean;
  status: TaskStatus;
  /** Suy ra từ due_at của task đứng trước — không phải cột DB. */
  start_at: string | null;
  due_at: string | null;
  is_overdue: boolean;
};

/** Tiến độ của ĐÚNG 1 Engineer, nhìn từ phía PM — SoT §17.2 "theo dõi tiến độ, deadline và blocker
 * của từng plan". `plan_id`/`plan_status` = null khi Engineer chưa được cấp plan (chưa duyệt). */
export type PmMemberProgressResponseDTO = {
  membership_id: number;
  engineer_name: string;
  engineer_email: string;
  plan_id: number | null;
  plan_status: OnboardingPlanResponseDTO["status"] | null;
  approved_at: string | null;
  completed_count: number;
  total_count: number;
  percent: number;
  overdue_count: number;
  tasks: PmProgressTaskDTO[];
  blockers: PmBlockerResponseDTO[];
};
