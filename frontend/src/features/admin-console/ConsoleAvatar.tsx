/**
 * Avatar chữ cái cho Admin/HR console.
 *
 * Trước đây ba panel tự định nghĩa `Avatar` riêng với ba kích thước và ba màu khác
 * nhau, nên cùng một người trông khác nhau ở mỗi tab. Gom về một chỗ để bảng nào cũng
 * đọc ra cùng một khuôn mặt.
 *
 * Màu suy ra từ tên: cùng tên luôn cho cùng màu, kể cả sau khi tải lại trang hay đổi
 * trang phân trang. Random hoặc theo index sẽ khiến avatar nhảy màu mỗi lần render.
 */

/** Bảng màu đủ tương phản với chữ trắng (tỉ lệ tương phản >= 4.5:1). */
const PALETTE = [
  "#2563eb", // blue
  "#7c3aed", // violet
  "#0f766e", // teal
  "#b45309", // amber
  "#be123c", // rose
  "#15803d", // green
  "#4338ca", // indigo
  "#a21caf", // fuchsia
];

export function initials(name: string) {
  return (
    name
      .trim()
      .split(/\s+/)
      .slice(-2)
      .map((part) => part[0] ?? "")
      .join("")
      .toUpperCase() || "?"
  );
}

function colorFor(name: string) {
  // Hàm băm đơn giản, tất định. Không cần chống va chạm — trùng màu chỉ là hai người
  // cùng sắc, không phải lỗi.
  let hash = 0;
  for (let index = 0; index < name.length; index += 1) {
    hash = (hash * 31 + name.charCodeAt(index)) % 100000;
  }
  return PALETTE[hash % PALETTE.length];
}

export function ConsoleAvatar({
  name,
  size = 34,
  muted = false,
}: {
  name: string;
  size?: number;
  /** Làm mờ khi dòng đang ở trạng thái bị chặn hoặc đã ngừng. */
  muted?: boolean;
}) {
  return (
    <span
      aria-hidden="true"
      style={{
        width: size,
        height: size,
        background: muted ? "var(--color-surface-3)" : colorFor(name),
        fontSize: Math.round(size * 0.36),
      }}
      className={`flex shrink-0 items-center justify-center rounded-full font-semibold ${
        muted ? "text-text-subtle" : "text-white"
      }`}
    >
      {initials(name)}
    </span>
  );
}
