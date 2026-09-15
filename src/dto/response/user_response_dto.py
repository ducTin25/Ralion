from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from src.model.enums import UserRole, UserStatus
from src.model.user import User


class UserResponseDTO(BaseModel):
    user_id: int
    email: str
    display_name: str
    system_role: UserRole | None
    status: UserStatus
    created_by_admin_id: int | None
    created_at: datetime

    @classmethod
    def from_entity(cls, user: User) -> UserResponseDTO:
        return cls(
            user_id=user.user_id,
            email=user.email,
            display_name=user.display_name,
            system_role=user.system_role,
            status=user.status,
            created_by_admin_id=user.created_by_admin_id,
            created_at=user.created_at,
        )
