/**
 * Shared API configuration cho FastAPI backend.
 */

const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]", "::1"]);

/**
 * Địa chỉ backend. Mặc định là rỗng, tức gọi API theo **cùng origin** với trang đang mở.
 *
 * Cookie phiên gắn với host của backend nên hostname phải khớp với trang, nếu không mọi
 * lời gọi là cross-site và `SameSite=Lax` khiến trình duyệt bỏ luôn cookie backend vừa
 * trả về: đăng nhập trả 200 nhưng không có phiên, rồi middleware đá ngược về /login —
 * trông hệt như "bấm đăng nhập mà không vào được". Đường dẫn tương đối tránh hẳn chuyện
 * đó; rewrite `/api/:path*` trong `next.config.ts` chuyển tiếp tới backend thật.
 *
 * `NEXT_PUBLIC_API_URL` vẫn được tôn trọng cho trường hợp gọi backend trực tiếp (e2e
 * Playwright trỏ sang cổng riêng). Khi đó, nếu cả API lẫn trang đều là địa chỉ loopback
 * thì lấy hostname theo trang đang mở, vì trình duyệt coi `localhost` và `127.0.0.1` là
 * hai site khác nhau (cổng thì không tính).
 */
function resolveApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (!configured) return "";
  if (typeof window === "undefined") return configured;
  try {
    const url = new URL(configured);
    if (LOOPBACK_HOSTS.has(url.hostname) && LOOPBACK_HOSTS.has(window.location.hostname)) {
      url.hostname = window.location.hostname;
      return url.origin;
    }
  } catch {
    // NEXT_PUBLIC_API_URL không phải URL hợp lệ — giữ nguyên để lỗi lộ ra rõ ràng.
  }
  return configured;
}

export const API_BASE_URL = resolveApiBaseUrl();

export const CHAT_ENDPOINT = `${API_BASE_URL}/api/v1/chat`;
export const CHAT_CONVERSATIONS_ENDPOINT = `${API_BASE_URL}/api/v1/chat/conversations`;
export const EMBEDDING_WARMUP_ENDPOINT = `${CHAT_ENDPOINT}/warmup`;
export const MEMBERSHIPS_ENDPOINT = `${API_BASE_URL}/api/v1/me/memberships?status=ACTIVE`;
export const ACTIVE_MEMBERSHIP_ENDPOINT = `${API_BASE_URL}/api/v1/me/active-membership`;
export const CONSOLE_ENDPOINT = `${API_BASE_URL}/api/v1/console`;
export const MY_POLICIES_ENDPOINT = `${API_BASE_URL}/api/v1/me/policies`;
export const MY_ACCESS_ENDPOINT = `${API_BASE_URL}/api/v1/me/access-grants`;
export const AUTH_ENDPOINT = `${API_BASE_URL}/api/v1/auth`;
export const DEMO_USER_ID = process.env.NEXT_PUBLIC_DEMO_USER_ID ?? "1";
export const CONSOLE_DEMO_USER_ID = process.env.NEXT_PUBLIC_CONSOLE_DEMO_USER_ID ?? "1";

export const USERS_ENDPOINT = `${API_BASE_URL}/api/v1/users`;
export const PM_PROJECTS_ENDPOINT = `${API_BASE_URL}/api/v1/projects/pm`;
export const PM_PROJECT_MEMBERSHIPS_ENDPOINT = `${API_BASE_URL}/api/v1/project-memberships/pm`;
export const PM_PROJECT_SCOPED_ENDPOINT = `${API_BASE_URL}/api/v1/pm/projects`;
export const PM_BLOCKERS_ENDPOINT = `${API_BASE_URL}/api/v1/pm/projects`;
export const PM_ONBOARDING_PLANS_ENDPOINT = `${API_BASE_URL}/api/v1/onboarding-plans/pm`;
export const PM_ONBOARDING_TEMPLATES_ENDPOINT = `${API_BASE_URL}/api/v1/onboarding-templates/pm`;
export const PM_TEMPLATE_VERSIONS_ENDPOINT = `${API_BASE_URL}/api/v1/template-versions/pm`;
export const PM_TEMPLATE_TASKS_ENDPOINT = `${API_BASE_URL}/api/v1/template-tasks/pm`;
export const PM_TASK_DEPENDENCIES_ENDPOINT = `${API_BASE_URL}/api/v1/task-dependencies/pm`;
export const PM_PLAN_TASKS_ENDPOINT = `${API_BASE_URL}/api/v1/plan-tasks/pm`;
export const KNOWLEDGE_DOCUMENTS_ENDPOINT = `${API_BASE_URL}/api/v1/knowledge-documents`;
export const PM_KNOWLEDGE_DOCUMENTS_ENDPOINT = `${API_BASE_URL}/api/v1/knowledge-documents/pm`;

/** F6 Rule Mining — PM Review Queue routes are project-scoped under `PM_PROJECT_SCOPED_ENDPOINT`
 * (`/pm/projects/{id}/rule-candidates/...`, see features/conventions/api.ts). `CONVENTIONS_ENDPOINT`
 * stays company-wide on purpose — it's what the chat Member Conventions panel reads. */
export const CONVENTIONS_ENDPOINT = `${API_BASE_URL}/api/v1/conventions`;
export const PROJECT_CONVENTIONS_ENDPOINT = `${API_BASE_URL}/api/v1/projects`;

/**
 * Router Phase 4 (`onboarding_plan_router.py`/`plan_task_router.py`) chưa được đưa vào PR auth của
 * ducTin25 (không nằm trong danh sách file auth-gate) nên vẫn nhận `approved_by_user_id` tường
 * minh từ body thay vì tự suy từ session — tạm giữ hằng số này cho tới khi 2 router đó cũng được
 * gắn `get_current_user`. Không dùng cho endpoint nào khác đã có auth thật.
 */
export const CURRENT_PM_USER_ID = 21;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly detail: unknown = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function parseJsonOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    const message =
      typeof detail?.detail === "string" ? detail.detail : `Request failed: ${response.status}`;
    throw new ApiError(response.status, message, detail);
  }
  return response.json() as Promise<T>;
}

type RequestJsonOptions = {
  timeoutMs?: number;
};

async function requestJson<T>(
  input: RequestInfo | URL,
  init: RequestInit = {},
  { timeoutMs = 12_000 }: RequestJsonOptions = {},
): Promise<T> {
  const controller = new AbortController();
  let timedOut = false;
  const abortFromCaller = () => controller.abort(init.signal?.reason);
  if (init.signal?.aborted) abortFromCaller();
  else init.signal?.addEventListener("abort", abortFromCaller, { once: true });
  const timeout = globalThis.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  try {
    return await parseJsonOrThrow<T>(
      await fetch(input, {
        ...init,
        credentials: init.credentials ?? "include",
        signal: controller.signal,
      }),
    );
  } catch (error) {
    if (timedOut) throw new ApiError(408, "The request timed out. Please try again.");
    throw error;
  } finally {
    globalThis.clearTimeout(timeout);
    init.signal?.removeEventListener("abort", abortFromCaller);
  }
}

export { parseJsonOrThrow, requestJson };
