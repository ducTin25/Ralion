from datetime import datetime

from pydantic import BaseModel


class BlockerAttachmentResponseDTO(BaseModel):
    """1 file minh chứng (ảnh/video) đính kèm 1 Blocker — dùng chung cho cả phía Member (người báo)
    và phía PM (người xem/xử lý), vì đây là cùng 1 dữ liệu, không có bản riêng cho mỗi phía."""

    attachment_id: int
    file_name: str
    mime_type: str
    url: str
    uploaded_at: datetime
