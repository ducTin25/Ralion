export type PlanStatus = "APPROVED" | "ACTIVE" | "PROJECT_READY" | "ONBOARDING_CLOSED";
export type TaskStatus = "NOT_STARTED" | "IN_PROGRESS" | "DONE" | "BLOCKED";
export type TaskCategory =
  "COMPANY" | "ORIENTATION" | "ACCESS" | "SETUP" | "CODEBASE" | "CONVENTION";
export type BlockerCategory = "ACCESS" | "SETUP" | "DOCUMENT" | "TECHNICAL" | "OTHER";
export type BlockerStatus = "OPEN" | "ROUTED" | "RESOLVED";

export type MemberProfile = {
  user_id: number;
  email: string;
  display_name: string;
};

export type MemberProject = {
  project_id: number;
  membership_id: number;
  key: string;
  name: string;
  project_role: "ENGINEER";
  plan_id: number | null;
  plan_status: PlanStatus | null;
};

export type MemberProjects = {
  member: MemberProfile;
  projects: MemberProject[];
};

export type MemberTaskSummary = {
  plan_task_id: number;
  title: string;
  category: TaskCategory;
  display_order: number;
  mandatory: boolean;
  estimated_minutes: number;
  status: TaskStatus;
  due_at: string | null;
  is_overdue: boolean;
  is_due_soon: boolean;
  started_at: string | null;
  completed_at: string | null;
  dependencies_met: boolean;
  open_blocker_count: number;
  source_count: number;
  is_locked: boolean;
  lock_reason: string | null;
  can_start: boolean;
  can_complete: boolean;
};

export type MemberTaskGroup = {
  category: TaskCategory;
  tasks: MemberTaskSummary[];
};

export type MemberChecklist = {
  member: MemberProfile;
  project: { project_id: number; key: string; name: string };
  membership_id: number;
  plan_id: number;
  plan_status: PlanStatus;
  approved_at: string | null;
  progress: { completed: number; total: number; percent: number };
  groups: MemberTaskGroup[];
};

export type MemberTaskDetail = MemberTaskSummary & {
  plan_id: number;
  plan_status: PlanStatus;
  objective: string;
  instruction: string;
  dependencies: { plan_task_id: number; title: string; status: TaskStatus }[];
  sources: {
    document_id: number;
    version_id: number;
    title: string;
    source_url: string;
    citation_note: string | null;
  }[];
  citations: {
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
  }[];
};

/** File minh chứng (ảnh/video) đính kèm 1 blocker — cùng hình dạng dữ liệu phía PM
 * (`BlockerAttachmentResponseDTO`), chỉ khác chỗ dùng. */
export type BlockerAttachment = {
  attachment_id: number;
  file_name: string;
  mime_type: string;
  url: string;
  uploaded_at: string;
};

export type TaskNotification = {
  plan_task_id: number;
  title: string;
  due_at: string;
  is_overdue: boolean;
  engineer_name: string | null;
  membership_id: number | null;
};

export type MemberBlocker = {
  blocker_id: number;
  plan_task_id: number;
  task_title: string;
  category: BlockerCategory;
  reason: string;
  status: BlockerStatus;
  reported_at: string;
  resolved_at: string | null;
  attachments: BlockerAttachment[];
};

/** Chính sách người dùng còn phải xác nhận đã đọc (`GET /api/v1/me/policies`).
 * Backend chỉ trả về tài liệu POLICY đang ACTIVE, có cờ requires_acknowledgement và
 * người dùng CHƯA xác nhận phiên bản hiện hành — nên danh sách này tự rỗng đi sau khi
 * xác nhận xong. */
export type PendingPolicy = {
  document_id: number;
  title: string;
  policy_category: string;
  version_no: string | null;
  effective_date: string | null;
  /** true = đã xác nhận một phiên bản CŨ HƠN của chính tài liệu này, tức đây là bản cập
   * nhật chứ không phải chính sách mới. */
  is_new_version: boolean;
};

/** Nội dung đọc tại chỗ. `source_url` luôn rỗng ở kênh member: file gốc HR upload là bản
 * chưa redact nên backend cố ý không lộ link (policy_acknowledgement_service, F-21 §8). */
export type MemberPolicyContent = {
  document_id: number;
  title: string;
  policy_category: string;
  version_no: string;
  effective_date: string | null;
  content: string;
  source_url: string;
};

export type PolicyAcknowledgement = {
  document_id: number;
  version_id: number;
  acknowledged_at: string;
  already_acknowledged: boolean;
};
