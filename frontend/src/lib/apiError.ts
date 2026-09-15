/**
 * Rút thông báo lỗi đọc được từ body `detail` của FastAPI.
 *
 * FastAPI trả `detail` ở ba dạng khác nhau và mã cũ chỉ xử lý hai:
 *
 * 1. `{"detail": "Policy not found"}`            — chuỗi, do `HTTPException(detail=...)`
 * 2. `{"detail": {"code": ..., "message": ...}}` — dict, quy ước của TV4
 * 3. `{"detail": [{"type": "int_parsing", "msg": ...}]}` — MẢNG, lỗi validate 422
 *
 * Dạng 3 lọt qua `detail?.message ?? detail` và rơi vào constructor của Error, nơi mảng
 * bị ép kiểu thành chuỗi `"[object Object]"`. Người dùng nhìn thấy đúng chuỗi đó trên
 * màn hình và không suy ra được điều gì — kể cả lập trình viên.
 */
/**
 * FastAPI trả đúng chuỗi này khi URL không khớp route nào.
 *
 * Trên màn hình nó hiện thành "Not Found" — không sai, nhưng vô dụng: người đọc không
 * phân biệt được "tài liệu này không tồn tại" với "endpoint chưa có trên server".
 * Trong lúc phát triển, nguyên nhân gần như luôn là uvicorn chưa khởi động lại sau khi
 * thêm route mới.
 */
const FASTAPI_UNMATCHED_ROUTE = "Not Found";

export function extractApiMessage(detail: unknown, fallback: string): string {
  if (detail === FASTAPI_UNMATCHED_ROUTE) {
    return "This API was not found on the server. If you just updated the code, restart the backend.";
  }
  if (typeof detail === "string" && detail.trim() !== "") return detail;

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) =>
        item && typeof item === "object" && "msg" in item
          ? String((item as { msg: unknown }).msg)
          : null,
      )
      .filter((value): value is string => Boolean(value));
    if (messages.length > 0) return messages.join(". ");
    return fallback;
  }

  if (detail && typeof detail === "object") {
    const message = (detail as { message?: unknown }).message;
    if (typeof message === "string" && message.trim() !== "") return message;
  }

  return fallback;
}

/** Mã lỗi nghiệp vụ, chỉ có ở dạng dict theo quy ước của TV4. */
export function extractApiCode(detail: unknown): string | undefined {
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const code = (detail as { code?: unknown }).code;
    if (typeof code === "string") return code;
  }
  return undefined;
}
