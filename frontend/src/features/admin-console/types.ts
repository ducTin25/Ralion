export type ConsoleSection =
  "overview" | "users" | "projects" | "memberships" | "master-template" | "policies";

export type PageMeta = { page: number; page_size: number; total: number };

export type ConsoleUser = {
  user_id: number;
  display_name: string;
  email: string;
  system_role: "ADMIN" | "HR" | null;
  status: "ACTIVE" | "INACTIVE";
  project_count: number;
  created_at: string;
  created_by_name: string | null;
  // Ngày bắt đầu làm việc; null với tài khoản tạo trước khi có cột này.
  start_date: string | null;
  // True khi mật khẩu hiện tại do admin đặt và người dùng chưa tự đổi.
  must_change_password: boolean;
  // Số quyền truy cập đang chờ admin cấp, chỉ tính membership còn hoạt động.
  pending_access_count: number;
};

export type ConsoleUserMembership = {
  membership_id: number;
  project_id: number;
  project_name: string;
  project_key: string;
  project_role: "PM" | "ENGINEER";
  status: "ACTIVE" | "INACTIVE";
  project_status: "ACTIVE" | "ARCHIVED";
  joined_at: string;
};

export type ConsoleUserDetail = ConsoleUser & {
  active_project_count: number;
  memberships: ConsoleUserMembership[];
};

export type ConsoleProject = {
  project_id: number;
  name: string;
  key: string;
  status: "ACTIVE" | "ARCHIVED";
  primary_pm_name: string | null;
  member_count: number;
  active_member_count: number;
  created_at: string;
  created_by_name: string | null;
  // Số quyền truy cập đang chờ cấp trong dự án này.
  pending_access_count: number;
};

export type SyncStatus = "NOT_STARTED" | "SYNCING" | "SUCCESS" | "PARTIAL" | "FAILED";

export type ConsoleProjectMember = {
  membership_id: number;
  user_id: number;
  display_name: string;
  email: string;
  project_role: "PM" | "ENGINEER";
  status: "ACTIVE" | "INACTIVE";
  joined_at: string;
  is_primary_pm: boolean;
};

export type ConsoleProjectDetail = ConsoleProject & {
  // `pending/<mã dự án>` là giá trị giả gán lúc tạo project — coi như chưa cấu hình.
  github_repo: string | null;
  default_branch: string | null;
  primary_pm_email: string | null;
  primary_pm_membership_id: number | null;
  active_pm_count: number;
  sync_status: SyncStatus;
  last_synced_at: string | null;
  members: ConsoleProjectMember[];
};

export type AccessState = "ACTIVE" | "SUSPENDED" | "BLOCKED_USER" | "BLOCKED_PROJECT";

export type ConsoleMembership = {
  membership_id: number;
  user_id: number;
  user_name: string;
  user_email: string;
  project_id: number;
  project_name: string;
  project_key: string;
  project_role: "PM" | "ENGINEER";
  status: "ACTIVE" | "INACTIVE";
  assigned_by_name: string | null;
  joined_at: string;
  user_system_role: "ADMIN" | "HR" | null;
  user_status: "ACTIVE" | "INACTIVE";
  project_status: "ACTIVE" | "ARCHIVED";
  is_primary_pm: boolean;
  access_state: AccessState;
  // Membership là đơn vị gắn quyền truy cập.
  granted_access_count: number;
  pending_access_count: number;
};

export type MembershipSummary = {
  total: number;
  active: number;
  suspended: number;
  blocked: number;
};

export type MembershipBulkResult = {
  created: ConsoleMembership[];
  skipped: Array<{ user_id: number; display_name: string | null; reason: string }>;
};

export type ConsolePolicy = {
  document_id: number;
  title: string;
  policy_category: string;
  source_key: string | null;
  // Nhãn phiên bản trên tài liệu gốc (ví dụ "3.2") — là CHUỖI, không phải số.
  // Thứ tự sắp xếp dùng revision_no; so sánh chuỗi sẽ cho "10" < "9".
  version_no: string | null;
  revision_no: number | null;
  effective_date: string | null;
  version_status: "PROCESSING" | "ACTIVE" | "FAILED" | "ARCHIVED" | null;
  created_by_name: string | null;
  status: "ACTIVE" | "ARCHIVED";
  created_at: string;
  // Có bắt nhân viên xác nhận đã đọc hay không. HR bật/tắt trong drawer chi tiết.
  requires_acknowledgement: boolean;
};

export type PolicyDetail = ConsolePolicy & { source_url: string; summary?: string | null };

/** Kết quả đọc file trước khi ingest — dữ liệu cho màn hình HR review. */
export type PolicyInspectResult = {
  detected_title: string | null;
  detected_document_code: string | null;
  detected_version: string | null;
  detected_effective_date: string | null;
  markdown_preview: string;
  warnings: string[];
  existing_document_id: number | null;
  existing_document_title: string | null;
};

