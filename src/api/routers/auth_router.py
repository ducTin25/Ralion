from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user, get_session_expiry
from src.dto.admin_console_dto import ChangePasswordDTO
from src.dto.auth_dto import (
    CurrentUserDTO,
    LoginRequestDTO,
    LoginResponseDTO,
    LogoutResponseDTO,
    UserPreferencesUpdateDTO,
)
from src.model.session import get_db
from src.model.user import User
from src.services.auth_service import (
    change_password,
    describe_current_user,
    login,
    update_preferences,
)
from src.services.session_service import (
    SESSION_COOKIE_NAME,
    SESSION_TTL_SECONDS,
    cookie_params,
    issue_token,
    read_token,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


def _attach_session(response: Response, user_id: int) -> datetime:
    """Cấp cookie phiên mới và trả về thời điểm hết hạn."""
    token = issue_token(user_id)
    _, _, expires_at = read_token(token)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=SESSION_TTL_SECONDS,
        **cookie_params(),
    )
    return datetime.fromtimestamp(expires_at, tz=UTC)


@router.post("/login", response_model=LoginResponseDTO)
async def sign_in(
    dto: LoginRequestDTO,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LoginResponseDTO:
    user, redirect_to, outcome = await login(db, dto.email, dto.password)
    # Cookie được cấp cả khi outcome=NO_ACTIVE_PROJECT: người dùng đã xác thực hợp lệ,
    # chỉ là chưa có dự án nào để mở.
    expires_at = _attach_session(response, user.user_id)
    return LoginResponseDTO(
        user_id=user.user_id,
        redirect_to=redirect_to,
        outcome=outcome,
        expires_at=expires_at,
    )


@router.get("/me", response_model=CurrentUserDTO)
async def read_me(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    expires_at: Annotated[int | None, Depends(get_session_expiry)] = None,
) -> CurrentUserDTO:
    profile = await describe_current_user(db, current_user)
    if expires_at is not None:
        profile.expires_at = datetime.fromtimestamp(expires_at, tz=UTC)
    return profile


@router.post("/refresh", response_model=CurrentUserDTO)
async def refresh_session(
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentUserDTO:
    """Gia hạn phiên cho người dùng còn hoạt động.

    Chạy qua `get_current_user` nên phiên hết hạn hoặc tài khoản bị khóa giữa chừng
    sẽ bị chặn tại đây thay vì được gia hạn vô thời hạn.
    """
    profile = await describe_current_user(db, current_user)
    profile.expires_at = _attach_session(response, current_user.user_id)
    return profile


@router.patch("/me/preferences", response_model=CurrentUserDTO)
async def update_my_preferences(
    dto: UserPreferencesUpdateDTO,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentUserDTO:
    """Self-service update of chat response length/tone (PERSONALIZE_CHATBOT_SPEC.md §2).

    Enum-validated at the DTO layer, so no free-form text can reach the prompt. Returns the
    same `CurrentUserDTO` shape as `GET /me` so the frontend can update session state from
    this one response instead of refetching.
    """
    user = await update_preferences(db, current_user, dto)
    return await describe_current_user(db, user)


@router.post("/change-password", response_model=LogoutResponseDTO)
async def change_own_password(
    dto: ChangePasswordDTO,
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LogoutResponseDTO:
    """Đổi mật khẩu rồi đăng xuất, buộc đăng nhập lại bằng mật khẩu mới.

    Xoá cookie ở đây là chủ ý: nếu đổi mật khẩu vì nghi bị lộ, giữ nguyên phiên cũ
    sẽ khiến thao tác này mất ý nghĩa.
    """
    await change_password(db, current_user, dto.current_password, dto.new_password)
    response.delete_cookie(SESSION_COOKIE_NAME, **cookie_params())
    return LogoutResponseDTO(outcome="PASSWORD_CHANGED")


@router.post("/logout", response_model=LogoutResponseDTO)
async def sign_out(response: Response) -> LogoutResponseDTO:
    """Xoá cookie phiên.

    Không yêu cầu đăng nhập: đăng xuất khi phiên đã hết hạn vẫn phải dọn được cookie
    còn sót trong trình duyệt.
    """
    response.delete_cookie(SESSION_COOKIE_NAME, **cookie_params())
    return LogoutResponseDTO()
