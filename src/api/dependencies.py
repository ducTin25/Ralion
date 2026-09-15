from typing import TYPE_CHECKING, Annotated

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings

if TYPE_CHECKING:  # tránh import nặng (sentence-transformers) lúc khởi động
    from src.ai.providers.embeddings import Embedder
    from src.model.onboarding_template import OnboardingTemplate
from src.model.enums import (
    MembershipStatus,
    ProjectRole,
    ProjectStatus,
    TemplateScope,
    UserRole,
    UserStatus,
)
from src.model.project import Project
from src.model.project_membership import ProjectMembership
from src.model.session import get_db
from src.model.user import User
from src.services.session_service import (
    SESSION_COOKIE_NAME,
    SessionError,
    is_revoked,
    read_token,
)


def get_embedder(request: Request) -> "Embedder":
    """Embedder cho ingestion: fake ở dev/test, Modal BGE-M3 ở production."""
    return request.app.state.ai_resources.ingestion_embedding


def get_policy_ingestor():
    """Hàm ingest của TV3, tiêm qua dependency để test thay được bản giả.

    Cần thiết vì `ingest_policy_document` dùng `pg_advisory_xact_lock` — hàm chỉ có trên
    PostgreSQL nên test chạy SQLite không gọi trực tiếp được.
    """
    from src.modules.knowledge.policy_ingestion import ingest_policy_document

    return ingest_policy_document


async def get_session_expiry(
    ralion_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> int | None:
    """Thời điểm hết hạn của cookie phiên, hoặc None nếu request không dùng cookie."""
    if not ralion_session:
        return None
    try:
        _, _, expires_at = read_token(ralion_session)
    except SessionError:
        return None
    return expires_at


async def get_session_issued_at(
    ralion_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> int | None:
    """Thời điểm phát hành token, để đối chiếu với mốc thu hồi của tài khoản.

    Trả None khi request không dùng cookie (lối tắt X-User-Id ở dev, hoặc test tiêm
    danh tính trực tiếp) — không có token thì không có gì để thu hồi.
    """
    if not ralion_session:
        return None
    try:
        _, issued_at, _ = read_token(ralion_session)
    except SessionError:
        return None
    return issued_at


async def get_current_user_id(
    ralion_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
    x_user_id: Annotated[int | None, Header(alias="X-User-Id")] = None,
) -> int:
    """Danh tính của request hiện tại.

    Ưu tiên cookie phiên có chữ ký. Header X-User-Id chỉ là lối tắt cho dev (curl,
    Swagger) và bị tắt khi `allow_header_user_context=false`, vì client tự đặt được
    header này nên nó không có giá trị xác thực.
    """
    if ralion_session:
        try:
            user_id, _, _ = read_token(ralion_session)
        except SessionError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": exc.code, "message": exc.message},
            ) from exc
        return user_id

    if get_settings().allow_header_user_context and x_user_id is not None:
        if x_user_id <= 0:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "INVALID_USER_CONTEXT",
                    "message": "The supplied user context is invalid.",
                },
            )
        return x_user_id

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "UNAUTHENTICATED", "message": "A valid user context is required."},
    )


async def get_session_user_id(
    ralion_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> int:
    """Authenticate solely from the signed session cookie.

    Sensitive endpoints use this strict boundary and never accept the development
    ``X-User-Id`` escape hatch from ``get_current_user_id``.
    """
    try:
        user_id, _, _ = read_token(ralion_session)
    except SessionError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    return user_id


async def _load_active_user(
    user_id: int, db: AsyncSession, issued_at: int | None = None
) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHENTICATED", "message": "User context is not recognized."},
        )
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACCOUNT_INACTIVE", "message": "This account is inactive and cannot sign in."},
        )
    # Thu hồi phiên tức thì. Token tự chứa và không gọi về server được, nên chốt chặn
    # duy nhất là so `issued_at` với mốc thu hồi đã lưu cùng User — vốn đã nạp ở trên
    # nên không tốn thêm truy vấn nào.
    #
    # Trả 401 chứ không 403: client cần hiểu là "hãy đăng nhập lại", không phải "bạn
    # thiếu quyền". Frontend đã có sẵn xử lý điều hướng về /login cho 401.
    if issued_at is not None and is_revoked(issued_at, user.session_invalid_before):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "SESSION_REVOKED",
                "message": "Phiên đăng nhập đã bị thu hồi. Vui lòng đăng nhập lại.",
            },
        )
    return user


