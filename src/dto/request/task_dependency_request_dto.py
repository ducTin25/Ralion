from pydantic import BaseModel


class TaskDependencyCreateRequestDTO(BaseModel):
    predecessor_task_id: int
    successor_task_id: int
