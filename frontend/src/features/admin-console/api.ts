import { API_BASE_URL, CONSOLE_DEMO_USER_ID, CONSOLE_ENDPOINT } from "@/lib/api";
import { extractApiCode, extractApiMessage } from "@/lib/apiError";
import type { OnboardingTemplateResponseDTO } from "@/features/project-management/dto/responseDTO/onboardingTemplate.response";
import type {
  ConsoleMembership,
  ConsolePolicy,
  ConsoleProject,
  ConsoleProjectDetail,
  ConsoleSection,
  ConsoleUser,
  ConsoleUserDetail,
  AdminPriorityUser,
  AdminRiskItem,
  AdminUnassignedUser,
  MembershipBulkResult,
  MembershipEligibility,
  MembershipOffboardingPreview,
  MembershipSummary,
  Overview,
  PageMeta,
  PolicyContent,
  PolicyCoverage,
  PolicyCoverageDetail,
  PolicyDetail,
  PolicyInspectResult,
  PolicyUploadFields,
  UserDeactivationPreview,
  UserImportPreview,
  UserImportResult,
} from "./types";

type Page<T> = { items: T[]; meta: PageMeta };

export class ConsoleApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
  ) {
    super(message);
    this.name = "ConsoleApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  return requestAt<T>(`${CONSOLE_ENDPOINT}${path}`, init);
}

/** Như `request` nhưng nhận URL tuyệt đối, để gọi được router ngoài prefix /console. */
async function requestAt<T>(url: string, init?: RequestInit): Promise<T> {
  const storedUserId =
    typeof window === "undefined"
      ? null
      : window.localStorage.getItem("ralion-demo-user-id")?.trim();
  // A blank or malformed value can remain after an interrupted demo login.  In that
  // case use the configured development Admin context rather than sending an
  // invalid X-User-Id header and leaving the console permanently in a loading/error state.
  const signedInUserId = storedUserId && /^\d+$/.test(storedUserId) ? storedUserId : null;
  // Với FormData phải để trình duyệt tự đặt Content-Type — nó cần thêm boundary vào
  // multipart/form-data. Tự đặt header sẽ khiến server không tách được các phần.
  const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData;
  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      // The signed session cookie is the real credential; the X-User-Id header below is
      // only the development fallback and is ignored by the API whenever a cookie exists.
      credentials: "include",
      headers: {
        ...(isFormData ? {} : { "Content-Type": "application/json" }),
        "X-User-Id": signedInUserId ?? CONSOLE_DEMO_USER_ID,
        ...init?.headers,
      },
    });
  } catch {
    throw new ConsoleApiError(
      "Không thể kết nối tới máy chủ. Vui lòng kiểm tra kết nối và thử lại.",
      0,
      "NETWORK_ERROR",
    );
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ConsoleApiError(
      extractApiMessage(body?.detail, "Console data could not be loaded."),
      response.status,
      extractApiCode(body?.detail),
    );
  }
  return response.json() as Promise<T>;
}