async def get_current_user(
    user_id: int = Depends(get_current_user_id),
    issued_at: int | None = Depends(get_session_issued_at),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await _load_active_user(user_id, db, issued_at)


async def get_session_user(
    user_id: int = Depends(get_session_user_id),
    db: AsyncSession = Depends(get_db),
    issued_at: int | None = Depends(get_session_issued_at),
) -> User:
    """Resolve an active user from a signed cookie, with no header fallback."""
    return await _load_active_user(user_id, db, issued_at)


async def require_password_changed(
    current_user: User = Depends(get_current_user),
) -> User:
    """Chặn endpoint nghiệp vụ khi tài khoản còn nợ đổi mật khẩu.

    CỐ Ý tách khỏi `get_current_user` thay vì nhét thẳng vào đó: `/auth/change-password`
    và `/auth/me` cũng dùng `get_current_user`. Chặn ở đấy là người dùng kẹt vĩnh viễn —
    phải đổi mật khẩu mới vào được, mà không vào được để đổi.

    Cũng cố ý đọc cờ từ DB chứ không nhét vào token phiên: token tự chứa và không thu hồi
    được, nên sau khi đổi mật khẩu, token cũ vẫn nói "chưa đổi" cho tới khi hết hạn.
    `get_current_user` vốn đã nạp User từ DB nên không tốn thêm truy vấn nào.
    """
    if current_user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "PASSWORD_CHANGE_REQUIRED",
                "message": "Bạn cần đổi mật khẩu trước khi tiếp tục.",
            },
        )
    return current_user


async def require_admin(current_user: User = Depends(require_password_changed)) -> User:
    if current_user.system_role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ADMIN_REQUIRED", "message": "Administrator access is required."},
        )
    return current_user


def require_project_member(*allowed_roles: ProjectRole):
    """Dependency factory: chặn request nếu người dùng không thuộc dự án trong path.

    TV1 và TV3 dùng lại hàm này thay vì tự viết kiểm tra membership, để cả hệ thống
    chỉ có một định nghĩa "thế nào là thành viên dự án".

        @router.get("/pm/projects/{project_id}/plans")
        async def list_plans(
            membership: Annotated[ProjectMembership, Depends(require_project_member(ProjectRole.PM))],
        ): ...

    Không truyền role nào nghĩa là chấp nhận cả PM lẫn ENGINEER. Admin đi qua được
    mọi dự án vì đó là người tạo và quản trị chúng.
    """

    async def dependency(
        project_id: int,
        current_user: Annotated[User, Depends(require_password_changed)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> ProjectMembership | None:
        if current_user.system_role == UserRole.ADMIN:
            return None

        membership = await db.scalar(
            select(ProjectMembership).where(
                ProjectMembership.user_id == current_user.user_id,
                ProjectMembership.project_id == project_id,
                ProjectMembership.status == MembershipStatus.ACTIVE,
            )
        )
        if membership is None:
            # Cùng một mã lỗi cho "không thuộc dự án" và "dự án không tồn tại": trả
            # lời khác nhau sẽ để lộ dự án nào đang tồn tại trong hệ thống.
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "PROJECT_ACCESS_REQUIRED",
                    "message": "Bạn không có quyền truy cập dự án này.",
                },
            )
        if allowed_roles and membership.project_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "PROJECT_ROLE_REQUIRED",
                    "message": "Vai trò trong dự án không đủ để thực hiện thao tác này.",
                },
            )

        project = await db.get(Project, project_id)
        if project is None or project.status != ProjectStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "PROJECT_NOT_ACTIVE",
                    "message": "Dự án đã lưu trữ, không thể thao tác.",
                },
            )
        return membership

    return dependency


async def _authorize_template_scope(
    db: AsyncSession, current_user: User, onboarding_template: "OnboardingTemplate | None"
) -> None:
    """Admin luôn qua được. Template scope GLOBAL chỉ Admin sửa được. Template scope PROJECT thì
    Admin hoặc PM đang có membership ACTIVE đúng project đó mới sửa được.

    Không raise 404 khi `onboarding_template is None` — đây là hàm AUTHORIZATION thuần, việc báo
    "không tìm thấy" để nguyên cho service layer đã tự làm (message riêng cho từng loại: task/
    version/template not found), tránh đổi hành vi not-found đã có sẵn.
    """
    if onboarding_template is None:
        return
    if current_user.system_role == UserRole.ADMIN:
        return

    if onboarding_template.scope == TemplateScope.GLOBAL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ADMIN_REQUIRED", "message": "Chỉ Admin được sửa Global Master Template."},
        )

    membership = await db.scalar(
        select(ProjectMembership).where(
            ProjectMembership.user_id == current_user.user_id,
            ProjectMembership.project_id == onboarding_template.project_id,
            ProjectMembership.project_role == ProjectRole.PM,
            ProjectMembership.status == MembershipStatus.ACTIVE,
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "PROJECT_ACCESS_REQUIRED",
                "message": "Bạn không có quyền sửa Master Template của dự án này.",
            },
        )


