from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.dto.request.task_dependency_request_dto import TaskDependencyCreateRequestDTO
from src.dto.response.task_dependency_response_dto import TaskDependencyResponseDTO
from src.model.session import get_db
from src.services import task_dependency_service

router = APIRouter(prefix="/task-dependencies", tags=["pm-task-dependencies"])


@router.post("/pm", response_model=TaskDependencyResponseDTO, status_code=201)
async def create_dependency(
    dto: TaskDependencyCreateRequestDTO, db: AsyncSession = Depends(get_db)
) -> TaskDependencyResponseDTO:
    try:
        dependency = await task_dependency_service.create_dependency(db, dto)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Dependency này đã tồn tại")
    return TaskDependencyResponseDTO.from_entity(dependency)


@router.get("/pm/by-version/{version_id}", response_model=list[TaskDependencyResponseDTO])
async def list_dependencies(version_id: int, db: AsyncSession = Depends(get_db)) -> list[TaskDependencyResponseDTO]:
    dependencies = await task_dependency_service.list_by_version(db, version_id)
    return [TaskDependencyResponseDTO.from_entity(d) for d in dependencies]


@router.delete("/pm/{dependency_id}", status_code=204)
async def delete_dependency(dependency_id: int, db: AsyncSession = Depends(get_db)) -> None:
    await task_dependency_service.delete_dependency(db, dependency_id)
