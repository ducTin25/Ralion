from collections.abc import Sequence
from datetime import date, timedelta
from typing import TypeVar

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dto.admin_console_dto import (
    AdminMembershipBulkCreateDTO,
    AdminMembershipBulkResultDTO,
    AdminMembershipCreateDTO,
    AdminMembershipListItemDTO,
    AdminMembershipSkippedDTO,
    AdminPriorityUserDTO,
    AdminProjectCreateDTO,
    AdminProjectDetailDTO,
    AdminProjectListItemDTO,
    AdminProjectMemberDTO,
    AdminProjectUpdateDTO,
    AdminRiskItemDTO,
    AdminUnassignedUserDTO,
    AdminUserCreateDTO,
    AdminUserDetailDTO,
    AdminUserListItemDTO,
    AdminUserMembershipDTO,
    AdminUserUpdateDTO,
    MembershipEligibilityDTO,
    MembershipEligibleProjectDTO,
    MembershipEligibleUserDTO,
    PolicyDetailDTO,
    PolicyListItemDTO,
)
from src.model.document_version import DocumentVersion
from src.model.enums import (
    DocumentDomain,
    DocumentStatus,
    MembershipStatus,
    ProjectRole,
    ProjectStatus,
    UserStatus,
    VersionStatus,
)
from src.model.knowledge_document import KnowledgeDocument
from src.model.project import Project
from src.model.project_membership import ProjectMembership
from src.model.user import User
from src.services import access_grant_service, onboarding_template_service
from src.services.auth_service import hash_password
from src.services.session_service import revocation_stamp

T = TypeVar("T")


def paginate(items: Sequence[T], page: int, page_size: int) -> tuple[list[T], int]:
    total = len(items)
    start = (page - 1) * page_size
    return list(items[start : start + page_size]), total


async def list_users(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    query: str | None,
    system_role: str | None,
    account_status: UserStatus | None,
    start_status: str | None = None,
    password_state: str | None = None,
) -> tuple[list[AdminUserListItemDTO], int]:
    today = date.today()
    users = list((await db.execute(select(User).order_by(User.created_at.desc()))).scalars())
    memberships = list((await db.execute(select(ProjectMembership))).scalars())
    user_names = {user.user_id: user.display_name for user in users}
    membership_count: dict[int, int] = {}
    for membership in memberships:
        membership_count[membership.user_id] = membership_count.get(membership.user_id, 0) + 1

    # Số quyền truy cập đang chờ cấp, gom theo người. Đếm ở đây thay vì để client gọi
    # thêm một request cho mỗi dòng — bảng 20 dòng sẽ thành 21 request.
    pending_access = await _pending_access_by_user(db, memberships)

    normalized = query.strip().lower() if query else ""
    filtered = [
        user
        for user in users
        if (not normalized or normalized in user.display_name.lower() or normalized in user.email.lower())
        and (system_role is None or (system_role == "NONE" and user.system_role is None) or user.system_role == system_role)
        and (account_status is None or user.status == account_status)
        # Không có start_date coi như đã đi làm: tài khoản cũ không có dữ liệu này,
        # xếp vào "sắp vào" sẽ tạo một danh sách chờ toàn người đang làm việc.
        and (
            start_status is None
            or (start_status == "UPCOMING" and user.start_date is not None and user.start_date > today)
            or (start_status == "STARTED" and (user.start_date is None or user.start_date <= today))
        )
        and (
            password_state is None
            or (password_state == "PENDING" and user.must_change_password)
            or (password_state == "SET" and not user.must_change_password)
        )
    ]
    selected, total = paginate(filtered, page, page_size)
    return [
        AdminUserListItemDTO(
            user_id=user.user_id,
            display_name=user.display_name,
            email=user.email,
            system_role=user.system_role,
            status=user.status,
            project_count=membership_count.get(user.user_id, 0),
            created_at=user.created_at,
            created_by_name=user_names.get(user.created_by_admin_id),
            start_date=user.start_date,
            must_change_password=user.must_change_password,
            pending_access_count=pending_access.get(user.user_id, 0),
        )
        for user in selected
    ], total


async def _pending_access_by_user(
    db: AsyncSession, memberships: Sequence[ProjectMembership]
) -> dict[int, int]:
    """Đếm quyền truy cập đang chờ cấp, gom theo user_id.

    Chỉ tính membership ACTIVE: quyền gắn với membership đã ngừng thì không còn là việc
    cần làm, nó thuộc checklist thu hồi.
    """
    from src.model.access_grant import AccessGrant
    from src.model.enums import AccessGrantStatus

    active = {m.membership_id: m.user_id for m in memberships if m.status == MembershipStatus.ACTIVE}
    if not active:
        return {}
    rows = await db.execute(
        select(AccessGrant.membership_id).where(
            AccessGrant.membership_id.in_(active.keys()),
            AccessGrant.status == AccessGrantStatus.REQUESTED,
        )
    )
    counts: dict[int, int] = {}
    for membership_id in rows.scalars():
        user_id = active[membership_id]
        counts[user_id] = counts.get(user_id, 0) + 1
    return counts


async def get_user_detail(db: AsyncSession, user_id: int) -> AdminUserDetailDTO:
    """Full profile for the user detail drawer, including every project membership."""
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    memberships = list(
        (
            await db.execute(
                select(ProjectMembership)
                .where(ProjectMembership.user_id == user_id)
                .order_by(ProjectMembership.joined_at.desc())
            )
        ).scalars()
    )
    projects = {project.project_id: project for project in (await db.execute(select(Project))).scalars()}
    creator = await db.get(User, user.created_by_admin_id) if user.created_by_admin_id else None
    rows = [
        AdminUserMembershipDTO(
            membership_id=membership.membership_id,
            project_id=membership.project_id,
            project_name=projects[membership.project_id].name,
            project_key=projects[membership.project_id].key,
            project_role=membership.project_role,
            status=membership.status,
            project_status=projects[membership.project_id].status,
            joined_at=membership.joined_at,
        )
        for membership in memberships
        if membership.project_id in projects
    ]
    return AdminUserDetailDTO(
        user_id=user.user_id,
        display_name=user.display_name,
        email=user.email,
        system_role=user.system_role,
        status=user.status,
        project_count=len(rows),
        created_at=user.created_at,
        created_by_name=creator.display_name if creator else None,
        start_date=user.start_date,
        must_change_password=user.must_change_password,
        pending_access_count=sum((await _pending_access_by_user(db, memberships)).values()),
        active_project_count=sum(row.status == MembershipStatus.ACTIVE for row in rows),
        memberships=rows,
    )


