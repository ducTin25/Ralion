/**
 * "Đã xem" cho dropdown chuông thông báo (PM + Member Portal) — thuần phía client, không có bảng
 * Notification/đã đọc-chưa đọc ở backend (xem notification_response_dto.py). Bấm vào 1 thông báo
 * để mở task thì đồng thời đánh dấu "đã xem" — chỉ ẩn khỏi badge/màu, không đổi trạng thái task.
 *
 * Key theo cả `plan_task_id` LẪN `due_at`: nếu due_at đổi (PM sửa hạn, hoặc task cũ trôi qua rồi
 * có task mới trùng id do dữ liệu demo bị xoá/tạo lại) thì coi như thông báo MỚI, không bị giấu
 * nhầm bởi lần "đã xem" của due_at cũ.
 */

const STORAGE_PREFIX = "ralion-dismissed-notifications";
export const NOTIFICATION_DISMISSAL_CHANGED_EVENT = "ralion:notification-dismissal-changed";

function storageKey(scope: string, userId: number, projectId: number): string {
  return `${STORAGE_PREFIX}:${scope}:${userId}:${projectId}`;
}

function itemKey(planTaskId: number, dueAt: string): string {
  return `${planTaskId}:${dueAt}`;
}

export function loadDismissedNotifications(
  scope: string,
  userId: number,
  projectId: number,
): Set<string> {
  try {
    const raw = window.localStorage.getItem(storageKey(scope, userId, projectId));
    if (!raw) return new Set();
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed)
      ? new Set(parsed.filter((v): v is string => typeof v === "string"))
      : new Set();
  } catch {
    // localStorage có thể bị chặn (chế độ riêng tư nghiêm ngặt) — coi như chưa xem gì, không phải
    // lỗi chặn luồng chính.
    return new Set();
  }
}

export function dismissNotification(
  scope: string,
  userId: number,
  projectId: number,
  planTaskId: number,
  dueAt: string,
): Set<string> {
  const current = loadDismissedNotifications(scope, userId, projectId);
  current.add(itemKey(planTaskId, dueAt));
  try {
    window.localStorage.setItem(
      storageKey(scope, userId, projectId),
      JSON.stringify(Array.from(current)),
    );
  } catch {
    // best-effort, xem ghi chú ở loadDismissedNotifications
  }
  window.dispatchEvent(new CustomEvent(NOTIFICATION_DISMISSAL_CHANGED_EVENT));
  return current;
}

export function isNotificationDismissed(
  dismissed: Set<string>,
  planTaskId: number,
  dueAt: string,
): boolean {
  return dismissed.has(itemKey(planTaskId, dueAt));
}
