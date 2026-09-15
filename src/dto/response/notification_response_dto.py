from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class TaskNotificationResponseDTO(BaseModel):
    """1 task sắp/đã trễ hạn, dùng cho dropdown chuông thông báo (PM + Member Portal).

    Tính trên mỗi lần đọc, không lưu bảng Notification riêng — chuông chỉ cần trả lời "việc gì
    cần chú ý ngay bây giờ", không cần lịch sử/đã đọc-chưa đọc.
    """

    plan_task_id: int
    title: str
    due_at: datetime
    is_overdue: bool
    engineer_name: str | None = None
    # Chỉ PM cần -- để FE dựng link mở đúng drawer "Xem tiến độ" của đúng Engineer đó. Bên Engineer
    # tự bấm bell của chính mình nên không cần membership_id (luôn là của chính họ).
    membership_id: int | None = None


class PmNotificationResponseDTO(BaseModel):
    """Backend-authored item for the PM bell, with a stable deduplication identity."""

    notification_id: str
    kind: Literal["TASK_DUE", "GITHUB_SYNC_COMPLETED", "CONVENTION_SCAN_COMPLETED"]
    title: str
    message: str
    created_at: datetime
    is_overdue: bool = False
    engineer_name: str | None = None
    membership_id: int | None = None
    plan_task_id: int | None = None