export const consoleApi = {
  overview: () => request<Overview>("/admin/overview"),
  masterTemplate: () => request<OnboardingTemplateResponseDTO>("/admin/master-template"),
  priorityUsers: () => request<{ items: AdminPriorityUser[] }>("/admin/priority-users"),
  riskItems: (limit = 20) =>
    request<{ items: AdminRiskItem[]; total: number }>(`/admin/risk-items?limit=${limit}`),
  unassignedUsers: (params: URLSearchParams) =>
    request<Page<AdminUnassignedUser>>(`/admin/unassigned-users?${params}`),
  users: (params: URLSearchParams) => request<Page<ConsoleUser>>(`/admin/users?${params}`),
  userDetail: (id: number) => request<ConsoleUserDetail>(`/admin/users/${id}`),
  projects: (params: URLSearchParams) => request<Page<ConsoleProject>>(`/admin/projects?${params}`),
  projectDetail: (id: number) => request<ConsoleProjectDetail>(`/admin/projects/${id}`),
  updateProject: (id: number, body: { name?: string; key?: string }) =>
    request<ConsoleProjectDetail>(`/admin/projects/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  /**
   * Trỏ dự án sang một repo GitHub thật.
   *
   * Cố ý gọi endpoint sẵn có của nhóm TV1 (`/knowledge-documents/pm/projects/...`) thay
   * vì viết một endpoint thứ hai trong console: hai đường ghi cùng một cột là cách chắc
   * chắn để chúng trôi ra khác nhau. Admin đi qua được `require_project_member` nên
   * không cần nới quyền.
   */
  connectGithubRepo: (projectId: number, githubRepo: string, defaultBranch: string) =>
    requestAt<ConsoleProjectDetail>(
      `${API_BASE_URL}/api/v1/knowledge-documents/pm/projects/${projectId}/github-repo`,
      {
        method: "PATCH",
        body: JSON.stringify({ github_repo: githubRepo, default_branch: defaultBranch }),
      },
    ),
  setPrimaryPm: (id: number, membershipId: number | null) =>
    request<ConsoleProjectDetail>(`/admin/projects/${id}/primary-pm`, {
      method: "PATCH",
      body: JSON.stringify({ membership_id: membershipId }),
    }),
  memberships: (params: URLSearchParams) =>
    request<Page<ConsoleMembership>>(`/admin/memberships?${params}`),
  membershipSummary: () => request<MembershipSummary>("/admin/memberships/summary"),
  createMembershipsBulk: (body: {
    project_id: number;
    project_role: "PM" | "ENGINEER";
    user_ids: number[];
  }) =>
    request<MembershipBulkResult>("/admin/memberships/bulk", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  policies: (params: URLSearchParams) => request<Page<ConsolePolicy>>(`/hr/policies?${params}`),
  policy: (id: number) => request<PolicyDetail>(`/hr/policies/${id}`),
  // Bước 1: đọc file, trả metadata gợi ý. Chưa ghi gì vào database.
  inspectPolicyFile: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<PolicyInspectResult>("/hr/policies/inspect", { method: "POST", body: form });
  },
  // Bước 2: ingest thật. Tạo mới hay thêm phiên bản đều dùng endpoint này —
  // backend tự phân biệt qua document_code.
  uploadPolicy: (file: File, fields: PolicyUploadFields) => {
    const form = new FormData();
    form.append("file", file);
    form.append("document_code", fields.document_code);
    form.append("title", fields.title);
    form.append("policy_category", fields.policy_category);
    if (fields.version) form.append("version", fields.version);
    if (fields.effective_date) form.append("effective_date", fields.effective_date);
    return request<PolicyDetail>("/hr/policies/upload", { method: "POST", body: form });
  },
  policyContent: (id: number) => request<PolicyContent>(`/hr/policies/${id}/content`),
  policyCoverage: () => request<{ items: PolicyCoverage[] }>("/hr/policies/coverage"),
  policyCoverageDetail: (id: number) =>
    request<PolicyCoverageDetail>(`/hr/policies/${id}/coverage`),
  setPolicyAckRequired: (id: number, required: boolean) =>
    request<PolicyCoverageDetail>(`/hr/policies/${id}/acknowledgement-required`, {
      method: "PATCH",
      body: JSON.stringify({ required }),
    }),
  archivePolicy: (id: number) =>
    request<PolicyDetail>(`/hr/policies/${id}/archive`, {
      method: "PATCH",
      body: JSON.stringify({}),
    }),
  restorePolicy: (id: number) =>
    request<PolicyDetail>(`/hr/policies/${id}/restore`, {
      method: "PATCH",
      body: JSON.stringify({}),
    }),
  previewUserImport: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<UserImportPreview>("/admin/users/import/preview", {
      method: "POST",
      body: form,
    });
  },
  importUsers: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<UserImportResult>("/admin/users/import", { method: "POST", body: form });
  },
  createUser: (body: object) =>
    request<ConsoleUser>("/admin/users", { method: "POST", body: JSON.stringify(body) }),
  createProject: (body: object) =>
    request<ConsoleProject>("/admin/projects", { method: "POST", body: JSON.stringify(body) }),
  createMembership: (body: object) =>
    request<ConsoleMembership>("/admin/memberships", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  membershipEligibility: (projectId?: number) =>
    request<MembershipEligibility>(
      projectId === undefined
        ? "/admin/memberships/eligibility"
        : `/admin/memberships/eligibility?project_id=${projectId}`,
    ),
  updateUser: (id: number, body: object) =>
    request<ConsoleUserDetail>(`/admin/users/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  resetUserPassword: (id: number, newPassword: string) =>
    request<ConsoleUser>(`/admin/users/${id}/password`, {
      method: "PATCH",
      body: JSON.stringify({ new_password: newPassword }),
    }),
  changeUserStatus: (id: number, status: "ACTIVE" | "INACTIVE") =>
    request<ConsoleUser>(`/admin/users/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  changeProjectStatus: (id: number, status: "ACTIVE" | "ARCHIVED", deactivateMemberships = false) =>
    request<ConsoleProjectDetail>(`/admin/projects/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status, deactivate_memberships: deactivateMemberships }),
    }),
  updateMembership: (id: number, body: object) =>
    request<ConsoleMembership>(`/admin/memberships/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  revokeMembershipAccess: (membershipId: number) =>
    request<{ items: unknown[] }>(`/admin/memberships/${membershipId}/revoke-access`, {
      method: "POST",
    }),
  deactivationPreview: (userId: number) =>
    request<UserDeactivationPreview>(`/admin/users/${userId}/deactivation-preview`),
  membershipOffboardingPreview: (membershipId: number) =>
    request<MembershipOffboardingPreview>(`/admin/memberships/${membershipId}/offboarding-preview`),
};

export function fetchSection(section: ConsoleSection, params: URLSearchParams) {
  if (section === "users") return consoleApi.users(params);
  if (section === "projects") return consoleApi.projects(params);
  if (section === "memberships") return consoleApi.memberships(params);
  if (section === "policies") return consoleApi.policies(params);
  return consoleApi.overview();
}
