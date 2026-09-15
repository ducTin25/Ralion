import hashlib
import hmac
import os

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dto.auth_dto import CurrentUserDTO, SessionMembershipDTO, UserPreferencesUpdateDTO
from src.model.enums import MembershipStatus, UserRole, UserStatus
from src.model.project import Project
from src.model.project_membership import ProjectMembership
from src.model.user import User
from src.services.session_service import revocation_stamp


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        _, salt_hex, digest_hex = encoded.split("$", 2)
        expected = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
        return hmac.compare_digest(expected.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


async def login(db: AsyncSession, email: str, password: str) -> tuple[User, str | None, str]:
    user = await db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"code": "INVALID_CREDENTIALS", "message": "Email hoặc mật khẩu không đúng."})
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "ACCOUNT_INACTIVE", "message": "Tài khoản đã bị khóa. Vui lòng liên hệ quản trị viên."})
    # Đặt TRƯỚC phần điều hướng theo vai trò: mật khẩu đang dùng là do admin đặt, nên
    # phải đổi trước khi vào bất kỳ khu vực nào — kể cả admin console.
    if user.must_change_password:
        return user, "/change-password", "MUST_CHANGE_PASSWORD"
    if user.system_role == UserRole.ADMIN:
        return user, "/admin", "AUTHENTICATED"
    if user.system_role == UserRole.HR:
        return user, "/hr/policies", "AUTHENTICATED"
    active = list((await db.execute(select(ProjectMembership).where(ProjectMembership.user_id == user.user_id, ProjectMembership.status == MembershipStatus.ACTIVE))).scalars())
    if not active:
        return user, None, "NO_ACTIVE_PROJECT"
    return user, "/select-project", "AUTHENTICATED"


async def change_password(db: AsyncSession, user: User, current_password: str, new_password: str) -> None:
    """Người dùng tự đổi mật khẩu.

    Bắt buộc nhập mật khẩu hiện tại: nếu không, một phiên bị chiếm quyền có thể đổi
    mật khẩu và khoá chủ tài khoản ra ngoài vĩnh viễn.
    """
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "WRONG_PASSWORD", "message": "Mật khẩu hiện tại không đúng."},
        )
    if current_password == new_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "PASSWORD_UNCHANGED", "message": "Mật khẩu mới phải khác mật khẩu cũ."},
        )
    user.password_hash = hash_password(new_password)
    # Người dùng đã tự chọn mật khẩu -> hết nợ. Đây là chỗ DUY NHẤT tắt cờ; admin reset
    # mật khẩu thì ngược lại, bật cờ (xem admin_console_service.reset_user_password).
    user.must_change_password = False
    # Đổi mật khẩu phải giết mọi phiên đang mở, kể cả phiên hiện tại — người ta đổi mật
    # khẩu chính vì nghi có người khác đang dùng tài khoản mình. Router đã xoá cookie sau
    # lệnh này nên người dùng hợp lệ chỉ cần đăng nhập lại; phiên của kẻ kia thì chết hẳn.
    user.session_invalid_before = revocation_stamp()
    await db.commit()


async def update_preferences(db: AsyncSession, user: User, dto: UserPreferencesUpdateDTO) -> User:
    """Partial update of the user's own chat response length/tone.

    Both fields are already `StrEnum`-validated by `UserPreferencesUpdateDTO` before this
    runs, so there is no free-form string path into these columns.
    """
    if dto.response_length is not None:
        user.response_length = dto.response_length
    if dto.response_tone is not None:
        user.response_tone = dto.response_tone
    await db.commit()
    return user


async def describe_current_user(db: AsyncSession, user: User) -> CurrentUserDTO:
    """Hồ sơ phiên cho GET /auth/me, gồm cả membership để frontend biết phạm vi truy cập."""
    memberships = list(
        (
            await db.execute(
                select(ProjectMembership)
                .where(ProjectMembership.user_id == user.user_id)
                .order_by(ProjectMembership.joined_at.desc())
            )
        ).scalars()
    )
    projects = {project.project_id: project for project in (await db.execute(select(Project))).scalars()}
    return CurrentUserDTO(
        user_id=user.user_id,
        display_name=user.display_name,
        email=user.email,
        system_role=user.system_role,
        status=user.status,
        response_length=user.response_length,
        response_tone=user.response_tone,
        memberships=[
            SessionMembershipDTO(
                membership_id=membership.membership_id,
                project_id=membership.project_id,
                project_name=projects[membership.project_id].name,
                project_key=projects[membership.project_id].key,
                project_role=membership.project_role,
                status=membership.status,
                project_status=projects[membership.project_id].status,
            )
            for membership in memberships
            if membership.project_id in projects
        ],
    )