async def create_user(db: AsyncSession, actor: User, dto: AdminUserCreateDTO) -> AdminUserListItemDTO:
    if "@" not in dto.email:
        raise HTTPException(status_code=422, detail="Email must be valid")
    duplicate = await db.scalar(select(User).where(User.email == dto.email.lower()))
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="Email already exists")
    user = User(
        email=dto.email.lower(),
        display_name=dto.display_name.strip(),
        password_hash=hash_password(dto.temporary_password),
        system_role=dto.system_role,
        status=dto.status,
        created_by_admin_id=actor.user_id,
        start_date=dto.start_date,
        # Mật khẩu tạm do admin chọn: bắt người dùng đổi ở lần đăng nhập đầu tiên.
        must_change_password=True,
    )
    # Temporary password is intentionally only validated at the boundary until the auth model has a password hash.
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return AdminUserListItemDTO(
        user_id=user.user_id,
        display_name=user.display_name,
        email=user.email,
        system_role=user.system_role,
        status=user.status,
        project_count=0,
        created_at=user.created_at,
        created_by_name=actor.display_name,
        start_date=user.start_date,
        must_change_password=user.must_change_password,
    )


async def update_user(db: AsyncSession, user_id: int, dto: AdminUserUpdateDTO) -> AdminUserDetailDTO:
    """Sửa tên, email hoặc quyền hệ thống của một tài khoản."""
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if dto.email is not None:
        email = dto.email.strip().lower()
        if "@" not in email:
            raise HTTPException(status_code=422, detail="Email must be valid")
        duplicate = await db.scalar(select(User).where(User.email == email, User.user_id != user_id))
        if duplicate is not None:
            raise HTTPException(status_code=409, detail="Email already exists")
        user.email = email

    if dto.display_name is not None:
        user.display_name = dto.display_name.strip()

    if dto.clear_start_date:
        user.start_date = None
    elif dto.start_date is not None:
        user.start_date = dto.start_date

    # Cấp quyền hệ thống cho người đang có membership sẽ tạo ra tài khoản vừa là
    # ADMIN/HR vừa là thành viên dự án — trạng thái mà create_membership vốn cấm.
    if dto.clear_system_role:
        user.system_role = None
    elif dto.system_role is not None:
        active = await db.scalar(
            select(ProjectMembership).where(
                ProjectMembership.user_id == user_id,
                ProjectMembership.status == MembershipStatus.ACTIVE,
            )
        )
        if active is not None:
            raise HTTPException(
                status_code=422,
                detail="Gỡ membership dự án đang hoạt động trước khi cấp quyền hệ thống",
            )
        user.system_role = dto.system_role

    await db.commit()
    return await get_user_detail(db, user_id)


async def reset_user_password(db: AsyncSession, user_id: int, new_password: str) -> AdminUserListItemDTO:
    """Admin đặt lại mật khẩu, dùng khi người dùng quên hoặc mật khẩu tạm bị lộ."""
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = hash_password(new_password)
    # Người dùng chưa biết mật khẩu này — admin chọn hộ. Bắt đổi ở lần đăng nhập kế tiếp,
    # nếu không admin sẽ vĩnh viễn biết mật khẩu của tài khoản mình vừa reset.
    user.must_change_password = True
    # Lý do phổ biến nhất để reset mật khẩu là nghi tài khoản bị chiếm. Nếu không cắt
    # phiên, kẻ đang giữ cookie vẫn thao tác được tới 30 phút sau khi admin "xử lý xong".
    user.session_invalid_before = revocation_stamp()
    await db.commit()
    detail = await get_user_detail(db, user_id)
    return AdminUserListItemDTO(**detail.model_dump(exclude={"active_project_count", "memberships"}))


async def change_user_status(db: AsyncSession, user_id: int, next_status: UserStatus) -> AdminUserListItemDTO:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.status = next_status
    if next_status != UserStatus.ACTIVE:
        # Khoá tài khoản phải cắt phiên đang mở ngay, không đợi cookie hết hạn. Đóng dấu
        # ở đây thay vì dựa vào việc `_load_active_user` chặn theo `status`: hai lớp bảo
        # vệ độc lập, và mốc này còn có tác dụng sau khi tài khoản được mở lại — token cũ
        # phát hành trước lúc khoá vẫn phải chết.
        user.session_invalid_before = revocation_stamp()
    await db.commit()
    await db.refresh(user)
    # Return the same shape the list endpoint produces so the caller can update a row
    # in place without a second round trip.
    detail = await get_user_detail(db, user_id)
    return AdminUserListItemDTO(**detail.model_dump(exclude={"active_project_count", "memberships"}))


def resolve_primary_pm(
    project: Project, project_memberships: Sequence[ProjectMembership]
) -> ProjectMembership | None:
    """The project's owning PM.

    Project.primary_pm_membership_id is the explicit assignment and wins when it still
    points at an active PM membership. Otherwise fall back to the earliest active PM so
    a project that was never explicitly assigned still shows an owner.
    """
    active_pms = [
        m
        for m in project_memberships
        if m.project_role == ProjectRole.PM and m.status == MembershipStatus.ACTIVE
    ]
    if project.primary_pm_membership_id is not None:
        explicit = next(
            (m for m in active_pms if m.membership_id == project.primary_pm_membership_id), None
        )
        if explicit is not None:
            return explicit
    return min(active_pms, key=lambda m: m.membership_id) if active_pms else None


