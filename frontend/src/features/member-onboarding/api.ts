import type {
  BlockerCategory,
  MemberPolicyContent,
  PendingPolicy,
  PolicyAcknowledgement,
  MemberBlocker,
  MemberChecklist,
  MemberProjects,
  MemberTaskDetail,
  TaskNotification,
  TaskStatus,
} from "@/features/member-onboarding/types";
import { API_BASE_URL, MY_POLICIES_ENDPOINT, requestJson } from "@/lib/api";

const MEMBER_ENDPOINT = `${API_BASE_URL}/api/v1/member`;

export async function listMemberProjects(
  signal?: AbortSignal,
  init: RequestInit = {},
): Promise<MemberProjects> {
  return requestJson<MemberProjects>(`${MEMBER_ENDPOINT}/projects`, { ...init, signal });
}

export async function getMemberChecklist(
  projectId: number,
  signal?: AbortSignal,
  init: RequestInit = {},
): Promise<MemberChecklist> {
  return requestJson<MemberChecklist>(`${MEMBER_ENDPOINT}/checklist?project_id=${projectId}`, {
    ...init,
    signal,
  });
}

export async function getMemberTask(
  taskId: number,
  signal?: AbortSignal,
  init: RequestInit = {},
): Promise<MemberTaskDetail> {
  return requestJson<MemberTaskDetail>(`${MEMBER_ENDPOINT}/plan-tasks/${taskId}`, {
    ...init,
    signal,
  });
}

export async function updateMemberTaskStatus(
  taskId: number,
  status: Extract<TaskStatus, "IN_PROGRESS" | "DONE">,
): Promise<MemberTaskDetail> {
  return requestJson<MemberTaskDetail>(`${MEMBER_ENDPOINT}/plan-tasks/${taskId}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
}

export async function listMemberNotifications(
  projectId: number,
  signal?: AbortSignal,
  init: RequestInit = {},
): Promise<TaskNotification[]> {
  return requestJson<TaskNotification[]>(`${MEMBER_ENDPOINT}/notifications?project_id=${projectId}`, {
    ...init,
    signal,
  });
}

export async function listMemberBlockers(
  projectId: number,
  signal?: AbortSignal,
  init: RequestInit = {},
): Promise<MemberBlocker[]> {
  return requestJson<MemberBlocker[]>(`${MEMBER_ENDPOINT}/blockers?project_id=${projectId}`, {
    ...init,
    signal,
  });
}

export async function createMemberBlocker(
  taskId: number,
  payload: { category: BlockerCategory; reason: string; attachments: File[] },
): Promise<MemberBlocker> {
  // multipart/form-data (không phải JSON): backend cần nhận file minh chứng cùng lúc với
  // category/lý do trong 1 request (UC-08). KHÔNG tự đặt header Content-Type — trình duyệt phải tự
  // sinh boundary cho multipart, đặt tay sẽ làm request hỏng.
  const form = new FormData();
  form.append("category", payload.category);
  form.append("reason", payload.reason);
  for (const file of payload.attachments) form.append("attachments", file);

  return requestJson<MemberBlocker>(`${MEMBER_ENDPOINT}/plan-tasks/${taskId}/blockers`, {
    method: "POST",
    body: form,
  });
}

export async function listPendingPolicies(
  signal?: AbortSignal,
  init: RequestInit = {},
): Promise<{ items: PendingPolicy[] }> {
  return requestJson<{ items: PendingPolicy[] }>(MY_POLICIES_ENDPOINT, { ...init, signal });
}

export async function getMemberPolicyContent(
  documentId: number,
  signal?: AbortSignal,
  init: RequestInit = {},
): Promise<MemberPolicyContent> {
  return requestJson<MemberPolicyContent>(`${MY_POLICIES_ENDPOINT}/${documentId}/content`, {
    ...init,
    signal,
  });
}

export async function acknowledgePolicy(documentId: number): Promise<PolicyAcknowledgement> {
  return requestJson<PolicyAcknowledgement>(`${MY_POLICIES_ENDPOINT}/${documentId}/acknowledge`, {
    method: "POST",
  });
}
