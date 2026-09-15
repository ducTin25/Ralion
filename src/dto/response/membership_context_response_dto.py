from datetime import datetime

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from src.model.enums import PlanStatus, ProjectRole, ProjectStatus, SyncStatus


class CamelCaseResponseDTO(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class MembershipPlanDTO(CamelCaseResponseDTO):
    status: PlanStatus
    revision: int
    required_done: int
    required_total: int
    open_blockers: int


class MembershipCardDTO(CamelCaseResponseDTO):
    membership_id: int
    project_id: int
    project_name: str
    project_key: str
    project_status: ProjectStatus
    project_role: ProjectRole
    joined_at: datetime
    sync_status: SyncStatus
    last_synced_at: datetime | None
    plan: MembershipPlanDTO | None


class ActiveMembershipResponseDTO(CamelCaseResponseDTO):
    membership_id: int
    project_id: int
    project_name: str
    project_key: str
    project_role: ProjectRole
    redirect_path: str
