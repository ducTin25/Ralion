from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dto.request.task_dependency_request_dto import TaskDependencyCreateRequestDTO
from src.model.task_dependency import TaskDependency
from src.model.template_task import TemplateTask


def _has_path(graph: dict[int, list[int]], start: int, target: int) -> bool:
    """True nếu có đường đi start -> target trong graph (dùng để phát hiện việc thêm cạnh
    predecessor->successor sẽ tạo chu trình, tức là đã có đường đi successor -> predecessor)."""
    visited: set[int] = set()
    stack = [start]
    while stack:
        node = stack.pop()
        if node == target:
            return True
        if node in visited:
            continue
        visited.add(node)
        stack.extend(graph.get(node, []))
    return False


async def list_by_version(db: AsyncSession, version_id: int) -> list[TaskDependency]:
    result = await db.execute(
        select(TaskDependency)
        .join(TemplateTask, TaskDependency.predecessor_task_id == TemplateTask.template_task_id)
        .where(TemplateTask.version_id == version_id)
    )
    return list(result.scalars().all())


async def create_dependency(db: AsyncSession, dto: TaskDependencyCreateRequestDTO) -> TaskDependency:
    if dto.predecessor_task_id == dto.successor_task_id:
        raise HTTPException(status_code=422, detail="Task không thể phụ thuộc vào chính nó")

    predecessor = await db.get(TemplateTask, dto.predecessor_task_id)
    successor = await db.get(TemplateTask, dto.successor_task_id)
    if predecessor is None or successor is None:
        raise HTTPException(status_code=404, detail="predecessor_task_id/successor_task_id không tồn tại")
    if predecessor.version_id != successor.version_id:
        raise HTTPException(status_code=422, detail="2 task phải cùng version mới tạo được dependency")

    existing_deps = await list_by_version(db, predecessor.version_id)
    graph: dict[int, list[int]] = {}
    for dep in existing_deps:
        graph.setdefault(dep.predecessor_task_id, []).append(dep.successor_task_id)

    # Thêm cạnh predecessor -> successor sẽ tạo chu trình nếu đã tồn tại đường đi successor -> predecessor.
    if _has_path(graph, dto.successor_task_id, dto.predecessor_task_id):
        raise HTTPException(status_code=422, detail="Không thể tạo dependency vì sẽ tạo chu trình (cycle)")

    dependency = TaskDependency(
        predecessor_task_id=dto.predecessor_task_id, successor_task_id=dto.successor_task_id
    )
    db.add(dependency)
    await db.commit()
    await db.refresh(dependency)
    return dependency


async def delete_dependency(db: AsyncSession, dependency_id: int) -> None:
    dependency = await db.get(TaskDependency, dependency_id)
    if dependency is None:
        raise HTTPException(status_code=404, detail="Dependency not found")
    await db.delete(dependency)
    await db.commit()
