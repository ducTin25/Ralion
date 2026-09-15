from pydantic import BaseModel, Field

from src.model.enums import ProjectStatus


class ProjectCreateRequestDTO(BaseModel):
    key: str = Field(..., min_length=2)
    name: str = Field(..., min_length=1)
    created_by_admin_id: int


class ProjectUpdateRequestDTO(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    status: ProjectStatus | None = None
