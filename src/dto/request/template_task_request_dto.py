from pydantic import BaseModel, Field

from src.model.enums import TaskCategory


class TemplateTaskCreateRequestDTO(BaseModel):
    version_id: int
    category: TaskCategory
    title_pattern: str = Field(..., min_length=1)
    objective: str = Field(..., min_length=1)
    instruction_template: str = Field(..., min_length=1)
    mandatory: bool = True
    estimated_minutes: int = Field(..., gt=0)


class TemplateTaskUpdateRequestDTO(BaseModel):
    category: TaskCategory | None = None
    title_pattern: str | None = Field(default=None, min_length=1)
    objective: str | None = Field(default=None, min_length=1)
    instruction_template: str | None = Field(default=None, min_length=1)
    mandatory: bool | None = None
    estimated_minutes: int | None = Field(default=None, gt=0)


class TemplateTaskReorderRequestDTO(BaseModel):
    version_id: int
    ordered_template_task_ids: list[int] = Field(..., min_length=1)
