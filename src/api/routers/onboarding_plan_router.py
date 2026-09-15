from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user
from src.dto.request.onboarding_plan_request_dto import (
    GenerateCandidatePlanRequestDTO,
    GenerateReferencePlanRequestDTO,
)
from src.dto.response.onboarding_plan_response_dto import OnboardingPlanResponseDTO
from src.dto.response.plan_generation_job_response_dto import PlanGenerationJobResponseDTO
from src.dto.response.plan_task_response_dto import (
    PlanTaskCitationResponseDTO,
    PlanTaskResponseDTO,
    PlanTaskSourceResponseDTO,
)
from src.model.project import Project
from src.model.session import AsyncSessionLocal, get_db
from src.model.user import User
from src.services import onboarding_plan_service, plan_task_service
from src.services.plan_generation import job_store, pipeline

router = APIRouter(prefix="/onboarding-plans", tags=["pm-onboarding-plans"])


async def _run_generation_job(
    job_id: str,
    existing_plan_id: int | None = None,
    schedule_start_at: datetime | None = None,
) -> None:
    """Chạy pipeline trong BackgroundTasks với session RIÊNG.

    Không tái dùng session của request: session từ `Depends(get_db)` bị đóng ngay khi response trả
    về, mà job này còn chạy tiếp sau đó — dùng lại sẽ lỗi "session is closed" giữa chừng.

    `schedule_start_at`: giờ bắt đầu PM chọn ở modal khi cấp plan cho kỹ sư (xem
    `generate_candidate_plan`) — truyền thẳng xuống `compute_due_dates()` qua pipeline; `None` thì
    pipeline tự rơi về giờ chạy job (hành vi cũ, áp dụng cho luồng sinh lộ trình chuẩn).
    """
    job = job_store.get_job(job_id)
    if job is None:
        return
    async with AsyncSessionLocal() as db:
        await pipeline.run_generation(
            db, job, existing_plan_id=existing_plan_id, schedule_start_at=schedule_start_at
        )


@router.get("/pm/by-project/{project_id}", response_model=list[OnboardingPlanResponseDTO])
async def list_plans_by_project(project_id: int, db: AsyncSession = Depends(get_db)) -> list[OnboardingPlanResponseDTO]:
    """Toàn bộ Plan của các thành viên trong 1 project — FE tự map theo membership_id,
    membership nào không có trong list nghĩa là chưa có Plan."""
    plans = await onboarding_plan_service.list_plans_by_project(db, project_id)
    return [OnboardingPlanResponseDTO.from_entity(p) for p in plans]


