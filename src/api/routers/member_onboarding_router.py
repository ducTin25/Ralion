from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user
from src.dto.request.member_onboarding_request_dto import MemberTaskStatusUpdateRequestDTO
from src.dto.response.member_onboarding_response_dto import (
    MemberBlockerResponseDTO,
    MemberChecklistResponseDTO,
    MemberProjectsResponseDTO,
    MemberTaskDetailResponseDTO,
)
from src.dto.response.notification_response_dto import TaskNotificationResponseDTO
from src.model.enums import BlockerCategory
from src.model.session import get_db
from src.model.user import User
from src.services import member_onboarding_service

router = APIRouter(prefix="/member", tags=["member-onboarding"])


def _raise_http(error: member_onboarding_service.MemberOnboardingError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get("/projects", response_model=MemberProjectsResponseDTO)
async def list_member_projects(
    member: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MemberProjectsResponseDTO:
    return await member_onboarding_service.list_projects(db, member)


@router.get("/checklist", response_model=MemberChecklistResponseDTO)
async def get_member_checklist(
    member: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    project_id: int = Query(gt=0),
) -> MemberChecklistResponseDTO:
    try:
        return await member_onboarding_service.get_checklist(db, member, project_id)
    except member_onboarding_service.MemberOnboardingError as error:
        _raise_http(error)


@router.get("/notifications", response_model=list[TaskNotificationResponseDTO])
async def list_member_notifications(
    member: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    project_id: int = Query(gt=0),
) -> list[TaskNotificationResponseDTO]:
    try:
        return await member_onboarding_service.list_notifications(db, member, project_id)
    except member_onboarding_service.MemberOnboardingError as error:
        _raise_http(error)


@router.get("/blockers", response_model=list[MemberBlockerResponseDTO])
async def list_member_blockers(
    member: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    project_id: int = Query(gt=0),
) -> list[MemberBlockerResponseDTO]:
    try:
        return await member_onboarding_service.list_blockers(db, member, project_id)
    except member_onboarding_service.MemberOnboardingError as error:
        _raise_http(error)


@router.post(
    "/plan-tasks/{task_id}/blockers",
    response_model=MemberBlockerResponseDTO,
    status_code=201,
)
async def create_member_blocker(
    task_id: int,
    member: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    # multipart/form-data (không phải JSON body) — UC-08 cần đính kèm file cùng lúc với category/lý
    # do, và FastAPI không cho trộn body JSON với `File()` trong cùng 1 request.
    category: Annotated[BlockerCategory, Form()],
    reason: Annotated[str, Form()],
    attachments: Annotated[list[UploadFile], File()] = [],  # noqa: B006 - FastAPI yêu cầu default này
) -> MemberBlockerResponseDTO:
    try:
        return await member_onboarding_service.create_blocker(
            db,
            member,
            task_id,
            category,
            reason,
            attachments,
        )
    except member_onboarding_service.MemberOnboardingError as error:
        _raise_http(error)


@router.get("/plan-tasks/{task_id}", response_model=MemberTaskDetailResponseDTO)
async def get_member_task(
    task_id: int,
    member: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MemberTaskDetailResponseDTO:
    try:
        return await member_onboarding_service.get_task_detail(db, member, task_id)
    except member_onboarding_service.MemberOnboardingError as error:
        _raise_http(error)


@router.patch("/plan-tasks/{task_id}/status", response_model=MemberTaskDetailResponseDTO)
async def update_member_task_status(
    task_id: int,
    payload: MemberTaskStatusUpdateRequestDTO,
    member: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MemberTaskDetailResponseDTO:
    try:
        return await member_onboarding_service.update_task_status(db, member, task_id, payload.status)
    except member_onboarding_service.MemberOnboardingError as error:
        _raise_http(error)
