import { MY_POLICIES_ENDPOINT } from "@/lib/api";
import { extractApiCode, extractApiMessage } from "@/lib/apiError";

export type PendingPolicy = {
  document_id: number;
  title: string;
  policy_category: string;
  version_no: string | null;
  effective_date: string | null;
  // True = đã xác nhận một phiên bản cũ hơn của chính tài liệu này.
  is_new_version: boolean;
};

export type PolicyContent = {
  document_id: number;
  title: string;
  policy_category: string;
  version_no: string;
  effective_date: string | null;
  content: string;
  source_url: string;
};

export class PolicyApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
  ) {
    super(message);
    this.name = "PolicyApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${MY_POLICIES_ENDPOINT}${path}`, {
    ...init,
    // Cookie phiên là thông tin xác thực duy nhất ở đây — không có đường tắt header
    // như phía console, vì endpoint này dành cho người dùng thật.
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new PolicyApiError(
      extractApiMessage(body?.detail, "Không thể tải dữ liệu chính sách."),
      response.status,
      extractApiCode(body?.detail),
    );
  }
  return response.json() as Promise<T>;
}

export const policyApi = {
  pending: () => request<{ items: PendingPolicy[] }>(""),
  content: (documentId: number) => request<PolicyContent>(`/${documentId}/content`),
  acknowledge: (documentId: number) =>
    request<{ document_id: number; already_acknowledged: boolean }>(`/${documentId}/acknowledge`, {
      method: "POST",
    }),
};
