"""Router membership dự án.

Gộp hai nhóm endpoint có chung entity nhưng khác góc nhìn:

* `/me/*`                  — góc nhìn "của tôi": Engineer/PM tự xem và chọn dự án
                             mình có membership. Bắt buộc đăng nhập.
* `/project-memberships/pm/*` — CRUD quản trị membership cho PM/Admin.

Cả hai được gộp vào một `router` duy nhất ở cuối file, nên phần đăng ký trong
`src/api/routers/__init__.py` không cần thay đổi.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user_id
from src.dto.request.membership_context_request_dto import ActiveMembershipRequestDTO
from src.dto.request.project_membership_request_dto import (
    ProjectMembershipCreateRequestDTO,
    ProjectMembershipUpdateRequestDTO,
)
from src.dto.response.membership_context_response_dto import (
    ActiveMembershipResponseDTO,
    MembershipCardDTO,
)
from src.dto.response.project_membership_response_dto import (
    ProjectMembershipDetailResponseDTO,
    ProjectMembershipResponseDTO,
)
from src.model.enums import MembershipStatus
from src.model.session import get_db
from src.services import project_membership_service

me_router = APIRouter(prefix="/me", tags=["project context"])

# TODO(bảo mật): nhóm endpoint này chưa có guard — người chưa đăng nhập vẫn tạo/xoá
# được membership. Cân nhắc thêm dependencies=[Depends(require_admin)] ở APIRouter.
# Prefix "/pm" trên từng path operation (xem giải thích trong project_router.py).
pm_router = APIRouter(prefix="/project-memberships", tags=["pm-project-memberships"])


# ---------------------------------------------------------------------------
# /me — ngữ cảnh membership của chính người đang đăng nhập
# ---------------------------------------------------------------------------


@me_router.get("/memberships", response_model=list[MembershipCardDTO])
async def list_my_memberships(
    user_id: Annotated[int, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Annotated[MembershipStatus, Query()] = MembershipStatus.ACTIVE,
) -> list[MembershipCardDTO]:
    return await project_membership_service.list_selectable_memberships(db, user_id, status)


@me_router.post("/active-membership", response_model=ActiveMembershipResponseDTO)
async def establish_active_membership(
    dto: ActiveMembershipRequestDTO,
    user_id: Annotated[int, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ActiveMembershipResponseDTO:
    try:
        return await project_membership_service.establish_active_membership(
            db,
            user_id,
            dto.membership_id,
        )
    except project_membership_service.MembershipSelectionError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc


# ---------------------------------------------------------------------------
# /project-memberships/pm — CRUD quản trị membership
# ---------------------------------------------------------------------------


@pm_router.post("/pm", response_model=ProjectMembershipResponseDTO, status_code=201)
async def create_membership(
    dto: ProjectMembershipCreateRequestDTO, db: AsyncSession = Depends(get_db)
) -> ProjectMembershipResponseDTO:
    try:
        membership = await project_membership_service.create_membership(db, dto)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="User is already a member of this project")
    except DBAPIError as exc:
        # Vi phạm bất biến nghiệp vụ ép buộc ở tầng DB trigger (vd INV1: user có system_role
        # không được có ProjectMembership) — không phải IntegrityError, phải bắt riêng và
        # rollback để không làm hỏng session cho các request/transaction tiếp theo.
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=str(exc.orig).strip() or "Membership violates a business rule",
        )
    return ProjectMembershipResponseDTO.from_entity(membership)


@pm_router.get("/pm", response_model=list[ProjectMembershipDetailResponseDTO])
async def list_memberships(
    project_id: int,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> list[ProjectMembershipDetailResponseDTO]:
    """Danh sách thành viên của 1 project, kèm sẵn email/tên user (join)."""
    rows = await project_membership_service.list_memberships_by_project_with_user(
        db, project_id, limit=limit, offset=offset
    )
    return [
        ProjectMembershipDetailResponseDTO(
            membership_id=m.membership_id,
            user_id=u.user_id,
            email=u.email,
            display_name=u.display_name,
            project_id=m.project_id,
            project_role=m.project_role,
            status=m.status,
            joined_at=m.joined_at,
        )
        for m, u in rows
    ]


@pm_router.get("/pm/by-user/{user_id}", response_model=list[ProjectMembershipResponseDTO])
async def list_memberships_by_user(
    user_id: int, db: AsyncSession = Depends(get_db)
) -> list[ProjectMembershipResponseDTO]:
    """Danh sách project mà 1 user tham gia — dùng cho màn hình PM chọn project đang quản lý."""
    memberships = await project_membership_service.list_memberships_by_user(db, user_id)
    return [ProjectMembershipResponseDTO.from_entity(m) for m in memberships]


@pm_router.get("/pm/{membership_id}", response_model=ProjectMembershipResponseDTO)
async def get_membership(
    membership_id: int, db: AsyncSession = Depends(get_db)
) -> ProjectMembershipResponseDTO:
    membership = await project_membership_service.get_membership(db, membership_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    return ProjectMembershipResponseDTO.from_entity(membership)


@pm_router.patch("/pm/{membership_id}", response_model=ProjectMembershipResponseDTO)
async def update_membership(
    membership_id: int, dto: ProjectMembershipUpdateRequestDTO, db: AsyncSession = Depends(get_db)
) -> ProjectMembershipResponseDTO:
    membership = await project_membership_service.update_membership(db, membership_id, dto)
    if membership is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    return ProjectMembershipResponseDTO.from_entity(membership)


@pm_router.delete("/pm/{membership_id}", response_model=ProjectMembershipResponseDTO)
async def deactivate_membership(
    membership_id: int, db: AsyncSession = Depends(get_db)
) -> ProjectMembershipResponseDTO:
    """Xoá mềm — chuyển status sang INACTIVE, không xoá row thật."""
    membership = await project_membership_service.deactivate_membership(db, membership_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    return ProjectMembershipResponseDTO.from_entity(membership)


# Router duy nhất được export — `__init__.py` giữ nguyên `import router`.
router = APIRouter()
router.include_router(me_router)
router.include_router(pm_router)
