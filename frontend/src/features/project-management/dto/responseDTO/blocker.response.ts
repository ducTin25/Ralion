import type {
  BlockerAttachment,
  BlockerCategory,
  BlockerStatus,
} from "@/features/member-onboarding/types";

export type PmBlockerResponseDTO = {
  blocker_id: number;
  project_id: number;
  membership_id: number;
  plan_task_id: number;
  engineer_name: string;
  engineer_email: string;
  task_title: string;
  category: BlockerCategory;
  reason: string;
  status: BlockerStatus;
  reported_at: string;
  resolved_at: string | null;
  attachments: BlockerAttachment[];
};
