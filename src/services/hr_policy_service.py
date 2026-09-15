"""Adapter giữa màn hình HR và pipeline ingestion của TV3.

Toàn bộ nghiệp vụ nặng (parse version, tạo document/version, chunk, embedding, archive,
activate) nằm trong `ingest_policy_document()` của TV3 và KHÔNG được viết lại ở đây.
Module này chỉ làm bốn việc thuộc trách nhiệm TV4:

1. Kiểm tra định dạng và kích thước file
2. Convert sang markdown + chuẩn hoá header
3. Lưu file gốc lên object storage
4. Dịch lỗi kỹ thuật của TV3 thành thông báo tiếng Việt cho HR

Việc thứ tư quan trọng hơn vẻ ngoài: TV3 ném `ValueError` với thông điệp tiếng Anh dành
cho lập trình viên. Nếu để nguyên, HR nhìn thấy chuỗi không hiểu được và không biết phải
sửa gì trong tài liệu.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.providers.embeddings import Embedder
from src.dto.admin_console_dto import PolicyDetailDTO
from src.model.enums import PolicyCategory
from src.model.knowledge_document import KnowledgeDocument
from src.model.user import User
from src.modules.knowledge.policy_ingestion import PolicyIngestRequest
from src.services import admin_console_service, document_conversion_service, storage_service
from src.services.document_conversion_service import DocumentConversionError

POLICY_STORAGE_FOLDER = "policies"


class PolicyIngestor(Protocol):
    """Chữ ký của `ingest_policy_document` — tách ra để test tiêm bản giả.

    Cần thiết vì hàm thật dùng `pg_advisory_xact_lock`, chỉ có trên PostgreSQL, nên
    test chạy SQLite không gọi được. Test của TV4 kiểm tra phần TV4 chịu trách nhiệm;
    phần ingest thật do TV3 tự test trên PostgreSQL.
    """

    async def __call__(
        self,
        session: AsyncSession,
        request: PolicyIngestRequest,
        embedder: Embedder,
        *,
        config: dict | None = None,
    ) -> KnowledgeDocument: ...


def _translate_ingest_error(message: str) -> tuple[int, str, str]:
    """Ánh xạ ValueError của TV3 sang (HTTP status, mã lỗi, thông báo tiếng Việt)."""
    lowered = message.lower()

    if "already exists with a different checksum" in lowered:
        return (
            409,
            "VERSION_CONTENT_MISMATCH",
            "Số phiên bản này đã tồn tại với nội dung khác. "
            "Hãy tăng số phiên bản trong tài liệu trước khi tải lên.",
        )
    # So khớp trên chuỗi đã lower — thông điệp gốc viết hoa "Phiên bản".
    if "missing" in lowered and "phiên bản" in lowered:
        return (
            422,
            "MISSING_VERSION_HEADER",
            "Không đọc được số phiên bản trong tài liệu. Vui lòng nhập thủ công.",
        )
    if "unsupported effective date" in lowered:
        return (
            422,
            "INVALID_EFFECTIVE_DATE",
            "Ngày hiệu lực phải theo định dạng DD/MM/YYYY.",
        )
    if "content must not be empty" in lowered:
        return (
            422,
            "EMPTY_CONTENT",
            "Không trích xuất được nội dung từ file. File có thể là ảnh scan chưa OCR.",
        )
    if "document_code must not be empty" in lowered:
        return (422, "MISSING_DOCUMENT_CODE", "Vui lòng nhập mã tài liệu.")
    if "must be normalized" in lowered:
        return (
            500,
            "EMBEDDING_CONFIG_ERROR",
            "Cấu hình embedding không hợp lệ. Vui lòng báo quản trị viên.",
        )
    if "vector count" in lowered:
        return (
            500,
            "EMBEDDING_FAILED",
            "Xử lý nội dung tài liệu thất bại. Vui lòng thử lại.",
        )

    # Lỗi chưa biết: giữ nguyên thông điệp gốc để còn debug được, nhưng bọc trong câu
    # tiếng Việt để HR biết đây là lỗi hệ thống chứ không phải họ làm sai.
    return (422, "INGESTION_FAILED", f"Không xử lý được tài liệu: {message}")


async def inspect_upload(
    content: bytes, filename: str, *, max_mb: int
) -> document_conversion_service.ConvertedDocument:
    """Bước 1 của luồng: đọc file, trả metadata gợi ý cho HR xác nhận. Chưa ghi gì."""
    try:
        document_conversion_service.validate_upload(filename, len(content), max_mb=max_mb)
        return document_conversion_service.inspect(content, filename)
    except DocumentConversionError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "FILE_NOT_READABLE", "message": str(exc)}
        ) from exc


async def find_existing_document(db: AsyncSession, document_code: str) -> KnowledgeDocument | None:
    """Tìm chính sách đã có theo mã, để UI báo trước 'đây sẽ là phiên bản mới'."""
    from sqlalchemy import select

    from src.model.enums import DocumentDomain
    from src.modules.knowledge.policy_metadata import normalize_policy_source_key

    try:
        source_key = normalize_policy_source_key(document_code)
    except ValueError:
        return None
    return await db.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.knowledge_domain == DocumentDomain.POLICY,
            KnowledgeDocument.source_key == source_key,
        )
    )


async def upload_policy(
    db: AsyncSession,
    actor: User,
    *,
    content: bytes,
    filename: str,
    document_code: str,
    title: str,
    policy_category: PolicyCategory,
    version: str | None,
    effective_date: date | None,
    embedder: Embedder,
    ingest: PolicyIngestor,
    max_mb: int,
) -> PolicyDetailDTO:
    """Bước 2: convert, lưu file gốc, bàn giao cho pipeline của TV3.

    `version` và `effective_date` chỉ dùng khi tài liệu thiếu header — khi đó chúng được
    chèn vào markdown để TV3 parse được. Nếu tài liệu đã có header hợp lệ thì giá trị
    trong tài liệu được ưu tiên.
    """
    try:
        document_conversion_service.validate_upload(filename, len(content), max_mb=max_mb)
        markdown = document_conversion_service.convert_to_markdown(content, filename)
    except DocumentConversionError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "FILE_NOT_READABLE", "message": str(exc)}
        ) from exc

    if not document_code.strip():
        raise HTTPException(
            status_code=422,
            detail={"code": "MISSING_DOCUMENT_CODE", "message": "Vui lòng nhập mã tài liệu."},
        )

    # Chuẩn hoá header trước khi giao cho TV3. Xem docstring của ensure_policy_header.
    if version and effective_date:
        markdown = document_conversion_service.ensure_policy_header(
            markdown, version=version, effective_date=effective_date
        )

    # Lưu FILE GỐC (không phải markdown) — HR cần tải lại đúng bản PDF/DOCX đã duyệt.
    try:
        source_url = storage_service.upload_document_bytes(content, POLICY_STORAGE_FOLDER, filename)
    except Exception as exc:  # pragma: no cover - phụ thuộc dịch vụ ngoài
        raise HTTPException(
            status_code=502,
            detail={
                "code": "STORAGE_UNAVAILABLE",
                "message": "Không lưu được file lên kho tài liệu. Vui lòng thử lại.",
            },
        ) from exc

    request = PolicyIngestRequest(
        title=title.strip(),
        content=markdown,
        document_code=document_code.strip(),
        policy_category=policy_category,
        created_by_user_id=actor.user_id,
        source_url=source_url,
    )

    try:
        document = await ingest(db, request, embedder)
    except ValueError as exc:
        await db.rollback()
        status_code, code, message = _translate_ingest_error(str(exc))
        raise HTTPException(status_code=status_code, detail={"code": code, "message": message}) from exc

    return await admin_console_service.get_policy_detail(db, document.document_id)