async def list_projects(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    account_status: ProjectStatus | None,
    query: str | None = None,
    pm_state: str | None = None,
) -> tuple[list[AdminProjectListItemDTO], int]:
    projects = list((await db.execute(select(Project).order_by(Project.created_at.desc()))).scalars())
    users = list((await db.execute(select(User))).scalars())
    memberships = list((await db.execute(select(ProjectMembership))).scalars())
    user_names = {user.user_id: user.display_name for user in users}
    pending_access = await _pending_access_by_project(db, memberships)
    normalized = query.strip().lower() if query else ""
    filtered = [
        project
        for project in projects
        if (account_status is None or project.status == account_status)
        and (not normalized or normalized in project.name.lower() or normalized in project.key.lower())
        # Dùng lại `resolve_primary_pm` thay vì tự viết điều kiện: bộ lọc và cột
        # "PM phụ trách" phải trả lời giống nhau, nếu không lọc "chưa có PM" sẽ ra
        # những dòng đang hiện tên một PM.
        and (
            pm_state is None
            or (
                pm_state == "MISSING"
                and resolve_primary_pm(
                    project, [m for m in memberships if m.project_id == project.project_id]
                )
                is None
            )
            or (
                pm_state == "ASSIGNED"
                and resolve_primary_pm(
                    project, [m for m in memberships if m.project_id == project.project_id]
                )
                is not None
            )
        )
    ]
    selected, total = paginate(filtered, page, page_size)
    rows: list[AdminProjectListItemDTO] = []
    for project in selected:
        project_memberships = [m for m in memberships if m.project_id == project.project_id]
        primary_pm = resolve_primary_pm(project, project_memberships)
        rows.append(
            AdminProjectListItemDTO(
                project_id=project.project_id,
                name=project.name,
                key=project.key,
                status=project.status,
                primary_pm_name=user_names.get(primary_pm.user_id) if primary_pm else None,
                member_count=len(project_memberships),
                active_member_count=sum(
                    m.status == MembershipStatus.ACTIVE for m in project_memberships
                ),
                created_at=project.created_at,
                created_by_name=user_names.get(project.created_by_admin_id),
                pending_access_count=pending_access.get(project.project_id, 0),
            )
        )
    return rows, total


async def _pending_access_by_project(
    db: AsyncSession, memberships: Sequence[ProjectMembership]
) -> dict[int, int]:
    """Đếm quyền truy cập đang chờ cấp, gom theo project_id.

    Quyền được cấp THEO DỰ ÁN, nên đây là góc nhìn tự nhiên hơn cả bảng người dùng:
    admin mở một dự án là biết ngay có bao nhiêu người đang ngồi chờ ở đó.
    """
    from src.model.access_grant import AccessGrant
    from src.model.enums import AccessGrantStatus

    active = {
        m.membership_id: m.project_id
        for m in memberships
        if m.status == MembershipStatus.ACTIVE
    }
    if not active:
        return {}
    rows = await db.execute(
        select(AccessGrant.membership_id).where(
            AccessGrant.membership_id.in_(active.keys()),
            AccessGrant.status == AccessGrantStatus.REQUESTED,
        )
    )
    counts: dict[int, int] = {}
    for membership_id in rows.scalars():
        project_id = active[membership_id]
        counts[project_id] = counts.get(project_id, 0) + 1
    return counts


async def update_project(
    db: AsyncSession, project_id: int, dto: AdminProjectUpdateDTO
) -> AdminProjectDetailDTO:
    """Sửa tên và mã dự án.

    `key` là định danh hiển thị khắp hệ thống và có ràng buộc unique, nên phải kiểm tra
    trùng trước khi commit — để DB ném IntegrityError thì người dùng nhận lỗi 500 khó hiểu
    thay vì một câu giải thích.

    Cố ý KHÔNG cho sửa dự án đã lưu trữ: đó là bản ghi lịch sử, sửa tên nó sẽ làm mọi
    tham chiếu cũ (ảnh chụp, biên bản họp) không khớp nữa.
    """
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.status != ProjectStatus.ACTIVE:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "PROJECT_ARCHIVED",
                "message": "Dự án đã lưu trữ, không sửa được thông tin.",
            },
        )

    if dto.key is not None and dto.key != project.key:
        duplicate = await db.scalar(select(Project).where(Project.key == dto.key))
        if duplicate is not None:
            raise HTTPException(
                status_code=409,
                detail={"code": "PROJECT_KEY_TAKEN", "message": "Mã dự án này đã được dùng."},
            )
        project.key = dto.key
    if dto.name is not None:
        project.name = dto.name

    await db.commit()
    return await get_project_detail(db, project_id)


async def get_project_detail(db: AsyncSession, project_id: int) -> AdminProjectDetailDTO:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    memberships = list(
        (
            await db.execute(
                select(ProjectMembership)
                .where(ProjectMembership.project_id == project_id)
                .order_by(ProjectMembership.joined_at.desc())
            )
        ).scalars()
    )
    users = {user.user_id: user for user in (await db.execute(select(User))).scalars()}
    primary_pm = resolve_primary_pm(project, memberships)
    members = [
        AdminProjectMemberDTO(
            membership_id=membership.membership_id,
            user_id=membership.user_id,
            display_name=users[membership.user_id].display_name,
            email=users[membership.user_id].email,
            project_role=membership.project_role,
            status=membership.status,
            joined_at=membership.joined_at,
            is_primary_pm=primary_pm is not None and membership.membership_id == primary_pm.membership_id,
        )
        for membership in memberships
        if membership.user_id in users
    ]
    # Active PMs first, then the rest, so the drawer leads with who owns the project.
    members.sort(
        key=lambda member: (
            not member.is_primary_pm,
            member.status != MembershipStatus.ACTIVE,
            member.project_role != ProjectRole.PM,
            member.display_name,
        )
    )
    creator = users.get(project.created_by_admin_id)
    return AdminProjectDetailDTO(
        project_id=project.project_id,
        name=project.name,
        key=project.key,
        status=project.status,
        primary_pm_name=users[primary_pm.user_id].display_name if primary_pm else None,
        primary_pm_email=users[primary_pm.user_id].email if primary_pm else None,
        primary_pm_membership_id=primary_pm.membership_id if primary_pm else None,
        member_count=len(members),
        active_member_count=sum(m.status == MembershipStatus.ACTIVE for m in members),
        active_pm_count=sum(
            m.status == MembershipStatus.ACTIVE and m.project_role == ProjectRole.PM for m in members
        ),
        created_at=project.created_at,
        created_by_name=creator.display_name if creator else None,
        pending_access_count=(await _pending_access_by_project(db, memberships)).get(project_id, 0),
        github_repo=project.github_repo,
        default_branch=project.default_branch,
        sync_status=project.sync_status,
        last_synced_at=project.last_synced_at,
        members=members,
    )


async def set_primary_pm(db: AsyncSession, project_id: int, membership_id: int | None) -> AdminProjectDetailDTO:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if membership_id is None:
        project.primary_pm_membership_id = None
        await db.commit()
        return await get_project_detail(db, project_id)
    membership = await db.get(ProjectMembership, membership_id)
    if membership is None or membership.project_id != project_id:
        raise HTTPException(status_code=404, detail="Membership does not belong to this project")
    if membership.project_role != ProjectRole.PM:
        raise HTTPException(status_code=422, detail="Only a PM membership can be the primary PM")
    if membership.status != MembershipStatus.ACTIVE:
        raise HTTPException(status_code=422, detail="Only an active membership can be the primary PM")
    project.primary_pm_membership_id = membership.membership_id
    await db.commit()
    return await get_project_detail(db, project_id)


