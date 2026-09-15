from pydantic import BaseModel

from src.model.enums import MembershipStatus, ProjectRole


class ProjectMembershipCreateRequestDTO(BaseModel):
    user_id: int
    project_id: int
    project_role: ProjectRole
    assigned_by_admin_id: int


class ProjectMembershipUpdateRequestDTO(BaseModel):
    project_role: ProjectRole | None = None
    status: MembershipStatus | None = None
