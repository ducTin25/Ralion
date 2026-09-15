from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dto.request.user_request_dto import UserCreateRequestDTO, UserUpdateRequestDTO
from src.model.enums import UserStatus
from src.model.user import User


async def create_user(db: AsyncSession, dto: UserCreateRequestDTO) -> User:
    user = User(
        email=dto.email.lower(),
        display_name=dto.display_name,
        system_role=dto.system_role,
        created_by_admin_id=dto.created_by_admin_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_user(db: AsyncSession, user_id: int) -> User | None:
    return await db.get(User, user_id)


async def list_users(db: AsyncSession, limit: int = 50, offset: int = 0) -> list[User]:
    result = await db.execute(select(User).order_by(User.user_id).limit(limit).offset(offset))
    return list(result.scalars().all())


async def update_user(db: AsyncSession, user_id: int, dto: UserUpdateRequestDTO) -> User | None:
    user = await db.get(User, user_id)
    if user is None:
        return None
    if dto.display_name is not None:
        user.display_name = dto.display_name
    if dto.system_role is not None:
        user.system_role = dto.system_role
    if dto.status is not None:
        user.status = dto.status
    await db.commit()
    await db.refresh(user)
    return user


async def archive_user(db: AsyncSession, user_id: int) -> User | None:
    """Xoá mềm: chuyển status = INACTIVE thay vì xoá row (không hard-delete)."""
    user = await db.get(User, user_id)
    if user is None:
        return None
    user.status = UserStatus.INACTIVE
    await db.commit()
    await db.refresh(user)
    return user