async def create_project(db: AsyncSession, actor: User, dto: AdminProjectCreateDTO) -> AdminProjectListItemDTO:
    key = dto.key.upper()
    if await db.scalar(select(Project).where(Project.key == key)):
        raise HTTPException(status_code=409, detail="Project key already exists")
    # SoT §11.16: mỗi project phải tự có 1 Project Template ngay khi tạo (fork từ Global Master
    # Template) — cùng ràng buộc project_service.create_project (luồng PM) đã áp dụng, trước đây
    # luồng Admin bỏ sót bước này nên project tạo qua đây không có Master Template.
    global_template = await onboarding_template_service.get_approved_global_template(db)
    if global_template is None:
        raise HTTPException(
            status_code=422,
            detail="Chưa có Global Master Template đã duyệt — không thể tạo project mới.",
        )
    # The Admin console currently creates the project before a repository is bound.
    # Keep the required sync coordinates valid until the repository-binding flow is added.
    project = Project(
        key=key,
        name=dto.name.strip(),
        github_repo=f"pending/{key.lower()}",
        default_branch="main",
        created_by_admin_id=actor.user_id,
    )
    db.add(project)
    await db.flush()

    await onboarding_template_service.materialize_project_template(db, project, global_template)

    await db.commit()
    await db.refresh(project)
    return AdminProjectListItemDTO(
        project_id=project.project_id,
        name=project.name,
        key=project.key,
        status=project.status,
        primary_pm_name=None,
        member_count=0,
        created_at=project.created_at,
        created_by_name=actor.display_name,
    )


async def change_project_status(
    db: AsyncSession,
    project_id: int,
    next_status: ProjectStatus,
    deactivate_memberships: bool = False,
) -> AdminProjectDetailDTO:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    project.status = next_status
    if next_status == ProjectStatus.ARCHIVED and deactivate_memberships:
        memberships = list(
            (
                await db.execute(
                    select(ProjectMembership).where(ProjectMembership.project_id == project_id)
                )
            ).scalars()
        )
        for membership in memberships:
            if membership.status == MembershipStatus.ACTIVE:
                membership.status = MembershipStatus.INACTIVE
        # The pointer would otherwise reference a membership nobody can use.
        project.primary_pm_membership_id = None
    await db.commit()
    return await get_project_detail(db, project_id)


def access_state(membership: ProjectMembership, user: User, project: Project) -> str:
    """Why this membership does or does not open the project workspace.

    A membership row being ACTIVE is not enough: the account must be able to sign in
    and the project must still be live. Naming the specific blocker is what lets an
    admin fix the right thing instead of toggling the membership and hoping.
    """
    if membership.status != MembershipStatus.ACTIVE:
        return "SUSPENDED"
    if user.status != UserStatus.ACTIVE:
        return "BLOCKED_USER"
    if project.status != ProjectStatus.ACTIVE:
        return "BLOCKED_PROJECT"
    return "ACTIVE"


def _membership_row(
    membership: ProjectMembership,
    users: dict[int, User],
    projects: dict[int, Project],
    access_counts: dict[int, tuple[int, int]] | None = None,
) -> AdminMembershipListItemDTO:
    """`access_counts` ánh xạ membership_id -> (đã cấp, đang chờ).

    Mặc định None để những nơi gọi sau một thao tác ghi (tạo, sửa) không phải truy vấn
    thêm — chúng chỉ dựng lại một dòng để client cập nhật tại chỗ, và số quyền sẽ đúng
    ở lần tải danh sách kế tiếp.
    """
    granted, pending = (access_counts or {}).get(membership.membership_id, (0, 0))
    user = users[membership.user_id]
    project = projects[membership.project_id]
    assigner = users.get(membership.assigned_by_admin_id)
    return AdminMembershipListItemDTO(
        membership_id=membership.membership_id,
        user_id=membership.user_id,
        user_name=user.display_name,
        user_email=user.email,
        project_id=membership.project_id,
        project_name=project.name,
        project_key=project.key,
        project_role=membership.project_role,
        status=membership.status,
        assigned_by_name=assigner.display_name if assigner else None,
        joined_at=membership.joined_at,
        user_system_role=user.system_role,
        user_status=user.status,
        project_status=project.status,
        is_primary_pm=project.primary_pm_membership_id == membership.membership_id,
        access_state=access_state(membership, user, project),
        granted_access_count=granted,
        pending_access_count=pending,
    )


async def _access_counts_by_membership(
    db: AsyncSession, membership_ids: Sequence[int]
) -> dict[int, tuple[int, int]]:
    """Đếm quyền đã cấp và đang chờ cho từng membership, trong MỘT truy vấn.

    Trả về map membership_id -> (đã cấp, đang chờ). Bản ghi REVOKED không tính: nó là
    lịch sử, không phải quyền đang tồn tại.
    """
    from src.model.access_grant import AccessGrant
    from src.model.enums import AccessGrantStatus

    if not membership_ids:
        return {}
    rows = await db.execute(
        select(AccessGrant.membership_id, AccessGrant.status).where(
            AccessGrant.membership_id.in_(membership_ids),
            AccessGrant.status != AccessGrantStatus.REVOKED,
        )
    )
    counts: dict[int, tuple[int, int]] = {}
    for membership_id, status in rows.all():
        granted, pending = counts.get(membership_id, (0, 0))
        if status == AccessGrantStatus.GRANTED:
            counts[membership_id] = (granted + 1, pending)
        else:
            counts[membership_id] = (granted, pending + 1)
    return counts


async def list_memberships(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    query: str | None,
    membership_status: MembershipStatus | None,
    project_id: int | None = None,
    project_role: ProjectRole | None = None,
    state: str | None = None,
) -> tuple[list[AdminMembershipListItemDTO], int]:
    memberships = list((await db.execute(select(ProjectMembership).order_by(ProjectMembership.joined_at.desc()))).scalars())
    users = {user.user_id: user for user in (await db.execute(select(User))).scalars()}
    projects = {project.project_id: project for project in (await db.execute(select(Project))).scalars()}
    normalized = query.strip().lower() if query else ""
    access_counts = await _access_counts_by_membership(
        db, [m.membership_id for m in memberships]
    )
    rows = [
        _membership_row(membership, users, projects, access_counts)
        for membership in memberships
        if membership.user_id in users and membership.project_id in projects
    ]
    filtered = [
        row
        for row in rows
        if (membership_status is None or row.status == membership_status)
        and (project_id is None or row.project_id == project_id)
        and (project_role is None or row.project_role == project_role)
        and (state is None or row.access_state == state)
        and (
            not normalized
            or normalized in row.user_name.lower()
            or normalized in row.user_email.lower()
            or normalized in row.project_name.lower()
            or normalized in row.project_key.lower()
        )
    ]
    return paginate(filtered, page, page_size)


