import type { ProjectResponseDTO } from "@/features/project-management/dto/responseDTO/project.response";
import type { ProjectMembershipDetailResponseDTO } from "@/features/project-management/dto/responseDTO/projectMembership.response";
import type { OnboardingPlanResponseDTO } from "@/features/project-management/dto/responseDTO/onboardingPlan.response";
import type { PlanGenerationJobResponseDTO } from "@/features/project-management/dto/responseDTO/planGenerationJob.response";
import type { PlanTaskResponseDTO } from "@/features/project-management/dto/responseDTO/planTask.response";
import type { OnboardingTemplateResponseDTO } from "@/features/project-management/dto/responseDTO/onboardingTemplate.response";
import type { KnowledgeDocumentResponseDTO } from "@/features/project-management/dto/responseDTO/knowledgeDocument.response";
import type {
  DocumentCategory,
  ProjectDocumentContentResponseDTO,
  ProjectDocumentResponseDTO,
} from "@/features/project-management/dto/responseDTO/document.response";
import type { CoverageReportResponseDTO } from "@/features/project-management/dto/responseDTO/repoScan.response";
import type { TaskDependencyResponseDTO } from "@/features/project-management/dto/responseDTO/taskDependency.response";
import type { PmBlockerResponseDTO } from "@/features/project-management/dto/responseDTO/blocker.response";
import type { PmMemberProgressResponseDTO } from "@/features/project-management/dto/responseDTO/pmProgress.response";
import type { PmDashboardResponseDTO } from "@/features/project-management/dto/responseDTO/pmDashboard.response";
import type { TaskNotificationResponseDTO } from "@/features/project-management/dto/responseDTO/notification.response";
import type {
  DiscoveryScheduleResponseDTO,
  DiscoveryScheduleUpdateInput,
  IngestionJobResponseDTO,
} from "@/features/project-management/dto/responseDTO/discoverySchedule.response";
import type {
  TaskCategory,
  TemplateTaskResponseDTO,
} from "@/features/project-management/dto/responseDTO/templateTask.response";
import type { TemplateVersionResponseDTO } from "@/features/project-management/dto/responseDTO/templateVersion.response";
import type { UserResponseDTO } from "@/features/project-management/dto/responseDTO/user.response";
import { authHeaders } from "@/features/auth/session";
import type { MembershipCard } from "@/types/project";
import {
  CURRENT_PM_USER_ID,
  KNOWLEDGE_DOCUMENTS_ENDPOINT,
  MEMBERSHIPS_ENDPOINT,
  PM_KNOWLEDGE_DOCUMENTS_ENDPOINT,
  PM_PROJECT_SCOPED_ENDPOINT,
  PM_ONBOARDING_PLANS_ENDPOINT,
  PM_ONBOARDING_TEMPLATES_ENDPOINT,
  PM_PLAN_TASKS_ENDPOINT,
  PM_PROJECTS_ENDPOINT,
  PM_PROJECT_MEMBERSHIPS_ENDPOINT,
  PM_TASK_DEPENDENCIES_ENDPOINT,
  PM_TEMPLATE_TASKS_ENDPOINT,
  PM_TEMPLATE_VERSIONS_ENDPOINT,
  USERS_ENDPOINT,
  parseJsonOrThrow,
} from "@/lib/api";

