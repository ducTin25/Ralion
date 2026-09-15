/**
 * Backend trả `datetime` dạng chuỗi ISO KHÔNG có offset (vd `"2026-08-19T02:47:00"`) — con số đó
 * thực chất là giờ UTC (xem `src/services/plan_generation/steps.py`: dùng
 * `datetime.now(UTC).replace(tzinfo=None)` xuyên suốt cả dự án), nhưng theo spec ES2015+,
 * `new Date()` hiểu 1 chuỗi ISO không-offset là giờ LOCAL của trình duyệt, không phải UTC. PM ở
 * Việt Nam (UTC+7) nên nếu không sửa, giờ hiển thị lệch 7 tiếng so với thực tế (đúng lỗi PM báo
 * cáo: "hạn 02:47" thay vì 09:47 thật).
 *
 * Không đổi cách backend lưu/trả `datetime` — naive-UTC là convention xuyên suốt cả dự án, ngoài
 * phạm vi lần sửa này. Chỉ sửa tầng hiển thị: ép hiểu chuỗi là UTC (thêm "Z" nếu chưa có offset),
 * rồi format tường minh theo giờ Việt Nam — không phụ thuộc múi giờ hệ thống máy PM đang dùng.
 */
export function parseBackendDateTime(value: string): Date {
  const hasOffset = /Z$|[+-]\d{2}:\d{2}$/.test(value);
  return new Date(hasOffset ? value : `${value}Z`);
}

const VIETNAM_TIME_ZONE = "Asia/Ho_Chi_Minh";

/** Ngày + giờ đầy đủ, đúng giờ Việt Nam. Dùng cho mọi nơi hiện `due_at`/`start_at` của PlanTask. */
export function formatDateTime(
  value: string | null,
  options?: Intl.DateTimeFormatOptions,
  locale = "vi-VN",
): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat(locale, {
    timeZone: VIETNAM_TIME_ZONE,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    ...options,
  }).format(parseBackendDateTime(value));
}

/** Chỉ ngày/tháng (không giờ, không năm) — chỗ nào chỉ cần hiển thị gọn thì dùng bản này thay vì
 * gọi `formatDateTime` rồi lược field, tránh phải nhớ đúng bộ option ở nhiều nơi gọi. */
export function formatDateOnly(value: string | null): string {
  return formatDateTime(value, { year: undefined, hour: undefined, minute: undefined });
}

// Việt Nam không có giờ mùa hè (DST) — offset cố định quanh năm, nên cộng/trừ 7 tiếng bằng số học
// thuần là đủ chính xác, không cần thư viện timezone (dự án chưa có sẵn date-fns-tz/Luxon).
const VIETNAM_UTC_OFFSET_MINUTES = 7 * 60;

/** `<input type="datetime-local">` cho ra chuỗi "YYYY-MM-DDTHH:MM" KHÔNG timezone — PM luôn gõ
 * theo Ý ĐỊNH giờ Việt Nam (đối tượng duy nhất dùng app), bất kể múi giờ hệ điều hành máy PM có
 * đúng hay không. Đọc thẳng các số trong chuỗi bằng tay (KHÔNG qua `new Date(string)`, vì cách đó
 * sẽ hiểu theo múi giờ OS — đúng lỗ hổng gây ra bug hiển thị lệch giờ ban đầu), rồi trừ 7 tiếng để
 * ra chuỗi UTC không-offset đúng quy ước backend đang lưu cho `due_at`.
 */
export function vietnamLocalInputToBackendString(datetimeLocalValue: string): string | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(datetimeLocalValue);
  if (!match) return null;
  const [year, month, day, hour, minute] = match.slice(1).map(Number);
  const utcMs =
    Date.UTC(year, month - 1, day, hour, minute) - VIETNAM_UTC_OFFSET_MINUTES * 60 * 1000;
  return new Date(utcMs).toISOString().slice(0, 19);
}

