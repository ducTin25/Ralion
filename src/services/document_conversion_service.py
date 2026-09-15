"""Chuyển file HR upload thành markdown mà pipeline của TV3 đọc được.

TV3 (`parse_policy_version_metadata`) yêu cầu markdown có đúng dòng header:

    - **Phiên bản:** 3.2 — Ngày hiệu lực: 01/01/2026

File `.md` viết tay thì đúng định dạng, nhưng convert từ PDF/DOCX thường làm mất `**`,
đổi gạch dài `—` thành gạch ngắn, hoặc tách dòng. Module này chịu trách nhiệm chuẩn hoá
lại trước khi gọi TV3 — nhờ vậy TV3 không phải nới lỏng regex và luồng ingest giữ nguyên.

Ranh giới: module này KHÔNG đụng tới database, embedding hay chunk. Chỉ xử lý byte → text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from src.modules.knowledge.policy_ingestion import parse_policy_header
from src.modules.knowledge.policy_metadata import parse_policy_version_metadata

SUPPORTED_EXTENSIONS = {".md", ".markdown", ".pdf", ".docx"}
MARKDOWN_EXTENSIONS = {".md", ".markdown"}
# `.txt` không có cú pháp markdown nhưng vẫn là văn bản thuần đọc được — pipeline chunk coi phần
# không khớp cú pháp là đoạn văn bình thường, nên chỉ cần decode là dùng được.
PLAIN_TEXT_EXTENSIONS = {".txt"}
# Tài liệu dự án (PROJECT) nhận thêm `.txt` so với chính sách HR (POLICY): repo thật hay có
# NOTES.txt/CHANGELOG.txt, còn văn bản chính sách thì không. Giữ 2 tập riêng để nới định dạng cho
# luồng này không âm thầm nới cả luồng HR.
PROJECT_SUPPORTED_EXTENSIONS = SUPPORTED_EXTENSIONS | PLAIN_TEXT_EXTENSIONS

# Các nhãn bullet có thể chứa mã tài liệu, theo thứ tự ưu tiên.
DOCUMENT_CODE_LABELS = ("mã tài liệu", "mã văn bản", "document code", "mã")
PREVIEW_LENGTH = 1200


class DocumentConversionError(Exception):
    """File không đọc được hoặc không hỗ trợ định dạng."""


@dataclass(frozen=True)
class ConvertedDocument:
    """Kết quả đọc file, dùng cho màn hình HR review trước khi ingest."""

    markdown: str
    detected_title: str | None
    detected_document_code: str | None
    detected_version: str | None
    detected_effective_date: date | None
    warnings: list[str]

    @property
    def has_valid_header(self) -> bool:
        return self.detected_version is not None and self.detected_effective_date is not None


def validate_upload(filename: str, size_bytes: int, *, max_mb: int) -> None:
    """Chặn sớm file sai định dạng hoặc quá lớn, trước khi tốn công đọc nội dung."""
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise DocumentConversionError(
            f"Định dạng {extension or 'không xác định'} không được hỗ trợ. Chỉ nhận: {supported}."
        )
    if size_bytes == 0:
        raise DocumentConversionError("File rỗng.")
    if size_bytes > max_mb * 1024 * 1024:
        raise DocumentConversionError(f"File vượt quá giới hạn {max_mb} MB.")


def convert_to_markdown(content: bytes, filename: str) -> str:
    """PDF/DOCX → markdown. File markdown/text trả về nguyên văn.

    Nhận diện theo ĐUÔI FILE, không đoán theo nội dung: chỉ định dạng văn bản mới được decode
    UTF-8, còn PDF/DOCX là nhị phân nên luôn đi qua markitdown. Đây là ranh giới quan trọng —
    decode thẳng file nhị phân sẽ hoặc ném UnicodeDecodeError, hoặc (với PDF ASCII) lọt qua và
    ingest nguyên cú pháp PDF làm "nội dung tài liệu".
    """
    extension = Path(filename).suffix.lower()
    if extension in MARKDOWN_EXTENSIONS or extension in PLAIN_TEXT_EXTENSIONS:
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DocumentConversionError(
                f"File {extension} không phải mã hoá UTF-8."
            ) from exc

    # markitdown xử lý cả PDF lẫn DOCX bằng một API, và giữ được heading — điều này
    # quan trọng vì chunk_policy_markdown() của TV3 chia chunk theo heading_path.
    try:
        from markitdown import MarkItDown
    except ImportError as exc:  # pragma: no cover - phụ thuộc môi trường
        raise DocumentConversionError(
            "Thiếu thư viện markitdown. Chạy: pip install -r requirements.txt"
        ) from exc

    import io

    try:
        result = MarkItDown().convert_stream(io.BytesIO(content), file_extension=extension)
    except Exception as exc:
        raise DocumentConversionError(f"Không đọc được nội dung file: {exc}") from exc

    markdown = (result.text_content or "").strip()
    if not markdown:
        raise DocumentConversionError(
            "Không trích xuất được nội dung. File có thể là ảnh scan chưa OCR."
        )
    return markdown


def _detect_document_code(header: dict[str, str]) -> str | None:
    for label in DOCUMENT_CODE_LABELS:
        value = header.get(label)
        if value:
            return value.strip()
    return None


def _detect_title(markdown: str) -> str | None:
    """Lấy heading cấp 1 đầu tiên làm tiêu đề gợi ý."""
    for line in markdown.splitlines():
        match = re.match(r"^#\s+(.+?)\s*$", line)
        if match:
            return match.group(1).strip()
    return None


def inspect(content: bytes, filename: str) -> ConvertedDocument:
    """Convert file và thử đọc metadata.

    KHÔNG ném lỗi khi thiếu header phiên bản — đó là trường hợp bình thường với PDF,
    và HR sẽ nhập tay ở màn hình review. Chỉ ném lỗi khi không đọc nổi nội dung.
    """
    markdown = convert_to_markdown(content, filename)
    warnings: list[str] = []

    try:
        version, effective_date = parse_policy_version_metadata(markdown)
    except ValueError:
        version, effective_date = None, None
        warnings.append(
            "Không đọc được số phiên bản và ngày hiệu lực trong tài liệu. Vui lòng nhập thủ công."
        )

    header = parse_policy_header(markdown)
    document_code = _detect_document_code(header)
    if document_code is None:
        warnings.append("Không đọc được mã tài liệu. Vui lòng nhập thủ công.")

    return ConvertedDocument(
        markdown=markdown,
        detected_title=_detect_title(markdown),
        detected_document_code=document_code,
        detected_version=version,
        detected_effective_date=effective_date,
        warnings=warnings,
    )


def ensure_policy_header(markdown: str, *, version: str, effective_date: date) -> str:
    """Chèn dòng header chuẩn nếu markdown chưa có, để TV3 parse được.

    Nếu markdown đã có header hợp lệ thì giữ nguyên — ưu tiên giá trị trong tài liệu gốc
    hơn giá trị HR gõ lại, tránh việc metadata lưu khác nội dung file.
    """
    try:
        parse_policy_version_metadata(markdown)
        return markdown
    except ValueError:
        pass

    header_line = f"- **Phiên bản:** {version} — Ngày hiệu lực: {effective_date:%d/%m/%Y}"
    return f"{header_line}\n\n{markdown}"


def preview(markdown: str, *, length: int = PREVIEW_LENGTH) -> str:
    """Đoạn đầu markdown cho HR kiểm tra chất lượng convert."""
    if len(markdown) <= length:
        return markdown
    return markdown[:length] + "\n\n… (còn tiếp)"