async def authorize_template_scope_for_version(
    db: AsyncSession, current_user: User, version_id: int
) -> None:
    """Gọi trực tiếp (không phải Depends()) từ trong handler khi id cần kiểm tra nằm trong request
    body (vd `TemplateTaskCreateRequestDTO.version_id`) chứ không phải path — tránh khai báo 1 tham
    số Pydantic body thứ 2 trong dependency, FastAPI sẽ gộp nhầm thành 1 body lồng nhau và phá format
    request client đang gửi."""
    from src.model.onboarding_template import OnboardingTemplate
    from src.model.template_version import TemplateVersion

    template = await db.scalar(
        select(OnboardingTemplate)
        .join(TemplateVersion, TemplateVersion.template_id == OnboardingTemplate.template_id)
        .where(TemplateVersion.version_id == version_id)
    )
    await _authorize_template_scope(db, current_user, template)


async def authorize_template_scope_for_template(
    db: AsyncSession, current_user: User, template_id: int
) -> None:
    from src.model.onboarding_template import OnboardingTemplate

    template = await db.get(OnboardingTemplate, template_id)
    await _authorize_template_scope(db, current_user, template)


def require_template_task_write_access():
    """Path có `template_task_id` (sửa/xoá 1 task) — tra ngược lên OnboardingTemplate qua
    TemplateTask -> TemplateVersion để biết scope GLOBAL/PROJECT rồi áp đúng luật ở
    `_authorize_template_scope`."""

    async def dependency(
        template_task_id: int,
        current_user: Annotated[User, Depends(require_password_changed)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> None:
        from src.model.onboarding_template import OnboardingTemplate
        from src.model.template_task import TemplateTask
        from src.model.template_version import TemplateVersion

        template = await db.scalar(
            select(OnboardingTemplate)
            .join(TemplateVersion, TemplateVersion.template_id == OnboardingTemplate.template_id)
            .join(TemplateTask, TemplateTask.version_id == TemplateVersion.version_id)
            .where(TemplateTask.template_task_id == template_task_id)
        )
        await _authorize_template_scope(db, current_user, template)

    return dependency


def require_template_version_write_access():
    """Path có `version_id` (xem/duyệt 1 version)."""

    async def dependency(
        version_id: int,
        current_user: Annotated[User, Depends(require_password_changed)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> None:
        await authorize_template_scope_for_version(db, current_user, version_id)

    return dependency


def require_template_id_write_access():
    """Path có `template_id` (xem 1 template, liệt kê version của nó)."""

    async def dependency(
        template_id: int,
        current_user: Annotated[User, Depends(require_password_changed)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> None:
        await authorize_template_scope_for_template(db, current_user, template_id)

    return dependency


async def require_hr_or_admin(current_user: User = Depends(require_password_changed)) -> User:
    if current_user.system_role not in (UserRole.ADMIN, UserRole.HR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "CONSOLE_ACCESS_REQUIRED", "message": "Console access is required."},
        )
    return current_user


async def require_pm_or_admin(
    current_user: Annotated[User, Depends(require_password_changed)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """F6 Phase 6 Review Queue approve/reject gate (CLAUDE.md Phase 6 §4).

    F6 rule mining is not project-scoped (single fixed repo, F6_RULE_MINING_SPEC.md §4.6),
    so there is no specific `project_id` to check a `ProjectMembership` against here. This is
    an interim mapping onto the existing PM concept (ProjectRole.PM in any active project),
    not a new role/permission system — documented per CLAUDE.md Phase 6 §4's instruction to
    report rather than invent RBAC. Revisit if F6 ever becomes multi-project/repo-scoped.
    """
    if current_user.system_role == UserRole.ADMIN:
        return current_user
    is_pm = await db.scalar(
        select(ProjectMembership.membership_id).where(
            ProjectMembership.user_id == current_user.user_id,
            ProjectMembership.project_role == ProjectRole.PM,
            ProjectMembership.status == MembershipStatus.ACTIVE,
        )
    )
    if is_pm is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "PM_OR_ADMIN_REQUIRED", "message": "PM or administrator access is required."},
        )
    return current_user
