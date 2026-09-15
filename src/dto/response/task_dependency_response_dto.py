from __future__ import annotations

from pydantic import BaseModel

from src.model.task_dependency import TaskDependency


class TaskDependencyResponseDTO(BaseModel):
    dependency_id: int
    predecessor_task_id: int
    successor_task_id: int

    @classmethod
    def from_entity(cls, dependency: TaskDependency) -> TaskDependencyResponseDTO:
        return cls(
            dependency_id=dependency.dependency_id,
            predecessor_task_id=dependency.predecessor_task_id,
            successor_task_id=dependency.successor_task_id,
        )