/** Chiều ngược lại — pre-fill `<input type="datetime-local">` từ giá trị `due_at` backend trả về
 * (chuỗi UTC không-offset), ra đúng chuỗi "YYYY-MM-DDTHH:MM" theo giờ Việt Nam để PM nhìn thấy và
 * sửa đúng con số họ mong đợi, không phải giờ UTC thô.
 */
export function backendStringToVietnamLocalInput(value: string | null): string {
  if (!value) return "";
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(value);
  if (!match) return "";
  const [year, month, day, hour, minute] = match.slice(1).map(Number);
  const localMs =
    Date.UTC(year, month - 1, day, hour, minute) + VIETNAM_UTC_OFFSET_MINUTES * 60 * 1000;
  return new Date(localMs).toISOString().slice(0, 16);
}

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

/** Đọc giờ HIỆN TẠI theo Việt Nam (không phụ thuộc múi giờ OS máy đang chạy — dùng `Intl` với
 * `timeZone` tường minh) thành các số nguyên rời, để tính toán ngày làm việc bằng số học thuần. */
function currentVietnamParts(now: Date): {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
} {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: VIETNAM_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23", // ép 0-23, tránh "24:00" mà hour12:false có thể trả cho đúng nửa đêm
  }).formatToParts(now);
  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? 0);
  return {
    year: get("year"),
    month: get("month"),
    day: get("day"),
    hour: get("hour"),
    minute: get("minute"),
  };
}

/** Dựng `Date` bằng `Date.UTC` từ các số Y-M-D THEO LỊCH VIỆT NAM (không phải UTC thật) — chỉ để
 * mượn `getUTCDay()` tính đúng thứ trong tuần bằng số học, không liên quan gì đến giờ UTC thật. */
function calendarDate(year: number, month: number, day: number): Date {
  return new Date(Date.UTC(year, month - 1, day));
}

/** Giờ đề xuất mặc định cho modal "Chọn giờ bắt đầu" khi PM bấm Sinh plan: nếu đang trong giờ hành
 * chính (09:00-17:00, Thứ 2 - Thứ 6, giờ Việt Nam) thì dùng luôn giờ hiện tại; ngoài khung đó thì
 * nhảy tới 09:00 của ngày làm việc kế tiếp (bỏ qua Thứ 7/Chủ nhật) — PM bấm nút lúc nửa đêm hay
 * cuối tuần không nên khiến lịch của kỹ sư bắt đầu ngay lúc đó.
 *
 * Nhận `now` làm tham số (mặc định giờ thật) để test được deterministic, không phụ thuộc đồng hồ
 * hệ thống lúc chạy test.
 */
export function recommendedPlanStartVietnamLocal(now: Date = new Date()): string {
  const { year, month, day, hour, minute } = currentVietnamParts(now);
  const weekday = calendarDate(year, month, day).getUTCDay(); // 0=CN .. 6=T7
  const isWeekday = weekday >= 1 && weekday <= 5;

  if (isWeekday && hour >= 9 && hour < 17) {
    return `${year}-${pad2(month)}-${pad2(day)}T${pad2(hour)}:${pad2(minute)}`;
  }

  // Còn trong ngày làm việc nhưng đến quá sớm (trước 09:00) -> dùng luôn hôm nay, không cần nhảy.
  if (isWeekday && hour < 9) {
    return `${year}-${pad2(month)}-${pad2(day)}T09:00`;
  }

  // Mọi ca còn lại (sau 17:00 ngày thường, hoặc bất kỳ giờ nào của T7/CN) -> nhảy sang ngày làm
  // việc kế tiếp, bỏ qua cuối tuần.
  let cursor = new Date(calendarDate(year, month, day).getTime() + 24 * 60 * 60 * 1000);
  while (cursor.getUTCDay() === 0 || cursor.getUTCDay() === 6) {
    cursor = new Date(cursor.getTime() + 24 * 60 * 60 * 1000);
  }
  return `${cursor.getUTCFullYear()}-${pad2(cursor.getUTCMonth() + 1)}-${pad2(cursor.getUTCDate())}T09:00`;
}
