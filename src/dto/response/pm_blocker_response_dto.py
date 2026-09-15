from datetime import datetime

from pydantic import BaseModel

from src.dto.response.blocker_attachment_response_dto import BlockerAttachmentResponseDTO
from src.model.enums import BlockerCategory, BlockerStatus


class PmBlockerResponseDTO(BaseModel):
    """Blocker của Engineer mà PM trong cùng project được phép theo dõi/xử lý."""

    blocker_id: int
    project_id: int
    membership_id: int
    plan_task_id: int
    engineer_name: str
    engineer_email: str
    task_title: str
    category: BlockerCategory
    reason: str
    status: BlockerStatus
    reported_at: datetime
    resolved_at: datetime | None
    # Minh chứng (ảnh/video) Engineer đính kèm khi báo — UC-08: "PM cùng dự án nhìn thấy và xử lý
    # qua kênh hiện có". Rỗng với blocker báo trước khi có tính năng này.
    attachments: list[BlockerAttachmentResponseDTO] = []
