"""Upload file tài liệu (bytes) lên Cloudinary — tách từ logic đã dùng trong
scripts/upload_sample_docs_to_cloudinary.py để tái dùng cho endpoint upload/scan-import thật của
Phase 3. Vẫn dùng resource_type="raw" + public secure_url giống Company Core hiện có (chưa có
Auth nên chưa làm signed URL — xem docs/PM/Phase-3/plan-phase3-documents.md mục Quyết định #2)."""

import cloudinary
import cloudinary.uploader

from src.config import get_settings


def upload_document_bytes(content: bytes, project_slug: str, filename: str) -> str:
    settings = get_settings()
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
    )
    result = cloudinary.uploader.upload(
        content,
        resource_type="raw",
        folder=f"knowledge-documents/{project_slug}",
        public_id=filename,
        overwrite=True,
    )
    return result["secure_url"]


def upload_blocker_attachment_bytes(content: bytes, blocker_id: int, filename: str) -> str:
    """Minh chứng blocker (ảnh/video) — UC-08: "File attachment lưu Object Storage, DB chỉ lưu
    storage key/metadata". Dùng `resource_type="auto"` (khác `upload_document_bytes` dùng "raw")
    để Cloudinary tự nhận diện ảnh/video và cho phép xem trước/transform, thay vì lưu như file thô.

    Không `overwrite=True` như tài liệu: 1 blocker có thể có NHIỀU file, `public_id` phải phân biệt
    theo tên gốc — trùng tên (2 lần chụp "IMG_0001.jpg") vẫn phải ra 2 file khác nhau, không đè lên
    nhau. Cloudinary tự thêm hậu tố khi trùng `public_id` trong cùng folder nếu không ép cụ thể, nên
    để nguyên `filename` làm gợi ý, dựa vào `folder` riêng theo từng blocker để không đụng nhau giữa
    các blocker khác."""
    settings = get_settings()
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
    )
    result = cloudinary.uploader.upload(
        content,
        resource_type="auto",
        folder=f"blocker-attachments/{blocker_id}",
        filename=filename,
        use_filename=True,
        unique_filename=True,
    )
    return result["secure_url"]
