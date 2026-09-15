from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.dto.request.plan_task_request_dto import UpdatePlanTaskRequestDTO
from src.dto.response.plan_task_response_dto import (
    PlanTaskCitationResponseDTO,
    PlanTaskResponseDTO,
    PlanTaskSourceResponseDTO,
)
from src.model.session import get_db
from src.services import plan_task_service

router = APIRouter(prefix="/plan-tasks", tags=["pm-plan-tasks"])


@router.patch("/pm/{plan_task_id}", response_model=PlanTaskResponseDTO)
async def update_plan_task(
    plan_task_id: int, dto: UpdatePlanTaskRequestDTO, db: AsyncSession = Depends(get_db)
) -> PlanTaskResponseDTO:
    """PM sửa tay nội dung 1 task khi Candidate Plan còn Nháp."""
    task = await plan_task_service.update_task(db, plan_task_id, dto)

    details = await plan_task_service.list_task_details(db, task.plan_id)
    detail = next(d for d in details if d.task.plan_task_id == plan_task_id)
    return PlanTaskResponseDTO.from_entity(
        detail.task,
        category=detail.category,
        estimated_minutes=detail.estimated_minutes,
        sources=[PlanTaskSourceResponseDTO.from_detail(source) for source in detail.sources],
        citations=[PlanTaskCitationResponseDTO.from_detail(c) for c in detail.citations],
        start_at=detail.start_at,
    )