function authenticatedFetch(input: RequestInfo | URL, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  for (const [name, value] of Object.entries(authHeaders())) {
    if (!headers.has(name)) headers.set(name, String(value));
  }
  return fetch(input, {
    ...init,
    credentials: "include",
    headers,
  });
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  return parseJsonOrThrow<T>(
    await authenticatedFetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

async function patchJson<T>(url: string, body?: unknown): Promise<T> {
  return parseJsonOrThrow<T>(
    await authenticatedFetch(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  );
}

async function putJson<T>(url: string, body: unknown): Promise<T> {
  return parseJsonOrThrow<T>(
    await authenticatedFetch(url, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

async function postMultipart<T>(url: string, formData: FormData): Promise<T> {
  return parseJsonOrThrow<T>(await authenticatedFetch(url, { method: "POST", body: formData }));
}

async function deleteRequest(url: string): Promise<void> {
  const response = await authenticatedFetch(url, { method: "DELETE" });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? `Request failed: ${response.status}`);
  }
}

/**
 * Danh sách project mà 1 PM đang quản lý (lọc project_role=PM phía client, join Project detail).
 * PM chỉ XEM danh sách này — tạo project thuộc về Admin, không có action tạo ở đây.
 */
export async function listProjectsManagedByPm(signal?: AbortSignal): Promise<ProjectResponseDTO[]> {
  const memberships = await parseJsonOrThrow<MembershipCard[]>(
    await authenticatedFetch(MEMBERSHIPS_ENDPOINT, { signal }),
  );
  const pmProjectIds = memberships
    .filter((membership) => membership.projectRole === "PM")
    .map((membership) => membership.projectId);
  const projects = await Promise.all(
    pmProjectIds.map(async (id) =>
      parseJsonOrThrow<ProjectResponseDTO>(
        await authenticatedFetch(`${PM_PROJECTS_ENDPOINT}/${id}`, { signal }),
      ),
    ),
  );
  return projects;
}

/**
 * Thành viên của 1 project — PM chỉ XEM, không thêm/xoá/khoá (Admin quản lý việc đó).
 */
export async function listProjectMembers(
  projectId: number,
  signal?: AbortSignal,
): Promise<ProjectMembershipDetailResponseDTO[]> {
  const response = await authenticatedFetch(
    `${PM_PROJECT_MEMBERSHIPS_ENDPOINT}?project_id=${projectId}`,
    { signal },
  );
  return parseJsonOrThrow<ProjectMembershipDetailResponseDTO[]>(response);
}

/** Blocker do Engineer báo trong project — PM chỉ xem blocker thuộc project mình quản lý. */
export async function listProjectBlockers(
  projectId: number,
  signal?: AbortSignal,
): Promise<PmBlockerResponseDTO[]> {
  const response = await authenticatedFetch(`${PM_PROJECT_SCOPED_ENDPOINT}/${projectId}/blockers`, {
    signal,
  });
  return parseJsonOrThrow<PmBlockerResponseDTO[]>(response);
}

/** PM xác nhận blocker đã được xử lý; thao tác idempotent ở backend. */
export async function resolveProjectBlocker(
  projectId: number,
  blockerId: number,
): Promise<PmBlockerResponseDTO> {
  return patchJson<PmBlockerResponseDTO>(
    `${PM_PROJECT_SCOPED_ENDPOINT}/${projectId}/blockers/${blockerId}/resolve`,
  );
}

/** Tiến độ (task/quá hạn/blocker) của ĐÚNG 1 Engineer — SoT §17.2. */
export async function getMemberProgress(
  projectId: number,
  membershipId: number,
  signal?: AbortSignal,
): Promise<PmMemberProgressResponseDTO> {
  const response = await authenticatedFetch(
    `${PM_PROJECT_SCOPED_ENDPOINT}/${projectId}/members/${membershipId}/progress`,
    { signal },
  );
  return parseJsonOrThrow<PmMemberProgressResponseDTO>(response);
}

/** Trang "Tổng quan" — tổng hợp tiến độ toàn dự án. */
export async function getProjectDashboard(
  projectId: number,
  signal?: AbortSignal,
): Promise<PmDashboardResponseDTO> {
  const response = await authenticatedFetch(
    `${PM_PROJECT_SCOPED_ENDPOINT}/${projectId}/dashboard`,
    {
      signal,
    },
  );
  return parseJsonOrThrow<PmDashboardResponseDTO>(response);
}

/** Task sắp/đã trễ hạn của mọi Engineer trong dự án, cho dropdown chuông thông báo PM. */
export async function getProjectNotifications(
  projectId: number,
  signal?: AbortSignal,
): Promise<TaskNotificationResponseDTO[]> {
  const response = await authenticatedFetch(
    `${PM_PROJECT_SCOPED_ENDPOINT}/${projectId}/notifications`,
    { signal },
  );
  return parseJsonOrThrow<TaskNotificationResponseDTO[]>(response);
}

/** Toàn bộ Plan của các thành viên trong 1 project — FE tự map theo membership_id. */
export async function listOnboardingPlansByProject(
  projectId: number,
): Promise<OnboardingPlanResponseDTO[]> {
  const response = await authenticatedFetch(
    `${PM_ONBOARDING_PLANS_ENDPOINT}/by-project/${projectId}`,
  );
  return parseJsonOrThrow<OnboardingPlanResponseDTO[]>(response);
}

// ---- Phase 4: sinh / duyệt Candidate Plan ----

/** Bắt đầu sinh Candidate Plan. Trả về NGAY (202) kèm job_id — pipeline chạy nền, FE poll tiến độ
 * bằng `getPlanGenerationJob`. Không đợi ở đây vì bước gọi LLM mất ~30s. */
export async function startPlanGeneration(
  membershipId: number,
  startAt?: string,
): Promise<PlanGenerationJobResponseDTO> {
  return postJson<PlanGenerationJobResponseDTO>(`${PM_ONBOARDING_PLANS_ENDPOINT}/generate`, {
    membership_id: membershipId,
    start_at: startAt ?? null,
  });
}

/** Plan "chuẩn" của project — bản đầu tiên từng sinh, dùng làm nguồn sao chép cho mọi kỹ sư sau.
 *
 * Trả `null` thay vì throw khi 404: "project chưa có plan nào" là trạng thái HỢP LỆ (dự án mới),
 * không phải lỗi — khác với các hàm còn lại trong file này. */
export async function getReferencePlan(
  projectId: number,
): Promise<OnboardingPlanResponseDTO | null> {
  const response = await fetch(`${PM_ONBOARDING_PLANS_ENDPOINT}/reference?project_id=${projectId}`);
  if (response.status === 404) return null;
  return parseJsonOrThrow<OnboardingPlanResponseDTO>(response);
}

/** Sinh (hoặc tạo lại) lộ trình CHUẨN của dự án — bước duy nhất gọi AI, mất ~30s.
 * Đã có bản chuẩn thì ghi đè tại chỗ. Không đụng plan đã cấp cho kỹ sư. */
export async function startReferencePlanGeneration(
  projectId: number,
): Promise<PlanGenerationJobResponseDTO> {
  return postJson<PlanGenerationJobResponseDTO>(
    `${PM_ONBOARDING_PLANS_ENDPOINT}/reference/generate`,
    { project_id: projectId },
  );
}

/** Sinh lại nội dung trên chính plan cũ — chỉ được khi plan còn DRAFT (backend chặn, trả 409). */
export async function regeneratePlan(planId: number): Promise<PlanGenerationJobResponseDTO> {
  return postJson<PlanGenerationJobResponseDTO>(
    `${PM_ONBOARDING_PLANS_ENDPOINT}/${planId}/regenerate`,
    {},
  );
}

export async function getPlanGenerationJob(jobId: string): Promise<PlanGenerationJobResponseDTO> {
  const response = await fetch(`${PM_ONBOARDING_PLANS_ENDPOINT}/generate/${jobId}`);
  return parseJsonOrThrow<PlanGenerationJobResponseDTO>(response);
}

export async function listPlanTasks(planId: number): Promise<PlanTaskResponseDTO[]> {
  const response = await fetch(`${PM_ONBOARDING_PLANS_ENDPOINT}/${planId}/tasks`);
  return parseJsonOrThrow<PlanTaskResponseDTO[]>(response);
}

/** Router hiện tại vẫn yêu cầu identity người duyệt trong body. */
export async function approvePlan(planId: number): Promise<OnboardingPlanResponseDTO> {
  return patchJson<OnboardingPlanResponseDTO>(`${PM_ONBOARDING_PLANS_ENDPOINT}/${planId}/approve`, {
    approved_by_user_id: CURRENT_PM_USER_ID,
  });
}

/** PM sửa tay 1 task khi plan còn Nháp. */
export async function updatePlanTask(
  planTaskId: number,
  payload: { title?: string; instruction?: string },
): Promise<PlanTaskResponseDTO> {
  return patchJson<PlanTaskResponseDTO>(`${PM_PLAN_TASKS_ENDPOINT}/${planTaskId}`, payload);
}

/** Lấy thông tin 1 user — dùng để hiện đúng tên/email PM đang đăng nhập ở sidebar footer. */
export async function getUserById(userId: number): Promise<UserResponseDTO> {
  const response = await fetch(`${USERS_ENDPOINT}/${userId}`);
  return parseJsonOrThrow<UserResponseDTO>(response);
}

// ---- Master Template (Phase 2) ----
// Mỗi project tạo sau Phase 2 đã tự có sẵn 1 Project Template (fork từ Global Master Template)
// ngay lúc tạo. Project cũ hơn (tạo trước Phase 2) có thể chưa có — createOnboardingTemplateForProject
// dùng đúng API backfill đã có sẵn (xem OnboardingTemplateCreateRequestDTO) thay vì tạo flow riêng.

/** Template hiện có của 1 project — 404 nếu project chưa có Master Template (project cũ, xem
 * createOnboardingTemplateForProject). */
export async function getTemplateByProject(
  projectId: number,
): Promise<OnboardingTemplateResponseDTO> {
  const response = await authenticatedFetch(
    `${PM_ONBOARDING_TEMPLATES_ENDPOINT}/by-project/${projectId}`,
  );
  return parseJsonOrThrow<OnboardingTemplateResponseDTO>(response);
}

/** Backfill Master Template cho project chưa có (404 ở getTemplateByProject). Yêu cầu đã tồn tại
 * 1 Global Master Template APPROVED — backend trả 422 nếu chưa, PM không tự sửa được điều đó. */
export async function createOnboardingTemplateForProject(
  projectId: number,
): Promise<OnboardingTemplateResponseDTO> {
  return postJson<OnboardingTemplateResponseDTO>(PM_ONBOARDING_TEMPLATES_ENDPOINT, {
    project_id: projectId,
  });
}

/** Lịch sử version của 1 template — mới nhất trước. */
export async function listTemplateVersions(
  templateId: number,
): Promise<TemplateVersionResponseDTO[]> {
  const response = await authenticatedFetch(
    `${PM_TEMPLATE_VERSIONS_ENDPOINT}/by-template/${templateId}`,
  );
  return parseJsonOrThrow<TemplateVersionResponseDTO[]>(response);
}

/** Tạo version mới (DRAFT) — mặc định sao chép toàn bộ task/dependency từ 1 version nguồn. */
export async function createTemplateVersion(
  templateId: number,
  cloneFromVersionId?: number,
): Promise<TemplateVersionResponseDTO> {
  return postJson<TemplateVersionResponseDTO>(PM_TEMPLATE_VERSIONS_ENDPOINT, {
    template_id: templateId,
    clone_from_version_id: cloneFromVersionId ?? null,
  });
}

/** Duyệt 1 version — chuyển DRAFT -> APPROVED, tự archive version đang APPROVED trước đó (nếu có). */
export async function approveTemplateVersion(
  versionId: number,
): Promise<TemplateVersionResponseDTO> {
  return patchJson<TemplateVersionResponseDTO>(
    `${PM_TEMPLATE_VERSIONS_ENDPOINT}/${versionId}/approve`,
  );
}

/** Task của 1 version, đã sắp theo display_order. */
export async function listTemplateTasks(versionId: number): Promise<TemplateTaskResponseDTO[]> {
  const response = await authenticatedFetch(
    `${PM_TEMPLATE_TASKS_ENDPOINT}/by-version/${versionId}`,
  );
  return parseJsonOrThrow<TemplateTaskResponseDTO[]>(response);
}

export type TemplateTaskFormInput = {
  category: TaskCategory;
  title_pattern: string;
  objective: string;
  instruction_template: string;
  mandatory: boolean;
  estimated_minutes: number;
};

/** Thêm task mới vào cuối 1 version — chỉ cho phép khi version đang DRAFT (409 nếu không). */
export async function createTemplateTask(
  versionId: number,
  input: TemplateTaskFormInput,
): Promise<TemplateTaskResponseDTO> {
  return postJson<TemplateTaskResponseDTO>(PM_TEMPLATE_TASKS_ENDPOINT, {
    version_id: versionId,
    ...input,
  });
}

/** Sửa 1 task — chỉ cho phép khi version đang DRAFT (409 nếu không). */
export async function updateTemplateTask(
  templateTaskId: number,
  input: Partial<TemplateTaskFormInput>,
): Promise<TemplateTaskResponseDTO> {
  return patchJson<TemplateTaskResponseDTO>(
    `${PM_TEMPLATE_TASKS_ENDPOINT}/${templateTaskId}`,
    input,
  );
}

/** Xoá hẳn (hard-delete) 1 task — chỉ cho phép khi version đang DRAFT (409 nếu không). */
export async function deleteTemplateTask(templateTaskId: number): Promise<void> {
  return deleteRequest(`${PM_TEMPLATE_TASKS_ENDPOINT}/${templateTaskId}`);
}

/** Cập nhật lại display_order hàng loạt theo thứ tự mới (kéo-thả/nút lên-xuống). */
export async function reorderTemplateTasks(
  versionId: number,
  orderedTemplateTaskIds: number[],
): Promise<TemplateTaskResponseDTO[]> {
  return patchJson<TemplateTaskResponseDTO[]>(`${PM_TEMPLATE_TASKS_ENDPOINT}/reorder`, {
    version_id: versionId,
    ordered_template_task_ids: orderedTemplateTaskIds,
  });
}

/** Dependency của 1 version (join qua template_tasks phía backend). */
export async function listTaskDependencies(
  versionId: number,
): Promise<TaskDependencyResponseDTO[]> {
  const response = await authenticatedFetch(
    `${PM_TASK_DEPENDENCIES_ENDPOINT}/by-version/${versionId}`,
  );
  return parseJsonOrThrow<TaskDependencyResponseDTO[]>(response);
}

/** Tạo dependency predecessor -> successor — backend tự chặn cùng-version/tự-tham-chiếu/cycle. */
export async function createTaskDependency(
  predecessorTaskId: number,
  successorTaskId: number,
): Promise<TaskDependencyResponseDTO> {
  return postJson<TaskDependencyResponseDTO>(PM_TASK_DEPENDENCIES_ENDPOINT, {
    predecessor_task_id: predecessorTaskId,
    successor_task_id: successorTaskId,
  });
}

export async function deleteTaskDependency(dependencyId: number): Promise<void> {
  return deleteRequest(`${PM_TASK_DEPENDENCIES_ENDPOINT}/${dependencyId}`);
}

// ---- Company Core (chính sách công ty — chỉ đọc, PM không sửa) ----

/** Tài liệu chính sách công ty (domain POLICY) — dùng chung mọi project, không gắn version. */
export async function listPolicyDocuments(): Promise<KnowledgeDocumentResponseDTO[]> {
  const response = await authenticatedFetch(`${KNOWLEDGE_DOCUMENTS_ENDPOINT}/policy`);
  return parseJsonOrThrow<KnowledgeDocumentResponseDTO[]>(response);
}

// ---- Project Documents (Phase 3 — UC-04) ----
// Version import xong ACTIVE ngay (TV3 đã nối chunk+activate vào luồng import). Xem
// docs/PM/Phase-4/plan-fix-onboarding-plan-quality.md mục 0 và 3.1.

export async function listProjectDocuments(
  projectId: number,
): Promise<ProjectDocumentResponseDTO[]> {
  const response = await authenticatedFetch(
    `${PM_KNOWLEDGE_DOCUMENTS_ENDPOINT}/projects/${projectId}`,
  );
  return parseJsonOrThrow<ProjectDocumentResponseDTO[]>(response);
}

/** Nội dung tài liệu để PM đọc ngay trong app (markdown đã chuẩn hoá cho mọi định dạng nguồn). */
export async function getProjectDocumentContent(
  projectId: number,
  documentId: number,
): Promise<ProjectDocumentContentResponseDTO> {
  const response = await authenticatedFetch(
    `${PM_KNOWLEDGE_DOCUMENTS_ENDPOINT}/projects/${projectId}/${documentId}/content`,
  );
  return parseJsonOrThrow<ProjectDocumentContentResponseDTO>(response);
}

export async function deleteProjectDocument(projectId: number, documentId: number): Promise<void> {
  return deleteRequest(`${PM_KNOWLEDGE_DOCUMENTS_ENDPOINT}/projects/${projectId}/${documentId}`);
}

/** Upload 1 file đơn lẻ — dùng khi Coverage Report báo MISSING 1 category hoặc tài liệu nằm ngoài
 * repository. */
export async function uploadProjectDocument(
  projectId: number,
  input: { category: DocumentCategory; title: string; file: File },
): Promise<ProjectDocumentResponseDTO> {
  const formData = new FormData();
  formData.append("category", input.category);
  formData.append("title", input.title);
  formData.append("file", input.file);
  return postMultipart<ProjectDocumentResponseDTO>(
    `${PM_KNOWLEDGE_DOCUMENTS_ENDPOINT}/projects/${projectId}/upload`,
    formData,
  );
}

export function uploadProjectDocumentWithProgress(
  projectId: number,
  input: { category: DocumentCategory; title: string; file: File },
  onProgress: (percent: number) => void,
): Promise<ProjectDocumentResponseDTO> {
  const formData = new FormData();
  formData.append("category", input.category);
  formData.append("title", input.title);
  formData.append("file", input.file);

  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${PM_KNOWLEDGE_DOCUMENTS_ENDPOINT}/projects/${projectId}/upload`);
    request.withCredentials = true;
    for (const [name, value] of Object.entries(authHeaders())) {
      request.setRequestHeader(name, String(value));
    }
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    request.onerror = () => reject(new Error("Network error"));
    request.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(request.responseText);
      } catch {
        // Preserve the HTTP status fallback below when the proxy returns a non-JSON response.
      }
      if (request.status >= 200 && request.status < 300) {
        resolve(body as ProjectDocumentResponseDTO);
        return;
      }
      const detail = body as { detail?: string } | null;
      reject(new Error(detail?.detail ?? `Request failed: ${request.status}`));
    };
    request.send(formData);
  });
}

/** PM xác nhận hoặc sửa lại nhóm cho 1 tài liệu dự án — dùng cho cả 2 trường hợp: tài liệu
 * AMBIGUOUS (classifier của GitHub sync không đủ tin cậy để tự xếp nhóm, xem
 * `project_category_classifier.py`) lẫn tài liệu đã CLASSIFIED nhưng PM phát hiện sai và muốn
 * đổi lại sau. Backend chỉ ghi đè metadata (không re-embed/re-chunk). */
export async function confirmProjectDocumentCategory(
  projectId: number,
  documentId: number,
  category: DocumentCategory,
): Promise<ProjectDocumentResponseDTO> {
  return patchJson<ProjectDocumentResponseDTO>(
    `${PM_KNOWLEDGE_DOCUMENTS_ENDPOINT}/projects/${projectId}/${documentId}/category`,
    { category },
  );
}

/** Trỏ project sang 1 repo GitHub thật kèm 1 Personal Access Token do PM cung cấp, thay
 * `pending/<key>` gán lúc tạo project — bước bắt buộc trước khi gọi được `syncProjectFromGithub`.
 * Backend validate token bằng 1 lệnh gọi GitHub thật trước khi lưu (mã hoá tại rest); token
 * không bao giờ được trả lại trong response. */
export async function connectGithubRepo(
  projectId: number,
  githubRepo: string,
  defaultBranch: string,
  githubToken: string,
): Promise<ProjectResponseDTO> {
  return patchJson<ProjectResponseDTO>(
    `${PM_KNOWLEDGE_DOCUMENTS_ENDPOINT}/projects/${projectId}/github-repo`,
    { github_repo: githubRepo, default_branch: defaultBranch, github_token: githubToken },
  );
}

/** Xếp hàng đồng bộ tài liệu dự án từ GitHub. API trả 202 ngay; UI poll trạng thái để không giữ
 * một kết nối proxy dài trong suốt quá trình download, ingest và embedding. */
export async function syncProjectFromGithub(projectId: number): Promise<ProjectResponseDTO> {
  return postJson<ProjectResponseDTO>(
    `${PM_KNOWLEDGE_DOCUMENTS_ENDPOINT}/projects/${projectId}/github-sync`,
    {},
  );
}

/** Quét folder PM chọn (đã lọc client-side trước, xem RepoScanWizard) — không ghi DB, chỉ trả
 * Coverage Report để PM duyệt trước khi Approve & Import. */
export async function scanRepository(
  projectId: number,
  files: File[],
): Promise<CoverageReportResponseDTO> {
  const formData = new FormData();
  for (const file of files) {
    const relativePath = (file as File & { webkitRelativePath?: string }).webkitRelativePath;
    formData.append("files", file, relativePath || file.name);
  }
  return postMultipart<CoverageReportResponseDTO>(
    `${PM_KNOWLEDGE_DOCUMENTS_ENDPOINT}/projects/${projectId}/scan`,
    formData,
  );
}

export async function getGithubSyncStatus(projectId: number): Promise<ProjectResponseDTO> {
  const response = await authenticatedFetch(
    `${PM_KNOWLEDGE_DOCUMENTS_ENDPOINT}/projects/${projectId}/github-sync`,
  );
  return parseJsonOrThrow<ProjectResponseDTO>(response);
}

// ---- F6 Scheduled Incremental Convention Discovery ----
// No field here ever carries model/concurrency/embedding-batch/cosine-threshold/retry-policy —
// the backend DTO simply has no such field (CLAUDE.md F6 playbook §5).

/** F6 Scheduled Incremental Convention Discovery — cadence per project (CLAUDE.md Phase 6). */
export async function getDiscoverySchedule(
  projectId: number,
): Promise<DiscoveryScheduleResponseDTO> {
  const response = await authenticatedFetch(
    `${PM_PROJECT_SCOPED_ENDPOINT}/${projectId}/discovery-schedule`,
  );
  return parseJsonOrThrow<DiscoveryScheduleResponseDTO>(response);
}

export async function updateDiscoverySchedule(
  projectId: number,
  input: DiscoveryScheduleUpdateInput,
): Promise<DiscoveryScheduleResponseDTO> {
  return putJson<DiscoveryScheduleResponseDTO>(
    `${PM_PROJECT_SCOPED_ENDPOINT}/${projectId}/discovery-schedule`,
    input,
  );
}

export async function runDiscoveryNow(projectId: number): Promise<DiscoveryScheduleResponseDTO> {
  return postJson<DiscoveryScheduleResponseDTO>(
    `${PM_PROJECT_SCOPED_ENDPOINT}/${projectId}/discovery-schedule/run-now`,
    {},
  );
}

export type ScanSelectionInput = {
  candidate_id: string;
  include: boolean;
  category: DocumentCategory;
  title?: string;
};

/** PM đã duyệt xong Coverage Report — ghi DB thật + upload Cloudinary cho các candidate được chọn. */
export async function importScanSelection(
  projectId: number,
  scanSessionId: string,
  selections: ScanSelectionInput[],
): Promise<IngestionJobResponseDTO> {
  return postJson<IngestionJobResponseDTO>(
    `${PM_KNOWLEDGE_DOCUMENTS_ENDPOINT}/projects/${projectId}/scan/${scanSessionId}/import`,
    { selections },
  );
}

export async function getScanImportStatus(
  projectId: number,
  jobId: number,
): Promise<IngestionJobResponseDTO> {
  const response = await authenticatedFetch(
    `${PM_KNOWLEDGE_DOCUMENTS_ENDPOINT}/projects/${projectId}/scan-import/${jobId}`,
  );
  return parseJsonOrThrow<IngestionJobResponseDTO>(response);
}
