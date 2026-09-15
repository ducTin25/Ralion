import { MY_ACCESS_ENDPOINT } from "@/lib/api";
import { extractApiCode, extractApiMessage } from "@/lib/apiError";

export type MyAccessGrant = {
  grant_id: number;
  resource_type: string;
  // Nhãn tiếng Việt do server tính sẵn — không map lại ở client.
  resource_label: string;
  resource_note: string | null;
  status: "REQUESTED" | "GRANTED" | "REVOKED";
  requested_at: string;
  granted_at: string | null;
  granted_by_name: string | null;
  project_name: string | null;
  project_key: string | null;
  is_overdue: boolean;
  waiting_hours: number | null;
};

export class MyAccessError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
  ) {
    super(message);
    this.name = "MyAccessError";
  }
}

export const myAccessApi = {
  /** Quyền của chính người đang đăng nhập. Không nhận user_id — danh tính lấy từ phiên. */
  list: async (): Promise<{ items: MyAccessGrant[] }> => {
    const response = await fetch(MY_ACCESS_ENDPOINT, {
      credentials: "include",
      headers: { "Content-Type": "application/json" },
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new MyAccessError(
        extractApiMessage(body?.detail, "Không tải được danh sách quyền truy cập."),
        response.status,
        extractApiCode(body?.detail),
      );
    }
    return response.json();
  },
};