async def membership_summary(db: AsyncSession) -> dict[str, int]:
    memberships = list((await db.execute(select(ProjectMembership))).scalars())
    users = {user.user_id: user for user in (await db.execute(select(User))).scalars()}
    projects = {project.project_id: project for project in (await db.execute(select(Project))).scalars()}
    states = [
        access_state(membership, users[membership.user_id], projects[membership.project_id])
        for membership in memberships
        if membership.user_id in users and membership.project_id in projects
    ]
    return {
        "total": len(states),
        "active": states.count("ACTIVE"),
        "suspended": states.count("SUSPENDED"),
        "blocked": states.count("BLOCKED_USER") + states.count("BLOCKED_PROJECT"),
    }


async def create_membership(db: AsyncSession, actor: User, dto: AdminMembershipCreateDTO) -> AdminMembershipListItemDTO:
    user, project = await db.get(User, dto.user_id), await db.get(Project, dto.project_id)
    if user is None or project is None:
        raise HTTPException(status_code=404, detail="User or project not found")
    if user.system_role is not None or user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=422, detail="Only active users without a system role can be assigned")
    if project.status != ProjectStatus.ACTIVE:
        raise HTTPException(status_code=422, detail="Only active projects can receive memberships")
    duplicate = await db.scalar(select(ProjectMembership).where(ProjectMembership.user_id == user.user_id, ProjectMembership.project_id == project.project_id))
    if duplicate:
        raise HTTPException(status_code=409, detail="Membership already exists")
    membership = ProjectMembership(
        user_id=user.user_id,
        project_id=project.project_id,
        project_role=dto.project_role,
        status=dto.status,
        assigned_by_admin_id=actor.user_id,
    )
    db.add(membership)
    await db.flush()
    # A project with no owner is the most common gap in the console, so the first
    # active PM assigned to it automatically becomes the primary PM.
    if (
        membership.project_role == ProjectRole.PM
        and membership.status == MembershipStatus.ACTIVE
        and project.primary_pm_membership_id is None
    ):
        project.primary_pm_membership_id = membership.membership_id
    # Bộ quyền chuẩn sinh trong cùng transaction: quyền chỉ nên tồn tại nếu membership
    # tồn tại. Chỉ sinh cho membership ACTIVE — tạo sẵn ở trạng thái INACTIVE nghĩa là
    # người đó chưa thực sự vào dự án, chưa cần quyền gì.
    if membership.status == MembershipStatus.ACTIVE:
        await access_grant_service.seed_grants_for_membership(db, membership)
    await db.commit()
    await db.refresh(membership)
    await db.refresh(project)
    return _membership_row(membership, {user.user_id: user, actor.user_id: actor}, {project.project_id: project})


