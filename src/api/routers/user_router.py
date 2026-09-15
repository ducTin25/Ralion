from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import require_admin
from src.dto.request.user_request_dto import UserCreateRequestDTO, UserUpdateRequestDTO
from src.dto.response.user_response_dto import UserResponseDTO
from src.model.session import get_db
from src.services import user_service

# Router CRUD thô, giữ lại cho script và công cụ nội bộ. Giao diện console dùng
# /console/admin/users vì có thêm số dự án, người tạo và bộ lọc.
#
# `dependencies` ở cấp router áp cho MỌI endpoint bên dưới: quên thêm guard vào một
# hàm mới cũng không tạo ra lỗ hổng. Trước đây toàn bộ router này không có guard nên
# ai cũng tạo/xoá được tài khoản.
router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(require_admin)],
)


@router.post("", response_model=UserResponseDTO, status_code=201)
async def create_user(dto: UserCreateRequestDTO, db: AsyncSession = Depends(get_db)) -> UserResponseDTO:
    try:
        user = await user_service.create_user(db, dto)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Email already exists")
    return UserResponseDTO.from_entity(user)


@router.get("", response_model=list[UserResponseDTO])
async def list_users(limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_db)) -> list[UserResponseDTO]:
    users = await user_service.list_users(db, limit=limit, offset=offset)
    return [UserResponseDTO.from_entity(u) for u in users]


@router.get("/{user_id}", response_model=UserResponseDTO)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)) -> UserResponseDTO:
    user = await user_service.get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponseDTO.from_entity(user)


@router.patch("/{user_id}", response_model=UserResponseDTO)
async def update_user(
    user_id: int, dto: UserUpdateRequestDTO, db: AsyncSession = Depends(get_db)
) -> UserResponseDTO:
    user = await user_service.update_user(db, user_id, dto)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponseDTO.from_entity(user)


@router.delete("/{user_id}", response_model=UserResponseDTO)
async def archive_user(user_id: int, db: AsyncSession = Depends(get_db)) -> UserResponseDTO:
    """Xoá mềm — chuyển status sang INACTIVE, không xoá row thật."""
    user = await user_service.archive_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponseDTO.from_entity(user)
