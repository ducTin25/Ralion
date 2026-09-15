/** Lọc file ứng viên NGAY Ở CLIENT trước khi upload — khớp đúng rule phía server
 * (src/services/repo_scanner_service.py `is_candidate_file`). Nhờ lọc trước, PM chọn nguyên folder
 * to (kể cả node_modules/.git bên trong) vẫn nhẹ — chỉ vài chục file tài liệu thật sự được đọc
 * bytes và đẩy lên mạng, không phải upload hết rồi mới lọc. */

const CANDIDATE_EXTENSIONS = new Set([".md", ".txt", ".pdf", ".docx"]);
const EXCLUDED_DIR_NAMES = new Set([
  ".git",
  "node_modules",
  "dist",
  "build",
  ".next",
  "__pycache__",
  ".venv",
]);
const SENSITIVE_NAME_KEYWORDS = ["secret", "token", "password"];
const SENSITIVE_EXTENSIONS = new Set([".pem", ".key"]);

function getExtension(filename: string): string {
  const dot = filename.lastIndexOf(".");
  return dot === -1 ? "" : filename.slice(dot).toLowerCase();
}

export function isCandidateFile(relativePath: string): boolean {
  const parts = relativePath.split("/");
  const filename = parts[parts.length - 1] ?? relativePath;
  const extension = getExtension(filename);

  if (!CANDIDATE_EXTENSIONS.has(extension)) return false;
  if (parts.slice(0, -1).some((part) => EXCLUDED_DIR_NAMES.has(part))) return false;

  const lower = filename.toLowerCase();
  if (lower === ".env") return false;
  if (SENSITIVE_EXTENSIONS.has(extension)) return false;
  if (SENSITIVE_NAME_KEYWORDS.some((keyword) => lower.includes(keyword))) return false;

  return true;
}

export function getFileRelativePath(file: File): string {
  return (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
}

/** Filter large folder selections in batches so React can keep painting progress UI. */
export async function filterCandidateFilesInBatches(
  files: ArrayLike<File>,
  onProgress?: (processed: number) => void,
  batchSize = 1_000,
): Promise<File[]> {
  const candidates: File[] = [];
  const safeBatchSize = Math.max(1, batchSize);
  for (let start = 0; start < files.length; start += safeBatchSize) {
    const end = Math.min(start + safeBatchSize, files.length);
    for (let index = start; index < end; index += 1) {
      const file = files[index];
      if (file && isCandidateFile(getFileRelativePath(file))) candidates.push(file);
    }
    onProgress?.(end);
    if (end < files.length) {
      await new Promise<void>((resolve) => globalThis.setTimeout(resolve, 0));
    }
  }
  return candidates;
}