async def update_membership(
    db: AsyncSession, membership_id: int, project_role: ProjectRole | None, membership_status: MembershipStatus | None
) -> AdminMembershipListItemDTO:
    membership = await db.get(ProjectMembership, membership_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    if project_role is not None:
        membership.project_role = project_role
    if membership_status is not None:
        membership.status = membership_status
    # Nâng ENGINEER lên PM cần thêm quyền, và bật lại membership đã ngừng cũng cần bộ
    # quyền chuẩn. `seed_grants_for_membership` bỏ qua loại đã có nên gọi ở đây an toàn.
    #
    # Chiều ngược lại KHÔNG tự thu hồi: hạ PM xuống ENGINEER hay ngừng membership chỉ
    # đưa quyền vào checklist để admin tự tick. Đánh dấu REVOKED tự động sẽ tạo ra một
    # danh sách sạch sẽ nói dối rằng quyền trên GitHub/Jira đã thực sự bị gỡ.
    if membership.status == MembershipStatus.ACTIVE:
        await access_grant_service.seed_grants_for_membership(db, membership)
    # Demoting or deactivating the owning PM must clear the project pointer, otherwise
    # the project keeps reporting an owner who no longer has PM access.
    owning_project = await db.get(Project, membership.project_id)
    if (
        owning_project is not None
        and owning_project.primary_pm_membership_id == membership.membership_id
        and (membership.project_role != ProjectRole.PM or membership.status != MembershipStatus.ACTIVE)
    ):
        owning_project.primary_pm_membership_id = None
    await db.commit()
    await db.refresh(membership)
    users = {user.user_id: user for user in (await db.execute(select(User))).scalars()}
    project = await db.get(Project, membership.project_id)
    return _membership_row(membership, users, {project.project_id: project})


async def create_memberships_bulk(
    db: AsyncSession, actor: User, dto: AdminMembershipBulkCreateDTO
) -> AdminMembershipBulkResultDTO:
    """Assign many people to one project in a single pass.

    Ineligible users are reported back instead of aborting the whole request, so one
    locked account cannot block the other nineteen assignments an admin just made.
    """
    project = await db.get(Project, dto.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.status != ProjectStatus.ACTIVE:
        raise HTTPException(status_code=422, detail="Only active projects can receive memberships")

    users = {user.user_id: user for user in (await db.execute(select(User))).scalars()}
    existing = {
        membership.user_id
        for membership in (
            await db.execute(
                select(ProjectMembership).where(ProjectMembership.project_id == dto.project_id)
            )
        ).scalars()
    }

    created: list[ProjectMembership] = []
    skipped: list[AdminMembershipSkippedDTO] = []
    for user_id in dict.fromkeys(dto.user_ids):
        user = users.get(user_id)
        if user is None:
            skipped.append(AdminMembershipSkippedDTO(user_id=user_id, display_name=None, reason="Không tìm thấy tài khoản"))
            continue
        if user.system_role is not None:
            skipped.append(AdminMembershipSkippedDTO(user_id=user_id, display_name=user.display_name, reason="Tài khoản có quyền hệ thống"))
            continue
        if user.status != UserStatus.ACTIVE:
            skipped.append(AdminMembershipSkippedDTO(user_id=user_id, display_name=user.display_name, reason="Tài khoản đã khóa"))
            continue
        if user_id in existing:
            skipped.append(AdminMembershipSkippedDTO(user_id=user_id, display_name=user.display_name, reason="Đã có membership ở dự án này"))
            continue
        membership = ProjectMembership(
            user_id=user_id,
            project_id=dto.project_id,
            project_role=dto.project_role,
            status=MembershipStatus.ACTIVE,
            assigned_by_admin_id=actor.user_id,
        )
        db.add(membership)
        created.append(membership)
        existing.add(user_id)

    if created:
        await db.flush()
        if dto.project_role == ProjectRole.PM and project.primary_pm_membership_id is None:
            project.primary_pm_membership_id = created[0].membership_id
        for membership in created:
            await access_grant_service.seed_grants_for_membership(db, membership)
        await db.commit()
        for membership in created:
            await db.refresh(membership)
        await db.refresh(project)

    return AdminMembershipBulkResultDTO(
        created=[_membership_row(membership, users, {project.project_id: project}) for membership in created],
        skipped=skipped,
    )


async def list_policies(db: AsyncSession, *, page: int, page_size: int, query: str | None) -> tuple[list[PolicyListItemDTO], int]:
    documents = list((await db.execute(select(KnowledgeDocument).where(KnowledgeDocument.knowledge_domain == DocumentDomain.POLICY).order_by(KnowledgeDocument.created_at.desc()))).scalars())
    versions = list((await db.execute(select(DocumentVersion))).scalars())
    users = {user.user_id: user.display_name for user in (await db.execute(select(User))).scalars()}
    # Sắp xếp theo revision_no (int) chứ KHÔNG phải version_no — version_no là nhãn dạng
    # chuỗi từ tài liệu nguồn, so sánh chuỗi sẽ cho "10" < "9".
    latest_versions: dict[int, DocumentVersion] = {}
    for version in versions:
        previous = latest_versions.get(version.document_id)
        if previous is None or version.revision_no > previous.revision_no:
            latest_versions[version.document_id] = version
    normalized = query.strip().lower() if query else ""
    filtered = [
        document
        for document in documents
        if not normalized
        or normalized in document.title.lower()
        or (document.source_key or "").lower().find(normalized) >= 0
    ]
    selected, total = paginate(filtered, page, page_size)
    rows: list[PolicyListItemDTO] = []
    for document in selected:
        latest = latest_versions.get(document.document_id)
        rows.append(
            PolicyListItemDTO(
                document_id=document.document_id,
                title=document.title,
                policy_category=document.policy_category,
                source_key=document.source_key,
                version_no=latest.version_no if latest else None,
                revision_no=latest.revision_no if latest else None,
                effective_date=latest.effective_date if latest else None,
                version_status=latest.status if latest else None,
                created_by_name=users.get(document.created_by_user_id),
                status=document.status.value,
                created_at=document.created_at,
                requires_acknowledgement=document.requires_acknowledgement,
            )
        )
    return rows, total


async def get_policy_detail(db: AsyncSession, document_id: int) -> PolicyDetailDTO:
    document = await db.get(KnowledgeDocument, document_id)
    if document is None or document.knowledge_domain != DocumentDomain.POLICY:
        raise HTTPException(status_code=404, detail="Policy not found")
    versions = list((await db.execute(select(DocumentVersion).where(DocumentVersion.document_id == document_id))).scalars())
    latest = max(versions, key=lambda version: version.revision_no) if versions else None
    creator = await db.get(User, document.created_by_user_id)
    return PolicyDetailDTO(
        document_id=document.document_id,
        title=document.title,
        policy_category=document.policy_category,
        source_key=document.source_key,
        version_no=latest.version_no if latest else None,
        revision_no=latest.revision_no if latest else None,
        effective_date=latest.effective_date if latest else None,
        version_status=latest.status if latest else None,
        created_by_name=creator.display_name if creator else None,
        status=document.status.value,
        created_at=document.created_at,
        requires_acknowledgement=document.requires_acknowledgement,
        source_url=document.source_url,
    )


# create_policy() và create_policy_version() đã bị gỡ.
#
# Hai hàm đó tạo DocumentVersion thủ công và thiếu embedding_model_version / revision_no
# (hai cột NOT NULL thêm ở nhánh develop), nên chạy là lỗi IntegrityError. Nghiệp vụ tạo
# và version hoá chính sách giờ do TV3 lo trọn trong `ingest_policy_document()`; TV4 gọi
# qua `src/services/hr_policy_service.upload_policy()`.


async def archive_policy(db: AsyncSession, document_id: int) -> PolicyDetailDTO:
    document = await db.get(KnowledgeDocument, document_id)
    if document is None or document.knowledge_domain != DocumentDomain.POLICY:
        raise HTTPException(status_code=404, detail="Policy not found")
    document.status = DocumentStatus.ARCHIVED
    versions = list((await db.execute(select(DocumentVersion).where(DocumentVersion.document_id == document_id))).scalars())
    latest = max(versions, key=lambda version: version.revision_no) if versions else None
    if latest:
        latest.status = VersionStatus.ARCHIVED
    await db.commit()
    return await get_policy_detail(db, document_id)


async def restore_policy(db: AsyncSession, document_id: int) -> PolicyDetailDTO:
    """Reactivate the latest stored policy revision without creating new content."""
    document = await db.get(KnowledgeDocument, document_id)
    if document is None or document.knowledge_domain != DocumentDomain.POLICY:
        raise HTTPException(status_code=404, detail="Policy not found")

    versions = list(
        (
            await db.execute(
                select(DocumentVersion)
                .where(DocumentVersion.document_id == document_id)
                .order_by(DocumentVersion.revision_no.desc())
            )
        ).scalars()
    )
    if not versions:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "POLICY_HAS_NO_VERSION",
                "message": "Chính sách chưa có phiên bản để khôi phục.",
            },
        )

    latest = versions[0]
    for version in versions:
        version.status = VersionStatus.ARCHIVED

    # Flush the deactivation first so the partial unique constraint for one
    # ACTIVE revision per document cannot be hit while restoring an older row.
    await db.flush()
    latest.status = VersionStatus.ACTIVE
    document.status = DocumentStatus.ACTIVE
    await db.commit()
    return await get_policy_detail(db, document_id)