@router.get("/pm/by-membership/{membership_id}", response_model=OnboardingPlanResponseDTO)
async def get_plan_by_membership(membership_id: int, db: AsyncSession = Depends(get_db)) -> OnboardingPlanResponseDTO:
    plan = await onboarding_plan_service.get_plan_by_membership(db, membership_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Membership chưa có Onboarding Plan")
    return OnboardingPlanResponseDTO.from_entity(plan)


@router.get("/pm/reference", response_model=OnboardingPlanResponseDTO)
async def get_reference_plan(
    project_id: int, db: AsyncSession = Depends(get_db)
) -> OnboardingPlanResponseDTO:
    """Lộ trình CHUẨN của dự án (row có `project_id`, `membership_id` NULL) — nội dung mẫu PM soạn
    1 lần, mỗi kỹ sư được cấp plan sẽ nhận 1 bản sao. Sửa ở đây chỉ ảnh hưởng kỹ sư nhận plan VỀ SAU.

    Khai báo TRƯỚC các route `/pm/{plan_id}/...` bên dưới: FastAPI khớp route theo thứ tự đăng ký,
    để sau thì "reference" sẽ bị `{plan_id}` nuốt mất và lỗi ép kiểu int.
    """
    plan = await onboarding_plan_service.get_reference_plan_for_project(db, project_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Project chưa có Onboarding Plan nào")
    return OnboardingPlanResponseDTO.from_entity(plan)


@router.post("/pm/generate", response_model=PlanGenerationJobResponseDTO, status_code=202)
async def generate_candidate_plan(
    dto: GenerateCandidatePlanRequestDTO,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> PlanGenerationJobResponseDTO:
    """Cấp Onboarding Plan cho 1 kỹ sư — SAO CHÉP lộ trình chuẩn của dự án, không gọi AI.

    Trả 202 + job_id ngay để FE poll tiến độ 6 bước (luồng này thường xong dưới 1 giây, nhưng giữ
    chung cơ chế với luồng sinh bản chuẩn để UI không phải rẽ nhánh).
    Kiểm tra "đã có lộ trình chuẩn chưa" NGAY ở đây thay vì để pipeline phát hiện: có vậy FE mới
    nhận 422 đồng bộ và hiện được nút điều hướng sang mục Onboarding Plan, thay vì phải mở màn hình
    6 bước rồi mới báo hỏng.
    """
    await onboarding_plan_service.assert_no_open_plan(db, dto.membership_id)
    await onboarding_plan_service.assert_reference_plan_exists(db, dto.membership_id)
    job = job_store.create_job(membership_id=dto.membership_id)
    background_tasks.add_task(
        _run_generation_job, job.job_id, schedule_start_at=dto.start_at
    )
    return PlanGenerationJobResponseDTO.from_job(job)


@router.post("/pm/reference/generate", response_model=PlanGenerationJobResponseDTO, status_code=202)
async def generate_reference_plan(
    dto: GenerateReferencePlanRequestDTO,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> PlanGenerationJobResponseDTO:
    """Sinh (hoặc tạo lại) LỘ TRÌNH CHUẨN của dự án — đây là chỗ DUY NHẤT còn gọi AI.

    Dùng chung cho cả lần đầu lẫn tạo lại: đã có bản chuẩn thì ghi đè tại chỗ (giữ nguyên plan_id,
    tăng revision) vì index `uq_onboarding_plans_one_reference_per_project` chỉ cho 1 bản/dự án.
    Không đụng plan đã cấp cho kỹ sư — họ giữ nguyên bản sao đang chạy (SoT rule 11).
    """
    project = await db.get(Project, dto.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project không tồn tại")

    job = job_store.create_job(project_id=dto.project_id)
    background_tasks.add_task(_run_generation_job, job.job_id)
    return PlanGenerationJobResponseDTO.from_job(job)


@router.get("/pm/generate/{job_id}", response_model=PlanGenerationJobResponseDTO)
async def get_generation_job(job_id: str) -> PlanGenerationJobResponseDTO:
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại hoặc đã hết hạn")
    return PlanGenerationJobResponseDTO.from_job(job)


@router.post("/pm/{plan_id}/regenerate", response_model=PlanGenerationJobResponseDTO, status_code=202)
async def regenerate_candidate_plan(
    plan_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> PlanGenerationJobResponseDTO:
    """Sinh lại nội dung TRÊN CHÍNH plan cũ (không tạo bản ghi mới) — chỉ khi còn DRAFT.
    Lý do không tạo plan mới: xem `onboarding_plan_service.assert_plan_regeneratable`."""
    plan = await onboarding_plan_service.assert_plan_regeneratable(db, plan_id)
    job = job_store.create_job(membership_id=plan.membership_id)
    background_tasks.add_task(_run_generation_job, job.job_id, plan_id)
    return PlanGenerationJobResponseDTO.from_job(job)


@router.patch("/pm/{plan_id}/approve", response_model=OnboardingPlanResponseDTO)
async def approve_candidate_plan(
    plan_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> OnboardingPlanResponseDTO:
    plan = await onboarding_plan_service.approve_plan(db, plan_id, current_user.user_id)
    return OnboardingPlanResponseDTO.from_entity(plan)


@router.get("/pm/{plan_id}/tasks", response_model=list[PlanTaskResponseDTO])
async def list_plan_tasks(plan_id: int, db: AsyncSession = Depends(get_db)) -> list[PlanTaskResponseDTO]:
    plan = await onboarding_plan_service.get_plan(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan không tồn tại")

    details = await plan_task_service.list_task_details(db, plan_id)
    return [
        PlanTaskResponseDTO.from_entity(
            detail.task,
            category=detail.category,
            estimated_minutes=detail.estimated_minutes,
            sources=[PlanTaskSourceResponseDTO.from_detail(source) for source in detail.sources],
            citations=[PlanTaskCitationResponseDTO.from_detail(c) for c in detail.citations],
            start_at=detail.start_at,
        )
        for detail in details
    ]
