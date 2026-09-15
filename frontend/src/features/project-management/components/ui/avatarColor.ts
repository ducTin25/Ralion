/** Bảng màu avatar cố định (đồng nhất cho mọi user/project) — chọn xoay vòng theo hash chuỗi
 * (email/key), nên cùng 1 người/project luôn ra đúng 1 màu, không đổi giữa các lần render. */
const AVATAR_PALETTE = [
  "#2657D9",
  "#5C8DF6",
  "#157F53",
  "#A8660A",
  "#7A6BA8",
  "#3F7A75",
  "#B04E72",
];

function hashString(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i++) {
    hash = (hash * 31 + value.charCodeAt(i)) >>> 0;
  }
  return hash;
}

export function avatarColorFor(seed: string): string {
  return AVATAR_PALETTE[hashString(seed) % AVATAR_PALETTE.length];
}

/** Lấy 1-2 chữ cái đầu để hiện trong avatar vuông (vd "Nguyen Van A" -> "NA", "PHONESHOP" -> "PH"). */
export function initialsFor(value: string, maxLetters = 2): string {
  const parts = value.trim().split(/\s+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
  return value.slice(0, maxLetters).toUpperCase();
}
