"""Kiểm thử phần bổ sung cho tab Người dùng: reset mật khẩu, sửa hồ sơ, đếm quyền chờ."""

import pytest

from src.api.dependencies import get_current_user, get_current_user_id, get_session_issued_at
from src.main import app
from src.model.enums import (
    MembershipStatus,
    ProjectRole,
    ProjectStatus,
    UserRole,
    UserStatus,
)
from src.model.project import Project
from src.model.project_membership import ProjectMembership
from src.model.user import User
from src.services import access_grant_service
from src.services.auth_service import hash_password, verify_password

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


async def seed_engineer(db_session, *, email: str = "an@onboarding.dev") -> User:
    engineer = User(
        email=email,
        display_name="Nguyễn An",
        password_hash=hash_password("mat-khau-cu"),
        system_role=None,
        status=UserStatus.ACTIVE,
        must_change_password=False,
    )
    db_session.add(engineer)
    await db_session.commit()
    await db_session.refresh(engineer)
    return engineer


# ------------------------------------------------------------ reset mật khẩu


@pytest.mark.asyncio
async def test_reset_mat_khau_doi_hash_va_bat_co_doi_lai(db_client, db_session):
    await seed_admin(db_session)
    engineer = await seed_engineer(db_session)
    old_hash = engineer.password_hash

    response = await db_client.patch(
        f"{API}/admin/users/{engineer.user_id}/password",
        json={"new_password": "mat-khau-moi-123"},
    )
    assert response.status_code == 200
    assert response.json()["must_change_password"] is True

    await db_session.refresh(engineer)
    assert engineer.password_hash != old_hash
    assert verify_password("mat-khau-moi-123", engineer.password_hash)


@pytest.mark.asyncio
async def test_reset_mat_khau_qua_ngan_bi_tu_choi(db_client, db_session):
    await seed_admin(db_session)
    engineer = await seed_engineer(db_session)

    response = await db_client.patch(
        f"{API}/admin/users/{engineer.user_id}/password", json={"new_password": "ngan"}
    )
    assert response.status_code == 422


# --------------------------------------------------------------- sửa hồ sơ


@pytest.mark.asyncio
async def test_sua_ten_va_email(db_client, db_session):
    await seed_admin(db_session)
    engineer = await seed_engineer(db_session)

    response = await db_client.patch(
        f"{API}/admin/users/{engineer.user_id}",
        json={"display_name": "Nguyễn Văn An", "email": "an.nguyen@onboarding.dev"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Nguyễn Văn An"
    assert body["email"] == "an.nguyen@onboarding.dev"


@pytest.mark.asyncio
async def test_cap_va_go_quyen_he_thong(db_client, db_session):
    """`clear_system_role` tồn tại vì `None` không phân biệt được "không đổi" với "gỡ"."""
    await seed_admin(db_session)
    engineer = await seed_engineer(db_session)

    promoted = await db_client.patch(
        f"{API}/admin/users/{engineer.user_id}", json={"system_role": "HR"}
    )
    assert promoted.json()["system_role"] == "HR"

    # Gửi lại một trường khác mà KHÔNG kèm system_role: quyền phải giữ nguyên.
    kept = await db_client.patch(
        f"{API}/admin/users/{engineer.user_id}", json={"display_name": "Nguyễn An"}
    )
    assert kept.json()["system_role"] == "HR"

    removed = await db_client.patch(
        f"{API}/admin/users/{engineer.user_id}", json={"clear_system_role": True}
    )
    assert removed.json()["system_role"] is None


# ------------------------------------------- đếm quyền chờ + lọc mật khẩu


async def seed_membership_with_grants(db_session, admin: User, engineer: User) -> ProjectMembership:
    project = Project(
        name="Dự án BO06",
        key="BO06",
        status=ProjectStatus.ACTIVE,
        created_by_admin_id=admin.user_id,
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    membership = ProjectMembership(
        user_id=engineer.user_id,
        project_id=project.project_id,
        project_role=ProjectRole.ENGINEER,
        status=MembershipStatus.ACTIVE,
        assigned_by_admin_id=admin.user_id,
    )
    db_session.add(membership)
    await db_session.commit()
    await db_session.refresh(membership)
    await access_grant_service.seed_grants_for_membership(db_session, membership)
    await db_session.commit()
    return membership


@pytest.mark.asyncio
async def test_dem_so_quyen_dang_cho_cap(db_client, db_session):
    admin = await seed_admin(db_session)
    engineer = await seed_engineer(db_session)
    await seed_membership_with_grants(db_session, admin, engineer)

    rows = (await db_client.get(f"{API}/admin/users?page=1&page_size=20")).json()["items"]
    row = next(r for r in rows if r["user_id"] == engineer.user_id)
    assert row["pending_access_count"] == 4

    detail = (await db_client.get(f"{API}/admin/users/{engineer.user_id}")).json()
    assert detail["pending_access_count"] == 4


@pytest.mark.asyncio
async def test_cap_quyen_lam_giam_so_dang_cho(db_client, db_session):
    admin = await seed_admin(db_session)
    engineer = await seed_engineer(db_session)
    membership = await seed_membership_with_grants(db_session, admin, engineer)

    grants = (
        await db_client.get(f"{API}/admin/memberships/{membership.membership_id}/access-grants")
    ).json()["items"]
    await db_client.patch(f"{API}/admin/access-grants/{grants[0]['grant_id']}/grant", json={})

    rows = (await db_client.get(f"{API}/admin/users?page=1&page_size=20")).json()["items"]
    row = next(r for r in rows if r["user_id"] == engineer.user_id)
    assert row["pending_access_count"] == 3


@pytest.mark.asyncio
async def test_membership_ngung_khong_tinh_vao_so_dang_cho(db_client, db_session):
    """Quyền của membership đã ngừng thuộc checklist thu hồi, không phải việc cần cấp."""
    admin = await seed_admin(db_session)
    engineer = await seed_engineer(db_session)
    membership = await seed_membership_with_grants(db_session, admin, engineer)

    await db_client.patch(
        f"{API}/admin/memberships/{membership.membership_id}", json={"status": "INACTIVE"}
    )

    rows = (await db_client.get(f"{API}/admin/users?page=1&page_size=20")).json()["items"]
    row = next(r for r in rows if r["user_id"] == engineer.user_id)
    assert row["pending_access_count"] == 0


@pytest.mark.asyncio
async def test_loc_theo_trang_thai_mat_khau(db_client, db_session):
    admin = await seed_admin(db_session)
    engineer = await seed_engineer(db_session)  # must_change_password = False
    await db_client.patch(
        f"{API}/admin/users/{engineer.user_id}/password", json={"new_password": "mat-khau-moi-123"}
    )

    pending = (
        await db_client.get(f"{API}/admin/users?page=1&page_size=20&password_state=PENDING")
    ).json()["items"]
    assert {row["user_id"] for row in pending} == {engineer.user_id}

    already_set = (
        await db_client.get(f"{API}/admin/users?page=1&page_size=20&password_state=SET")
    ).json()["items"]
    assert {row["user_id"] for row in already_set} == {admin.user_id}


@pytest.mark.asyncio
async def test_loc_mat_khau_gia_tri_la_bi_tu_choi(db_client, db_session):
    await seed_admin(db_session)
    response = await db_client.get(f"{API}/admin/users?page=1&page_size=20&password_state=XYZ")
    assert response.status_code == 422
