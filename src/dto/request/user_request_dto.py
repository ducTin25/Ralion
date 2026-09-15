from pydantic import BaseModel, Field

from src.model.enums import UserRole, UserStatus


class UserCreateRequestDTO(BaseModel):
    email: str = Field(..., min_length=3)
    display_name: str = Field(..., min_length=1)
    # Quyền cấp công ty (ADMIN/HR); để trống với nhân viên thường (quyền theo dự án
    # nằm ở ProjectMembership.project_role, không phải ở đây).
    system_role: UserRole | None = None
    created_by_admin_id: int | None = None


class UserUpdateRequestDTO(BaseModel):
    display_name: str | None = Field(default=None, min_length=1)
    system_role: UserRole | None = None
    status: UserStatus | None = None
