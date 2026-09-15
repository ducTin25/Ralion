from pydantic import BaseModel

from src.model.enums import TaskStatus


class MemberTaskStatusUpdateRequestDTO(BaseModel):
    status: TaskStatus


# Báo blocker giờ nhận qua multipart/form-data (category + reason + file đính kèm tuỳ chọn), không
# còn qua body JSON — xem `member_onboarding_router.create_member_blocker`. Validate độ dài `reason`
# nằm ở `member_onboarding_service.create_blocker()` (tầng service, không phải DTO nữa) vì `Form()`
# không dựng được model Pydantic đầy đủ khi đi kèm `File()` trong cùng request.
