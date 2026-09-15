from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from src.model.enums import MembershipStatus, ProjectRole
from src.model.project_membership import ProjectMembership


class ProjectMembershipResponseDTO(BaseModel):
    membership_id: int
    user_id: int
    project_id: int
    project_role: ProjectRole
    status: MembershipStatus
    assigned_by_admin_id: int
    joined_at: datetime

    @classmethod
    def from_entity(cls, membership: ProjectMembership) -> ProjectMembershipResponseDTO:
        return cls(
            membership_id=membership.membership_id,
            user_id=membership.user_id,
            project_id=membership.project_id,
            project_role=membership.project_role,
            status=membership.status,
            assigned_by_admin_id=membership.assigned_by_admin_id,
            joined_at=membership.joined_at,
        )


class ProjectMembershipDetailResponseDTO(BaseModel):
    """Membership kèm thông tin User (email/tên) — dùng cho màn hình danh sách thành viên,
    tránh FE phải gọi thêm API riêng lấy User cho từng dòng."""

    membership_id: int
    user_id: int
    email: str
    display_name: str
    project_id: int
    project_role: ProjectRole
    status: MembershipStatus
    joined_at: datetime
