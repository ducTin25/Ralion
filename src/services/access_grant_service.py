"""Hàng đợi cấp quyền truy cập (đề xuất A) và thu hồi khi rời dự án (đề xuất D).

Bốn quy tắc nghiệp vụ ghi tường minh ở đây, không để ngầm định:

1. **Yêu cầu do hệ thống tự sinh, không phải kỹ sư tự xin.** Người mới ngày đầu chưa
   biết mình cần quyền gì để mà xin — đó chính là vấn đề cần giải quyết. Gán vào dự án
   là sinh ngay bộ quyền chuẩn ở trạng thái REQUESTED.

2. **Chỉ ADMIN được cấp và thu hồi.** Khớp với `require_admin` đã có, không phát sinh
   tầng phân quyền mới.

3. **Thu hồi không xoá bản ghi.** `revoked_at` là bằng chứng đã thu hồi — thứ mà kiểm
   toán hỏi tới, và là lý do tồn tại của cả bảng.

4. **Ngừng membership KHÔNG tự thu hồi quyền.** Cố ý. Gỡ quyền trên GitHub/Jira/VPN là
   việc phải làm bằng tay ở hệ thống khác; đánh dấu REVOKED tự động sẽ tạo ra một danh
   sách sạch sẽ nói dối rằng mọi thứ đã được gỡ. Hệ thống chỉ đưa ra checklist và bắt
   admin tự tick.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.model.access_grant import AccessGrant
from src.model.enums import (
    AccessGrantStatus,
    AccessResourceType,
    MembershipStatus,
    ProjectRole,
    UserStatus,
)
from src.model.project import Project
from src.model.project_membership import ProjectMembership
from src.model.user import User

# Bộ quyền tự sinh khi một người được gán vào dự án. Cố ý ngắn — bốn thứ gần như kỹ sư
# nào cũng cần. Thêm quyền đặc thù là việc của admin, không nên bắt mọi dự án gánh một
# danh sách dài rồi phải thu hồi hàng loạt thứ chưa bao giờ dùng.
DEFAULT_ENGINEER_RESOURCES: tuple[AccessResourceType, ...] = (
    AccessResourceType.REPOSITORY,
    AccessResourceType.ISSUE_TRACKER,
    AccessResourceType.CI_CD,
    AccessResourceType.DATABASE,
)

# PM cần thêm quyền quản lý bí mật (biến môi trường, khoá triển khai) vì họ là người
# cấu hình môi trường cho cả nhóm.
DEFAULT_PM_EXTRA_RESOURCES: tuple[AccessResourceType, ...] = (AccessResourceType.SECRETS,)

# Yêu cầu chưa xử lý quá mốc này bị coi là quá hạn và nổi lên bảng cảnh báo của admin.
# Một ngày làm việc là ngưỡng hợp lý: người mới ngồi chờ quyền repo sang ngày thứ hai
# thì buổi onboarding đã hỏng.
PENDING_OVERDUE_HOURS = 24

RESOURCE_LABELS: dict[AccessResourceType, str] = {
    AccessResourceType.REPOSITORY: "Mã nguồn (repository)",
    AccessResourceType.ISSUE_TRACKER: "Quản lý công việc (Jira/Linear)",
    AccessResourceType.CI_CD: "CI/CD",
    AccessResourceType.DATABASE: "Cơ sở dữ liệu",
    AccessResourceType.SECRETS: "Biến môi trường & khoá bí mật",
    AccessResourceType.VPN: "VPN / mạng nội bộ",
    AccessResourceType.OTHER: "Khác",
}


def default_resources_for(project_role: ProjectRole) -> tuple[AccessResourceType, ...]:
    if project_role == ProjectRole.PM:
        return DEFAULT_ENGINEER_RESOURCES + DEFAULT_PM_EXTRA_RESOURCES
    return DEFAULT_ENGINEER_RESOURCES


def _now() -> datetime:
    """Thời điểm hiện tại theo UTC, bỏ timezone.

    Hai lý do phải tự đặt giá trị thay vì để `server_default=func.now()` lo:

    1. Cột là `DateTime` naive. Trộn aware và naive trong cùng một cột là cách chắc chắn
       nhất để phép trừ ném TypeError ở production mà test SQLite không bắt được.
    2. `func.now()` của PostgreSQL trả giờ theo timezone của server khi ghi vào cột
       không timezone. Nếu server chạy giờ Việt Nam thì `requested_at` lệch 7 tiếng so
       với `_now()` ở đây, và mọi phép tính "đã chờ bao lâu" sai đúng 7 giờ — đủ để một
       yêu cầu vừa tạo bị báo quá hạn ngay lập tức.

    Vì vậy MỌI nơi tạo `AccessGrant` đều truyền `requested_at=_now()` tường minh.
    `server_default` chỉ còn là lưới an toàn cho INSERT viết tay.
    """
    return datetime.now(UTC).replace(tzinfo=None)


async def seed_grants_for_membership(
    db: AsyncSession, membership: ProjectMembership
) -> list[AccessGrant]:
    """Sinh bộ quyền chuẩn cho một membership vừa tạo.

    KHÔNG commit — nơi gọi đang ở giữa transaction tạo membership, và quyền chỉ nên tồn
    tại nếu membership tồn tại. Chỉ `flush` để lấy khoá chính.

    Bỏ qua loại tài nguyên đã có bản ghi chưa REVOKED, nên gọi lại nhiều lần cũng không
    sinh trùng (ví dụ khi membership INACTIVE được bật lại thành ACTIVE).
    """
    existing = {
        grant.resource_type
        for grant in (
            await db.execute(
                select(AccessGrant).where(
                    AccessGrant.membership_id == membership.membership_id,
                    AccessGrant.status != AccessGrantStatus.REVOKED,
                )
            )
        ).scalars()
    }

    created: list[AccessGrant] = []
    for resource_type in default_resources_for(membership.project_role):
        if resource_type in existing:
            continue
        grant = AccessGrant(
            membership_id=membership.membership_id,
            resource_type=resource_type,
            status=AccessGrantStatus.REQUESTED,
            requested_at=_now(),
        )
        db.add(grant)
        created.append(grant)

    if created:
        await db.flush()
    return created


async def _load_grant(db: AsyncSession, grant_id: int) -> AccessGrant:
    grant = await db.get(AccessGrant, grant_id)
    if grant is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "GRANT_NOT_FOUND", "message": "Không tìm thấy yêu cầu cấp quyền."},
        )
    return grant


async def grant_access(
    db: AsyncSession, actor: User, grant_id: int, *, resource_note: str | None = None
) -> AccessGrant:
    """Admin xác nhận đã cấp quyền thật ở hệ thống bên ngoài.

    Idempotent: bấm hai lần trả cùng kết quả, không đè lại `granted_at` — thời điểm cấp
    lần đầu mới là dữ liệu có ý nghĩa.
    """
    grant = await _load_grant(db, grant_id)
    if grant.status == AccessGrantStatus.REVOKED:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "GRANT_REVOKED",
                "message": "Quyền này đã bị thu hồi. Hãy tạo yêu cầu mới nếu cần cấp lại.",
            },
        )
    if grant.status == AccessGrantStatus.GRANTED:
        if resource_note is not None:
            grant.resource_note = resource_note.strip() or None
            await db.commit()
            await db.refresh(grant)
        return grant

    grant.status = AccessGrantStatus.GRANTED
    grant.granted_by_admin_id = actor.user_id
    grant.granted_at = _now()
    if resource_note is not None:
        grant.resource_note = resource_note.strip() or None
    await db.commit()
    await db.refresh(grant)
    return grant


async def revoke_access(db: AsyncSession, grant_id: int) -> AccessGrant:
    """Đánh dấu đã thu hồi. Áp dụng được cho cả REQUESTED (huỷ yêu cầu chưa xử lý)."""
    grant = await _load_grant(db, grant_id)
    if grant.status == AccessGrantStatus.REVOKED:
        return grant
    grant.status = AccessGrantStatus.REVOKED
    grant.revoked_at = _now()
    await db.commit()
    await db.refresh(grant)
    return grant


async def add_grant(
    db: AsyncSession,
    membership_id: int,
    resource_type: AccessResourceType,
    *,
    resource_note: str | None = None,
) -> AccessGrant:
    """Thêm một quyền ngoài bộ chuẩn (VPN, hệ thống nội bộ khác...)."""
    membership = await db.get(ProjectMembership, membership_id)
    if membership is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "MEMBERSHIP_NOT_FOUND", "message": "Không tìm thấy membership."},
        )
    duplicate = await db.scalar(
        select(AccessGrant).where(
            AccessGrant.membership_id == membership_id,
            AccessGrant.resource_type == resource_type,
            AccessGrant.status != AccessGrantStatus.REVOKED,
        )
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "GRANT_ALREADY_EXISTS",
                "message": "Loại quyền này đã có trong danh sách và chưa bị thu hồi.",
            },
        )
    grant = AccessGrant(
        membership_id=membership_id,
        resource_type=resource_type,
        resource_note=(resource_note or "").strip() or None,
        status=AccessGrantStatus.REQUESTED,
        requested_at=_now(),
    )
    db.add(grant)
    await db.commit()
    await db.refresh(grant)
    return grant


async def _context_for(
    db: AsyncSession, grants: list[AccessGrant]
) -> tuple[dict[int, ProjectMembership], dict[int, User], dict[int, Project]]:
    membership_ids = {grant.membership_id for grant in grants}
    if not membership_ids:
        return {}, {}, {}
    memberships = {
        m.membership_id: m
        for m in (
            await db.execute(
                select(ProjectMembership).where(
                    ProjectMembership.membership_id.in_(membership_ids)
                )
            )
        ).scalars()
    }
    users = {u.user_id: u for u in (await db.execute(select(User))).scalars()}
    projects = {p.project_id: p for p in (await db.execute(select(Project))).scalars()}
    return memberships, users, projects


def _row(
    grant: AccessGrant,
    memberships: dict[int, ProjectMembership],
    users: dict[int, User],
    projects: dict[int, Project],
    *,
    now: datetime,
) -> dict:
    membership = memberships.get(grant.membership_id)
    user = users.get(membership.user_id) if membership else None
    project = projects.get(membership.project_id) if membership else None
    granter = users.get(grant.granted_by_admin_id) if grant.granted_by_admin_id else None

    waiting_hours = (now - grant.requested_at).total_seconds() / 3600
    return {
        "grant_id": grant.grant_id,
        "membership_id": grant.membership_id,
        "resource_type": grant.resource_type,
        "resource_label": RESOURCE_LABELS[grant.resource_type],
        "resource_note": grant.resource_note,
        "status": grant.status,
        "requested_at": grant.requested_at,
        "granted_at": grant.granted_at,
        "revoked_at": grant.revoked_at,
        "granted_by_name": granter.display_name if granter else None,
        "user_id": user.user_id if user else None,
        "user_name": user.display_name if user else None,
        "user_email": user.email if user else None,
        "project_id": project.project_id if project else None,
        "project_name": project.name if project else None,
        "project_key": project.key if project else None,
        # Toạ độ GitHub của dự án, để màn hình cấp quyền điền sẵn ô ghi chú thay vì bắt
        # admin tự nhớ. `pending/<key>` là giá trị giả gán lúc tạo project nên bỏ qua —
        # điền nó vào là ghi lại một tên repo không tồn tại.
        "project_repo": (
            project.github_repo
            if project and project.github_repo and not project.github_repo.startswith("pending/")
            else None
        ),
        "project_role": membership.project_role if membership else None,
        "membership_status": membership.status if membership else None,
        # Chỉ yêu cầu CHƯA xử lý mới tính quá hạn. Quyền đã cấp thì thời gian chờ không
        # còn là vấn đề đang mở.
        "is_overdue": (
            grant.status == AccessGrantStatus.REQUESTED and waiting_hours >= PENDING_OVERDUE_HOURS
        ),
        "waiting_hours": round(waiting_hours, 1) if grant.status == AccessGrantStatus.REQUESTED else None,
    }


async def list_queue(
    db: AsyncSession,
    *,
    status: AccessGrantStatus | None = AccessGrantStatus.REQUESTED,
    project_id: int | None = None,
) -> list[dict]:
    """Hàng đợi cho admin: mặc định chỉ yêu cầu chưa xử lý, cũ nhất lên trước.

    Cũ nhất lên trước là có chủ ý — hàng đợi sắp xếp theo thời điểm yêu cầu giảm dần sẽ
    đẩy người chờ lâu nhất xuống cuối, đúng người cần được xử lý trước lại bị bỏ quên.
    """
    query = select(AccessGrant).order_by(AccessGrant.requested_at.asc())
    if status is not None:
        query = query.where(AccessGrant.status == status)
    grants = list((await db.execute(query)).scalars())

    memberships, users, projects = await _context_for(db, grants)
    if project_id is not None:
        grants = [
            grant
            for grant in grants
            if (m := memberships.get(grant.membership_id)) is not None
            and m.project_id == project_id
        ]

    now = _now()
    return [_row(grant, memberships, users, projects, now=now) for grant in grants]


async def queue_summary(db: AsyncSession) -> dict[str, int]:
    grants = list((await db.execute(select(AccessGrant))).scalars())
    now = _now()
    pending = [g for g in grants if g.status == AccessGrantStatus.REQUESTED]
    return {
        "pending": len(pending),
        "overdue": sum(
            1
            for g in pending
            if (now - g.requested_at) >= timedelta(hours=PENDING_OVERDUE_HOURS)
        ),
        "granted": sum(1 for g in grants if g.status == AccessGrantStatus.GRANTED),
        "revoked": sum(1 for g in grants if g.status == AccessGrantStatus.REVOKED),
    }


async def list_for_user(db: AsyncSession, user: User) -> list[dict]:
    """Quyền của chính người đang đăng nhập, mọi dự án còn hoạt động.

    Thay cho việc nhắn Slack hỏi mò "quyền repo của em xong chưa" — kỹ sư tự thấy đang
    chờ gì và ai đã xử lý.
    """
    memberships = list(
        (
            await db.execute(
                select(ProjectMembership).where(
                    ProjectMembership.user_id == user.user_id,
                    ProjectMembership.status == MembershipStatus.ACTIVE,
                )
            )
        ).scalars()
    )
    if not memberships:
        return []

    membership_ids = [m.membership_id for m in memberships]
    grants = list(
        (
            await db.execute(
                select(AccessGrant)
                .where(
                    AccessGrant.membership_id.in_(membership_ids),
                    AccessGrant.status != AccessGrantStatus.REVOKED,
                )
                .order_by(AccessGrant.requested_at.asc())
            )
        ).scalars()
    )

    memberships_by_id = {m.membership_id: m for m in memberships}
    users = {user.user_id: user}
    granter_ids = {g.granted_by_admin_id for g in grants if g.granted_by_admin_id}
    if granter_ids:
        for granter in (
            await db.execute(select(User).where(User.user_id.in_(granter_ids)))
        ).scalars():
            users[granter.user_id] = granter
    projects = {
        p.project_id: p
        for p in (
            await db.execute(
                select(Project).where(
                    Project.project_id.in_({m.project_id for m in memberships})
                )
            )
        ).scalars()
    }

    now = _now()
    return [_row(grant, memberships_by_id, users, projects, now=now) for grant in grants]


async def list_for_membership(db: AsyncSession, membership_id: int) -> list[dict]:
    grants = list(
        (
            await db.execute(
                select(AccessGrant)
                .where(AccessGrant.membership_id == membership_id)
                .order_by(AccessGrant.requested_at.asc())
            )
        ).scalars()
    )
    memberships, users, projects = await _context_for(db, grants)
    now = _now()
    return [_row(grant, memberships, users, projects, now=now) for grant in grants]


async def deactivation_preview(db: AsyncSession, user_id: int) -> dict:
    """Hậu quả của việc khoá một tài khoản, tính TRƯỚC khi khoá.

    Lý do tồn tại: nút khoá tài khoản hiện không hỏi gì cả. Admin bấm xong không biết
    vừa cắt đứt những gì. Màn hình xác nhận chỉ có giá trị khi nó nói được con số cụ
    thể — "sẽ ngừng 3 membership và 5 quyền cần thu hồi tay" khác hẳn "bạn có chắc không".

    Danh sách quyền ở đây là checklist thủ công: hệ thống không tự gỡ được quyền trên
    GitHub hay VPN, nên nó liệt kê ra và để admin tự tick.
    """
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "USER_NOT_FOUND", "message": "Không tìm thấy tài khoản."},
        )

    memberships = list(
        (
            await db.execute(
                select(ProjectMembership).where(
                    ProjectMembership.user_id == user_id,
                    ProjectMembership.status == MembershipStatus.ACTIVE,
                )
            )
        ).scalars()
    )
    projects = {
        p.project_id: p
        for p in (
            await db.execute(
                select(Project).where(
                    Project.project_id.in_({m.project_id for m in memberships} or {-1})
                )
            )
        ).scalars()
    }

    grants: list[AccessGrant] = []
    if memberships:
        grants = list(
            (
                await db.execute(
                    select(AccessGrant).where(
                        AccessGrant.membership_id.in_([m.membership_id for m in memberships]),
                        AccessGrant.status == AccessGrantStatus.GRANTED,
                    )
                )
            ).scalars()
        )

    memberships_by_id = {m.membership_id: m for m in memberships}
    return {
        "user_id": user.user_id,
        "display_name": user.display_name,
        "email": user.email,
        "is_primary_pm_of": [
            {
                "project_id": project.project_id,
                "project_name": project.name,
                "project_key": project.key,
            }
            for project in projects.values()
            if project.primary_pm_membership_id in memberships_by_id
        ],
        "memberships": [
            {
                "membership_id": m.membership_id,
                "project_id": m.project_id,
                "project_name": projects[m.project_id].name,
                "project_key": projects[m.project_id].key,
                "project_role": m.project_role,
            }
            for m in memberships
            if m.project_id in projects
        ],
        "granted_access": [
            {
                "grant_id": grant.grant_id,
                "resource_type": grant.resource_type,
                "resource_label": RESOURCE_LABELS[grant.resource_type],
                "resource_note": grant.resource_note,
                "project_name": projects[memberships_by_id[grant.membership_id].project_id].name
                if memberships_by_id[grant.membership_id].project_id in projects
                else None,
            }
            for grant in grants
        ],
        # Luôn True khi tài khoản đang hoạt động: khoá tài khoản là đóng dấu
        # `session_invalid_before`, mọi cookie đang mở chết ngay ở request kế tiếp.
        "will_revoke_sessions": user.status == UserStatus.ACTIVE,
    }


async def membership_offboarding_preview(db: AsyncSession, membership_id: int) -> dict:
    """Hậu quả của việc ngừng một membership — bản hẹp của `deactivation_preview`.

    Khác biệt quan trọng: KHÔNG cắt phiên đăng nhập. Rời một dự án không phải rời công
    ty; người đó vẫn làm việc bình thường ở dự án khác.
    """
    membership = await db.get(ProjectMembership, membership_id)
    if membership is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "MEMBERSHIP_NOT_FOUND", "message": "Không tìm thấy membership."},
        )
    user = await db.get(User, membership.user_id)
    project = await db.get(Project, membership.project_id)

    grants = list(
        (
            await db.execute(
                select(AccessGrant).where(
                    AccessGrant.membership_id == membership_id,
                    AccessGrant.status == AccessGrantStatus.GRANTED,
                )
            )
        ).scalars()
    )
    return {
        "membership_id": membership_id,
        "user_id": membership.user_id,
        "display_name": user.display_name if user else "",
        "project_id": membership.project_id,
        "project_name": project.name if project else "",
        "project_key": project.key if project else "",
        "is_primary_pm": bool(project and project.primary_pm_membership_id == membership_id),
        "granted_access": [
            {
                "grant_id": grant.grant_id,
                "resource_type": grant.resource_type,
                "resource_label": RESOURCE_LABELS[grant.resource_type],
                "resource_note": grant.resource_note,
                "project_name": project.name if project else None,
            }
            for grant in grants
        ],
    }


async def revoke_all_for_membership(db: AsyncSession, membership_id: int) -> int:
    """Tick toàn bộ checklist một lượt. Trả về số quyền vừa đánh dấu thu hồi."""
    grants = list(
        (
            await db.execute(
                select(AccessGrant).where(
                    AccessGrant.membership_id == membership_id,
                    AccessGrant.status != AccessGrantStatus.REVOKED,
                )
            )
        ).scalars()
    )
    now = _now()
    for grant in grants:
        grant.status = AccessGrantStatus.REVOKED
        grant.revoked_at = now
    if grants:
        await db.commit()
    return len(grants)


async def overdue_pending(db: AsyncSession) -> list[tuple[AccessGrant, ProjectMembership]]:
    """Yêu cầu chưa xử lý quá `PENDING_OVERDUE_HOURS`, kèm membership để dựng cảnh báo."""
    cutoff = _now() - timedelta(hours=PENDING_OVERDUE_HOURS)
    rows = await db.execute(
        select(AccessGrant, ProjectMembership)
        .join(ProjectMembership, ProjectMembership.membership_id == AccessGrant.membership_id)
        .where(
            AccessGrant.status == AccessGrantStatus.REQUESTED,
            AccessGrant.requested_at <= cutoff,
            ProjectMembership.status == MembershipStatus.ACTIVE,
        )
    )
    return list(rows.all())
