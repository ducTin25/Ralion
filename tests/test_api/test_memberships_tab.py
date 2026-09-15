"""Kiểm thử phần bổ sung cho tab Membership: đếm quyền, đổi vai trò, lọc theo dự án."""

import pytest

from src.api.dependencies import get_current_user, get_current_user_id, get_session_issued_at
from src.main import app
from src.model.enums import MembershipStatus, ProjectRole, ProjectStatus, UserRole, UserStatus
from src.model.project import Project
from src.model.project_membership import ProjectMembership
from src.model.user import User
from src.services import access_grant_service
from src.services.auth_service import hash_password

API = "/api/v1/console"


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    for dependency in (get_current_user, get_current_user_id, get_session_issued_at):
        app.dependency_overrides.pop(dependency, None)


async def seed_admin(db_session) -> User:
    admin = User(
        email="admin@onboarding.dev",
        display_name="Admin Root",
        password_hash=hash_password("admin-password"),
        system_role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[get_current_user_id] = lambda: admin.user_id
    return admin


async def seed_project(db_session, admin: User, *, key: str = "BO06") -> Project:
    project = Project(
        name=f"Dự án {key}",
        key=key,
        status=ProjectStatus.ACTIVE,
        created_by_admin_id=admin.user_id,
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


async def seed_member(
    db_session,
    admin: User,
    project: Project,
    *,
    email: str = "an@onboarding.dev",
    role: ProjectRole = ProjectRole.ENGINEER,
    with_grants: bool = True,
) -> ProjectMembership:
    user = User(
        email=email,
        display_name="Nguyễn An",
        password_hash=hash_password("mat-khau"),
        system_role=None,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    membership = ProjectMembership(
        user_id=user.user_id,
        project_id=project.project_id,
        project_role=role,
        status=MembershipStatus.ACTIVE,
        assigned_by_admin_id=admin.user_id,
    )
    db_session.add(membership)
    await db_session.commit()
    await db_session.refresh(membership)
    if (
        membership.project_role == ProjectRole.PM
        and membership.status == MembershipStatus.ACTIVE
        and project.primary_pm_membership_id is None
    ):
        project.primary_pm_membership_id = membership.membership_id
        await db_session.commit()
        await db_session.refresh(project)
    if with_grants:
        await access_grant_service.seed_grants_for_membership(db_session, membership)
        await db_session.commit()
    return membership


# ------------------------------------------------------- đếm quyền theo membership


@pytest.mark.asyncio
async def test_dem_quyen_da_cap_va_dang_cho(db_client, db_session):
    admin = await seed_admin(db_session)
    project = await seed_project(db_session, admin)
    membership = await seed_member(db_session, admin, project)

    grants = (
        await db_client.get(f"{API}/admin/memberships/{membership.membership_id}/access-grants")
    ).json()["items"]
    await db_client.patch(f"{API}/admin/access-grants/{grants[0]['grant_id']}/grant", json={})

    rows = (await db_client.get(f"{API}/admin/memberships?page=1&page_size=20")).json()["items"]
    row = next(r for r in rows if r["membership_id"] == membership.membership_id)
    assert row["granted_access_count"] == 1
    assert row["pending_access_count"] == 3


@pytest.mark.asyncio
async def test_quyen_da_thu_hoi_khong_tinh_vao_hai_con_so(db_client, db_session):
    """REVOKED là lịch sử, không phải quyền đang tồn tại."""
    admin = await seed_admin(db_session)
    project = await seed_project(db_session, admin)
    membership = await seed_member(db_session, admin, project)

    grants = (
        await db_client.get(f"{API}/admin/memberships/{membership.membership_id}/access-grants")
    ).json()["items"]
    await db_client.patch(f"{API}/admin/access-grants/{grants[0]['grant_id']}/revoke")

    rows = (await db_client.get(f"{API}/admin/memberships?page=1&page_size=20")).json()["items"]
    row = next(r for r in rows if r["membership_id"] == membership.membership_id)
    assert row["granted_access_count"] + row["pending_access_count"] == 3


@pytest.mark.asyncio
async def test_membership_khong_co_quyen_tra_ve_khong(db_client, db_session):
    admin = await seed_admin(db_session)
    project = await seed_project(db_session, admin)
    membership = await seed_member(db_session, admin, project, with_grants=False)

    rows = (await db_client.get(f"{API}/admin/memberships?page=1&page_size=20")).json()["items"]
    row = next(r for r in rows if r["membership_id"] == membership.membership_id)
    assert row["granted_access_count"] == 0
    assert row["pending_access_count"] == 0


# --------------------------------------------------------------- đổi vai trò


@pytest.mark.asyncio
async def test_nang_ky_su_len_pm(db_client, db_session):
    admin = await seed_admin(db_session)
    project = await seed_project(db_session, admin)
    membership = await seed_member(db_session, admin, project, with_grants=False)

    response = await db_client.patch(
        f"{API}/admin/memberships/{membership.membership_id}", json={"project_role": "PM"}
    )
    assert response.status_code == 200
    assert response.json()["project_role"] == "PM"


@pytest.mark.asyncio
async def test_ha_pm_chinh_xuong_ky_su_go_luon_vi_tri_phu_trach(db_client, db_session):
    """Hậu quả lan ra ngoài dòng đang thao tác, nên hộp thoại phải cảnh báo trước."""
    admin = await seed_admin(db_session)
    project = await seed_project(db_session, admin)
    pm = await seed_member(
        db_session, admin, project, email="pm@onboarding.dev", role=ProjectRole.PM
    )

    await db_session.refresh(project)
    assert project.primary_pm_membership_id == pm.membership_id

    await db_client.patch(
        f"{API}/admin/memberships/{pm.membership_id}", json={"project_role": "ENGINEER"}
    )
    await db_session.refresh(project)
    assert project.primary_pm_membership_id is None

    detail = (await db_client.get(f"{API}/admin/projects/{project.project_id}")).json()
    assert detail["primary_pm_name"] is None


@pytest.mark.asyncio
async def test_nang_len_pm_sinh_them_quyen_secrets(db_client, db_session):
    """PM cần thêm quyền bí mật; seed chạy lại không được nhân đôi bộ quyền cũ."""
    admin = await seed_admin(db_session)
    project = await seed_project(db_session, admin)
    membership = await seed_member(db_session, admin, project)

    await db_client.patch(
        f"{API}/admin/memberships/{membership.membership_id}", json={"project_role": "PM"}
    )
    grants = (
        await db_client.get(f"{API}/admin/memberships/{membership.membership_id}/access-grants")
    ).json()["items"]
    types = [row["resource_type"] for row in grants]
    assert "SECRETS" in types
    assert len(types) == len(set(types))


# ------------------------------------------------------------- lọc theo dự án


@pytest.mark.asyncio
async def test_loc_membership_theo_du_an(db_client, db_session):
    """Bộ lọc này được nút "Gán PM" ở trang tổng quan dùng qua tham số URL."""
    admin = await seed_admin(db_session)
    first = await seed_project(db_session, admin, key="AAA")
    second = await seed_project(db_session, admin, key="BBB")
    m1 = await seed_member(db_session, admin, first, email="a@onboarding.dev", with_grants=False)
    await seed_member(db_session, admin, second, email="b@onboarding.dev", with_grants=False)

    rows = (
        await db_client.get(
            f"{API}/admin/memberships?page=1&page_size=20&project_id={first.project_id}"
        )
    ).json()["items"]
    assert {row["membership_id"] for row in rows} == {m1.membership_id}


# ------------------------------------------- xem trước khi tạm ngừng membership


@pytest.mark.asyncio
async def test_xem_truoc_tam_ngung_liet_ke_quyen_da_cap(db_client, db_session):
    admin = await seed_admin(db_session)
    project = await seed_project(db_session, admin)
    membership = await seed_member(db_session, admin, project)

    grants = (
        await db_client.get(f"{API}/admin/memberships/{membership.membership_id}/access-grants")
    ).json()["items"]
    await db_client.patch(f"{API}/admin/access-grants/{grants[0]['grant_id']}/grant", json={})
    await db_client.patch(f"{API}/admin/access-grants/{grants[1]['grant_id']}/grant", json={})

    preview = (
        await db_client.get(f"{API}/admin/memberships/{membership.membership_id}/offboarding-preview")
    ).json()
    # Chỉ quyền ĐÃ CẤP mới cần thu hồi; yêu cầu chưa xử lý thì không có gì để gỡ.
    assert len(preview["granted_access"]) == 2
    assert preview["is_primary_pm"] is False
