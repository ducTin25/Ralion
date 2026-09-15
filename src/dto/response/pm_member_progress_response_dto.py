from datetime import datetime

from pydantic import BaseModel

from src.dto.response.pm_blocker_response_dto import PmBlockerResponseDTO
from src.model.enums import PlanStatus, TaskCategory, TaskStatus


class PmProgressTaskDTO(BaseModel):
    """1 task trong plan của Engineer, nhìn từ phía PM — thêm `is_overdue` mà bản thân `PlanTask`
    không lưu (suy ra từ `due_at`/`status` tại thời điểm đọc, không phải cột cố định)."""

    plan_task_id: int
    title: str
    category: TaskCategory
    mandatory: bool
    status: TaskStatus
    # Không phải cột DB — due_at của task đứng ngay trước, xem pm_progress_service.get_member_progress.
    start_at: datetime | None
    due_at: datetime | None
    is_overdue: bool


class PmMemberProgressResponseDTO(BaseModel):
    """SoT §17.2 (TV1/PM): "Theo dõi tiến độ, deadline và blocker của từng plan" — gộp 3 thứ đó
    vào đúng 1 response để PM xem 1 lần, không phải ghép từ nhiều API."""

    membership_id: int
    engineer_name: str
    engineer_email: str
    plan_id: int | None
    plan_status: PlanStatus | None
    approved_at: datetime | None
    completed_count: int
    total_count: int
    percent: int
    overdue_count: int
    tasks: list[PmProgressTaskDTO]
    blockers: list[PmBlockerResponseDTO]