async def overview(db: AsyncSession) -> dict[str, int]:
    users = list((await db.execute(select(User))).scalars())
    projects = list((await db.execute(select(Project))).scalars())
    memberships = list((await db.execute(select(ProjectMembership))).scalars())
    active_user_ids = {membership.user_id for membership in memberships if membership.status == MembershipStatus.ACTIVE}
    # Phải truyền cùng dữ liệu như risk_items(), nếu không con số trên thẻ tổng quan sẽ
    # lệch với số dòng trong danh sách và không ai hiểu vì sao.
    policies = await _active_policies(db)
    return {
        "active_users": sum(user.status == UserStatus.ACTIVE for user in users),
        "active_projects": sum(project.status == ProjectStatus.ACTIVE for project in projects),
        "active_memberships": sum(membership.status == MembershipStatus.ACTIVE for membership in memberships),
        "unassigned_active_users": sum(user.status == UserStatus.ACTIVE and user.system_role is None and user.user_id not in active_user_ids for user in users),
        "total_users": len(users),
        "total_projects": len(projects),
        "total_memberships": len(memberships),
        "risk_count": len(
            _build_risk_items(
                users, projects, memberships, policies, await access_grant_service.overdue_pending(db)
            )
        ),
    }


# Chính sách hiệu lực quá mốc này bị coi là cần rà soát lại. Để hằng số ở đây thay vì
# rải số 365 giữa code, và để nhóm chỉnh một chỗ khi thấy ngưỡng gây nhiễu.
STALE_POLICY_MONTHS = 12

# Ngưỡng quá hạn của yêu cầu cấp quyền. Đọc lại từ access_grant_service thay vì khai
# một số 24 thứ hai ở đây — hai hằng số cùng nghĩa mà lệch nhau thì cảnh báo và hàng đợi
# sẽ nói hai chuyện khác nhau.
ACCESS_OVERDUE_HOURS = access_grant_service.PENDING_OVERDUE_HOURS


