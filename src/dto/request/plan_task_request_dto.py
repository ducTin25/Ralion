from datetime import datetime

from pydantic import BaseModel, Field


class UpdatePlanTaskRequestDTO(BaseModel):
    """PM sửa tay nội dung 1 task trong Candidate Plan (chỉ khi plan còn DRAFT).

    Không cho sửa `mandatory`/`display_order`/`template_task_id`: đó là cấu trúc kế thừa từ
    TemplateVersion, đổi ở đây sẽ làm plan lệch khỏi template đã duyệt (SoT rule 11).
    """

    title: str | None = Field(default=None, min_length=1, max_length=300)
    instruction: str | None = Field(default=None, min_length=1)
    # PM chỉnh lại hạn 1 task (vd giờ compute_due_dates() đề xuất không hợp lý cho task đó). Sửa
    # start_at hiển thị của task KẾ TIẾP là hệ quả tự động — nó suy ra từ due_at này, không lưu
    # riêng (xem plan_task_service.list_task_details).
    due_at: datetime | None = Field(default=None)