/** Một chính sách kèm tỷ lệ người đã xác nhận đã đọc. */
export type PolicyCoverage = {
  document_id: number;
  title: string;
  policy_category: string;
  version_no: string | null;
  effective_date: string | null;
  acknowledged_count: number;
  required_count: number;
  // Server tính sẵn để mọi màn hình hiển thị cùng một con số.
  coverage_percent: number;
};

export type AckUser = {
  user_id: number;
  display_name: string;
  email: string;
  // null ở danh sách chưa xác nhận.
  acknowledged_at: string | null;
};

export type PolicyCoverageDetail = {
  document_id: number;
  title: string;
  version_no: string | null;
  requires_acknowledgement: boolean;
  acknowledged: AckUser[];
  pending: AckUser[];
};

/** Nội dung đã chuyển đổi, để xem trong ứng dụng thay vì phải tải file về. */
export type PolicyContent = {
  document_id: number;
  title: string;
  policy_category: string;
  version_no: string;
  effective_date: string | null;
  content: string;
  source_url: string;
};

export type PolicyUploadFields = {
  document_code: string;
  title: string;
  policy_category: string;
  version?: string;
  effective_date?: string;
};

/** Một dòng CSV sau khi kiểm tra, dùng cho màn hình xem trước import. */
export type UserImportRow = {
  line: number;
  display_name: string;
  email: string;
  system_role: "ADMIN" | "HR" | null;
  start_date: string | null;
  // null = dòng hợp lệ; khác null là lý do sẽ bị bỏ qua.
  error: string | null;
};

export type UserImportPreview = {
  rows: UserImportRow[];
  valid_count: number;
  invalid_count: number;
};

export type UserImportCreated = {
  user_id: number;
  display_name: string;
  email: string;
  // Chỉ trả về một lần, không lưu ở đâu. Admin phải gửi ngay cho từng người.
  temporary_password: string;
};

export type UserImportResult = {
  created: UserImportCreated[];
  skipped: UserImportRow[];
};

export type Overview = {
  active_users: number;
  active_projects: number;
  active_memberships: number;
  unassigned_active_users: number;
  total_users: number;
  total_projects: number;
  total_memberships: number;
  risk_count: number;
};

export type RiskKind =
  | "INACTIVE_USER_IN_PROJECT"
  | "PROJECT_WITHOUT_PM"
  | "ACTIVE_USER_NO_MEMBERSHIP"
  | "STALE_POLICY"
  | "POLICY_MISSING_EFFECTIVE_DATE"
  | "PENDING_ACCESS_OVERDUE";

export type AccessResourceType =
  "REPOSITORY" | "ISSUE_TRACKER" | "CI_CD" | "DATABASE" | "SECRETS" | "VPN" | "OTHER";

export type OffboardingAccess = {
  grant_id: number;
  resource_type: AccessResourceType;
  resource_label: string;
  resource_note: string | null;
  project_name: string | null;
};

export type UserDeactivationPreview = {
  user_id: number;
  display_name: string;
  email: string;
  is_primary_pm_of: Array<{ project_id: number; project_name: string; project_key: string }>;
  memberships: Array<{
    membership_id: number;
    project_id: number;
    project_name: string;
    project_key: string;
    project_role: "PM" | "ENGINEER";
  }>;
  granted_access: OffboardingAccess[];
  will_revoke_sessions: boolean;
};

export type MembershipOffboardingPreview = {
  membership_id: number;
  user_id: number;
  display_name: string;
  project_id: number;
  project_name: string;
  project_key: string;
  is_primary_pm: boolean;
  granted_access: OffboardingAccess[];
};

export type AdminRiskItem = {
  risk_id: string;
  kind: RiskKind;
  severity: "HIGH" | "MEDIUM";
  title: string;
  message: string;
  action_label: string;
  user_id: number | null;
  user_email: string | null;
  membership_id: number | null;
  project_id: number | null;
  project_name: string | null;
  project_key: string | null;
  // Chỉ có ở risk thuộc miền chính sách.
  document_id: number | null;
};

export type AdminUnassignedUser = {
  user_id: number;
  display_name: string;
  email: string;
  system_role: "ADMIN" | "HR" | null;
  created_at: string;
  inactive_membership_count: number;
};

export type AdminPriorityUser = Pick<
  ConsoleUser,
  "user_id" | "display_name" | "email" | "created_at"
>;

export type MembershipEligibility = {
  users: Array<Pick<ConsoleUser, "user_id" | "display_name" | "email">>;
  projects: Array<Pick<ConsoleProject, "project_id" | "name" | "key">>;
};
