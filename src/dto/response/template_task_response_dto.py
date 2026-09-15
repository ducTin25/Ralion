from __future__ import annotations

from pydantic import BaseModel

from src.model.enums import TaskCategory
from src.model.template_task import TemplateTask


class TemplateTaskResponseDTO(BaseModel):
    template_task_id: int
    version_id: int
    category: TaskCategory
    title_pattern: str
    objective: str
    instruction_template: str
    display_order: int
    mandatory: bool
    estimated_minutes: int

    @classmethod
    def from_entity(cls, task: TemplateTask) -> TemplateTaskResponseDTO:
        return cls(
            template_task_id=task.template_task_id,
            version_id=task.version_id,
            category=task.category,
            title_pattern=task.title_pattern,
            objective=task.objective,
            instruction_template=task.instruction_template,
            display_order=task.display_order,
            mandatory=task.mandatory,
            estimated_minutes=task.estimated_minutes,
        )