def _build_risk_items(
    users: Sequence[User],
    projects: Sequence[Project],
    memberships: Sequence[ProjectMembership],
    policies: Sequence[tuple[KnowledgeDocument, DocumentVersion]] = (),
    overdue_grants: Sequence[tuple[object, ProjectMembership]] = (),
) -> list[AdminRiskItemDTO]:
    """Detect access inconsistencies the admin should resolve, ordered by severity.

    Six classes of problem are surfaced:
      * HIGH  - a locked account still holds an active membership (stale access).
      * HIGH  - an active project has no active PM (nobody owns onboarding).
      * HIGH  - an access request has been waiting over a working day.
      * MEDIUM- an active account with no system role has no membership at all.
      * MEDIUM- a policy whose active version took effect over a year ago.
      * MEDIUM- a policy whose active version has no effective date at all.

    `policies` và `overdue_grants` mặc định rỗng để nơi gọi cũ không vỡ, nhưng cả hai
    nơi gọi trong module này đều truyền dữ liệu thật — nếu không, con số trên thẻ tổng
    quan sẽ lệch với số dòng trong danh sách.
    """
    users_by_id = {user.user_id: user for user in users}
    projects_by_id = {project.project_id: project for project in projects}
    active_memberships = [m for m in memberships if m.status == MembershipStatus.ACTIVE]
    assigned_user_ids = {m.user_id for m in active_memberships}
    items: list[AdminRiskItemDTO] = []

    for membership in active_memberships:
        user = users_by_id.get(membership.user_id)
        project = projects_by_id.get(membership.project_id)
        if user is None or project is None or user.status == UserStatus.ACTIVE:
            continue
        items.append(
            AdminRiskItemDTO(
                risk_id=f"stale-access-{membership.membership_id}",
                kind="INACTIVE_USER_IN_PROJECT",
                severity="HIGH",
                title=user.display_name,
                message=f'Tài khoản đã khóa nhưng vẫn còn membership hoạt động ở dự án "{project.name}".',
                action_label="Gỡ bỏ",
                user_id=user.user_id,
                user_email=user.email,
                membership_id=membership.membership_id,
                project_id=project.project_id,
                project_name=project.name,
                project_key=project.key,
            )
        )

    for project in projects:
        if project.status != ProjectStatus.ACTIVE:
            continue
        has_pm = any(
            m.project_id == project.project_id and m.project_role == ProjectRole.PM for m in active_memberships
        )
        if has_pm:
            continue
        items.append(
            AdminRiskItemDTO(
                risk_id=f"no-pm-{project.project_id}",
                kind="PROJECT_WITHOUT_PM",
                severity="HIGH",
                title=project.name,
                message="Dự án đang chạy nhưng chưa có PM phụ trách.",
                action_label="Gán PM",
                project_id=project.project_id,
                project_name=project.name,
                project_key=project.key,
            )
        )

    # Người mới ngồi chờ quyền repo sang ngày thứ hai thì buổi onboarding đã hỏng —
    # nên đây là HIGH, ngang với tài khoản khoá còn quyền. Gom theo người + dự án thay
    # vì một dòng mỗi quyền: bốn dòng "đang chờ" cho cùng một người là nhiễu, admin cần
    # biết "An chờ 4 quyền ở dự án X", không phải bốn lời nhắc riêng lẻ.
    grouped_overdue: dict[tuple[int, int], list[str]] = {}
    for grant, membership in overdue_grants:
        grouped_overdue.setdefault(
            (membership.user_id, membership.project_id), []
        ).append(getattr(grant, "resource_type", ""))

    for (overdue_user_id, overdue_project_id), resource_types in grouped_overdue.items():
        user = users_by_id.get(overdue_user_id)
        project = projects_by_id.get(overdue_project_id)
        if user is None or project is None:
            continue
        items.append(
            AdminRiskItemDTO(
                risk_id=f"access-overdue-{overdue_user_id}-{overdue_project_id}",
                kind="PENDING_ACCESS_OVERDUE",
                severity="HIGH",
                title=user.display_name,
                message=f'Đang chờ {len(resource_types)} quyền truy cập ở dự án "{project.name}" '
                f"quá {ACCESS_OVERDUE_HOURS} giờ.",
                action_label="Cấp quyền",
                user_id=user.user_id,
                user_email=user.email,
                project_id=project.project_id,
                project_name=project.name,
                project_key=project.key,
            )
        )

    for user in users:
        if user.status != UserStatus.ACTIVE or user.system_role is not None:
            continue
        if user.user_id in assigned_user_ids:
            continue
        items.append(
            AdminRiskItemDTO(
                risk_id=f"unassigned-{user.user_id}",
                kind="ACTIVE_USER_NO_MEMBERSHIP",
                severity="MEDIUM",
                title=user.display_name,
                message="Tài khoản đang hoạt động nhưng chưa có membership dự án.",
                action_label="Gán dự án",
                user_id=user.user_id,
                user_email=user.email,
            )
        )

    # Chính sách quá hạn rà soát. Tài liệu cũ mà trợ lý AI vẫn trích dẫn nguy hiểm hơn
    # không có tài liệu: người đọc nhận câu trả lời tự tin nhưng sai.
    stale_before = date.today() - timedelta(days=365 * STALE_POLICY_MONTHS // 12)
    for document, version in policies:
        if version.effective_date is None:
            items.append(
                AdminRiskItemDTO(
                    risk_id=f"policy-no-date-{document.document_id}",
                    kind="POLICY_MISSING_EFFECTIVE_DATE",
                    severity="MEDIUM",
                    title=document.title,
                    message="Chính sách đang hiệu lực nhưng không có ngày hiệu lực. "
                    "Không xác định được tài liệu còn phù hợp hay không.",
                    action_label="Bổ sung ngày",
                    document_id=document.document_id,
                )
            )
        elif version.effective_date < stale_before:
            items.append(
                AdminRiskItemDTO(
                    risk_id=f"stale-policy-{document.document_id}",
                    kind="STALE_POLICY",
                    severity="MEDIUM",
                    title=document.title,
                    message=f"Hiệu lực từ {version.effective_date:%d/%m/%Y}, đã quá "
                    f"{STALE_POLICY_MONTHS} tháng chưa cập nhật.",
                    action_label="Rà soát lại",
                    document_id=document.document_id,
                )
            )

    order = {"HIGH": 0, "MEDIUM": 1}
    items.sort(key=lambda item: (order[item.severity], item.kind, item.title))
    return items


async def _active_policies(
    db: AsyncSession,
) -> list[tuple[KnowledgeDocument, DocumentVersion]]:
    """Chính sách còn hiệu lực kèm phiên bản đang dùng.

    Tài liệu ARCHIVED bị loại: đã bỏ thì không cần cảnh báo quá hạn.
    """
    rows = await db.execute(
        select(KnowledgeDocument, DocumentVersion)
        .join(DocumentVersion, DocumentVersion.document_id == KnowledgeDocument.document_id)
        .where(
            KnowledgeDocument.knowledge_domain == DocumentDomain.POLICY,
            KnowledgeDocument.status == DocumentStatus.ACTIVE,
            DocumentVersion.status == VersionStatus.ACTIVE,
        )
    )
    return list(rows.all())


async def risk_items(db: AsyncSession, *, limit: int = 20) -> tuple[list[AdminRiskItemDTO], int]:
    users = list((await db.execute(select(User))).scalars())
    projects = list((await db.execute(select(Project))).scalars())
    memberships = list((await db.execute(select(ProjectMembership))).scalars())
    items = _build_risk_items(
        users,
        projects,
        memberships,
        await _active_policies(db),
        await access_grant_service.overdue_pending(db),
    )
    return items[:limit], len(items)


async def list_unassigned_users(
    db: AsyncSession, *, page: int, page_size: int, query: str | None = None
) -> tuple[list[AdminUnassignedUserDTO], int]:
    """Tài khoản ACTIVE, không có quyền hệ thống, và chưa có membership dự án nào.

    Loại ADMIN/HR có chủ ý — bản trước cố ý GIỮ họ lại và đó là quyết định sai, vì ba lý do:

    1. `create_membership` từ chối thẳng tài khoản có `system_role` ("Only active users
       without a system role can be assigned"). Nút "Gán membership" trên dòng của họ
       chắc chắn trả 422 — một nút không bao giờ hoạt động.
    2. `overview()["unassigned_active_users"]` đã lọc `system_role IS NULL` từ đầu. Giữ
       họ ở danh sách khiến màn hình hiện "2 tài khoản chưa gán" ngay cạnh "độ phủ 100%".
    3. Đây là danh sách việc-cần-làm. ADMIN/HR không bao giờ cần membership, nên họ nằm
       đó vĩnh viễn và dạy người dùng bỏ qua cả khối.
    """
    users = list((await db.execute(select(User).order_by(User.created_at.desc()))).scalars())
    memberships = list((await db.execute(select(ProjectMembership))).scalars())
    assigned_ids = {m.user_id for m in memberships if m.status == MembershipStatus.ACTIVE}
    inactive_counts: dict[int, int] = {}
    for membership in memberships:
        if membership.status != MembershipStatus.ACTIVE:
            inactive_counts[membership.user_id] = inactive_counts.get(membership.user_id, 0) + 1

    normalized = query.strip().lower() if query else ""
    filtered = [
        user
        for user in users
        if user.status == UserStatus.ACTIVE
        and user.system_role is None
        and user.user_id not in assigned_ids
        and (not normalized or normalized in user.display_name.lower() or normalized in user.email.lower())
    ]
    selected, total = paginate(filtered, page, page_size)
    return [
        AdminUnassignedUserDTO(
            user_id=user.user_id,
            display_name=user.display_name,
            email=user.email,
            system_role=user.system_role,
            created_at=user.created_at,
            inactive_membership_count=inactive_counts.get(user.user_id, 0),
        )
        for user in selected
    ], total


async def priority_users(db: AsyncSession) -> list[AdminPriorityUserDTO]:
    users = list((await db.execute(select(User).order_by(User.created_at.desc()))).scalars())
    memberships = list((await db.execute(select(ProjectMembership))).scalars())
    assigned_ids = {membership.user_id for membership in memberships if membership.status == MembershipStatus.ACTIVE}
    return [
        AdminPriorityUserDTO(user_id=user.user_id, display_name=user.display_name, email=user.email, created_at=user.created_at)
        for user in users
        if user.status == UserStatus.ACTIVE and user.system_role is None and user.user_id not in assigned_ids
    ][:5]


async def membership_eligibility(db: AsyncSession, project_id: int | None = None) -> MembershipEligibilityDTO:
    users = list((await db.execute(select(User).where(User.status == UserStatus.ACTIVE, User.system_role.is_(None)).order_by(User.display_name))).scalars())
    projects = list((await db.execute(select(Project).where(Project.status == ProjectStatus.ACTIVE).order_by(Project.name))).scalars())
    if project_id is not None:
        # Adding from a project drawer: hide people who already hold a membership here,
        # since the unique (user, project) constraint would reject them with a 409.
        taken = {
            membership.user_id
            for membership in (
                await db.execute(
                    select(ProjectMembership).where(ProjectMembership.project_id == project_id)
                )
            ).scalars()
        }
        users = [user for user in users if user.user_id not in taken]
    return MembershipEligibilityDTO(
        users=[MembershipEligibleUserDTO(user_id=user.user_id, display_name=user.display_name, email=user.email) for user in users],
        projects=[MembershipEligibleProjectDTO(project_id=project.project_id, name=project.name, key=project.key) for project in projects],
    )
