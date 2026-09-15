from datetime import datetime

from pydantic import BaseModel, Field

from src.dto.response.blocker_attachment_response_dto import BlockerAttachmentResponseDTO
from src.dto.response.plan_task_response_dto import PlanTaskCitationResponseDTO
from src.model.enums import BlockerCategory, BlockerStatus, PlanStatus, ProjectRole, TaskCategory, TaskStatus


class MemberProfileResponseDTO(BaseModel):
    user_id: int
    email: str
    display_name: str


class MemberProjectResponseDTO(BaseModel):
    project_id: int
    membership_id: int
    key: str
    name: str
    project_role: ProjectRole
    plan_id: int | None
    plan_status: PlanStatus | None


class MemberProjectsResponseDTO(BaseModel):
    member: MemberProfileResponseDTO
    projects: list[MemberProjectResponseDTO]


class MemberChecklistProjectResponseDTO(BaseModel):
    project_id: int
    key: str
    name: str


class MemberChecklistProgressResponseDTO(BaseModel):
    completed: int
    total: int
    percent: int


class MemberTaskSummaryResponseDTO(BaseModel):
    plan_task_id: int
    title: str
    category: TaskCategory
    display_order: int
    mandatory: bool
    estimated_minutes: int
    status: TaskStatus
    due_at: datetime | None
    is_overdue: bool
    is_due_soon: bool
    started_at: datetime | None
    completed_at: datetime | None
    dependencies_met: bool
    open_blocker_count: int
    source_count: int
    is_locked: bool
    lock_reason: str | None
    can_start: bool
    can_complete: bool


class MemberTaskGroupResponseDTO(BaseModel):
    category: TaskCategory
    tasks: list[MemberTaskSummaryResponseDTO]


class MemberChecklistResponseDTO(BaseModel):
    member: MemberProfileResponseDTO
    project: MemberChecklistProjectResponseDTO
    membership_id: int
    plan_id: int
    plan_status: PlanStatus
    approved_at: datetime | None
    progress: MemberChecklistProgressResponseDTO
    groups: list[MemberTaskGroupResponseDTO]


class MemberTaskDependencyResponseDTO(BaseModel):
    plan_task_id: int
    title: str
    status: TaskStatus


class MemberTaskSourceResponseDTO(BaseModel):
    document_id: int
    version_id: int
    title: str
    source_url: str
    citation_note: str | None


class MemberTaskDetailResponseDTO(MemberTaskSummaryResponseDTO):
    plan_id: int
    plan_status: PlanStatus
    objective: str
    instruction: str
    dependencies: list[MemberTaskDependencyResponseDTO]
    sources: list[MemberTaskSourceResponseDTO]
    citations: list[PlanTaskCitationResponseDTO] = Field(default_factory=list)


class MemberBlockerResponseDTO(BaseModel):
    blocker_id: int
    plan_task_id: int
    task_title: str
    category: BlockerCategory
    reason: str
    status: BlockerStatus
    reported_at: datetime
    resolved_at: datetime | None
    attachments: list[BlockerAttachmentResponseDTO] = Field(default_factory=list)
