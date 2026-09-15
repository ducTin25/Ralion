from datetime import datetime

from pydantic import BaseModel, Field

from src.model.enums import (
    MembershipStatus,
    ProjectRole,
    ProjectStatus,
    ResponseLength,
    ResponseTone,
    UserRole,
    UserStatus,
)


class LoginRequestDTO(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=256)


class LoginResponseDTO(BaseModel):
    user_id: int
    redirect_to: str | None
    outcome: str
    # Thời điểm cookie phiên hết hạn, để frontend biết khi nào cần gọi /auth/refresh.
    expires_at: datetime | None = None


class SessionMembershipDTO(BaseModel):
    membership_id: int
    project_id: int
    project_name: str
    project_key: str
    project_role: ProjectRole
    status: MembershipStatus
    project_status: ProjectStatus


class CurrentUserDTO(BaseModel):
    """Danh tính và phạm vi quyền của phiên hiện tại.

    Frontend dùng response này thay cho việc suy đoán từ localStorage: nó cho biết
    hiển thị tên ai, mở được khu vực nào và đang tham gia những dự án nào.
    """

    user_id: int
    display_name: str
    email: str
    system_role: UserRole | None
    status: UserStatus
    response_length: ResponseLength
    response_tone: ResponseTone
    memberships: list[SessionMembershipDTO]
    expires_at: datetime | None = None


class UserPreferencesUpdateDTO(BaseModel):
    """Self-service partial update of the current user's own chat personalization.

    Both fields are validated as `StrEnum` members — there is no `str` field anywhere
    in this DTO, so no free-form text can reach the prompt (PERSONALIZE_CHATBOT_SPEC.md §3).
    """

    response_length: ResponseLength | None = None
    response_tone: ResponseTone | None = None


class LogoutResponseDTO(BaseModel):
    outcome: str = "SIGNED_OUT"
