"""Kiểm thử phần bổ sung cho tab Dự án: sửa tên/mã, đếm quyền chờ, lọc theo PM."""

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


async def seed_project(
    db_session,
    admin: User,
    *,
    key: str = "BO06",
    name: str = "Dự án BO06",
    status: ProjectStatus = ProjectStatus.ACTIVE,
) -> Project:
    project = Project(
        name=name, key=key, status=status, created_by_admin_id=admin.user_id
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


async def seed_engineer(db_session, *, email: str = "an@onboarding.dev") -> User:
    engineer = User(
        email=email,
        display_name="Nguyễn An",
        password_hash=hash_password("mat-khau"),
        system_role=None,
        status=UserStatus.ACTIVE,
    )
    db_session.add(engineer)
    await db_session.commit()
    await db_session.refresh(engineer)
    return engineer


# ------------------------------------------------------------ sửa tên và mã


@pytest.mark.asyncio
async def test_sua_ten_va_ma_du_an(db_client, db_session):
    admin = await seed_admin(db_session)
    project = await seed_project(db_session, admin)

    response = await db_client.patch(
        f"{API}/admin/projects/{project.project_id}",
        json={"name": "Onboarding Buddy", "key": "BO06X"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Onboarding Buddy"
    assert body["key"] == "BO06X"


@pytest.mark.asyncio
async def test_chi_sua_ten_giu_nguyen_ma(db_client, db_session):
    admin = await seed_admin(db_session)
    project = await seed_project(db_session, admin)

    response = await db_client.patch(
        f"{API}/admin/projects/{project.project_id}", json={"name": "Tên mới"}
    )
    assert response.status_code == 200
    assert response.json()["key"] == "BO06"


@pytest.mark.asyncio
async def test_ma_du_an_trung_bi_tu_choi(db_client, db_session):
    """Kiểm tra trước khi commit, nếu không người dùng nhận 500 từ IntegrityError."""
    admin = await seed_admin(db_session)
    await seed_project(db_session, admin, key="BO06")
    other = await seed_project(db_session, admin, key="BO07", name="Dự án khác")

    response = await db_client.patch(
        f"{API}/admin/projects/{other.project_id}", json={"key": "BO06"}
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "PROJECT_KEY_TAKEN"


@pytest.mark.asyncio
async def test_giu_nguyen_ma_cua_chinh_no_khong_bao_trung(db_client, db_session):
    """Gửi lại đúng key hiện tại không được coi là trùng với chính mình."""
    admin = await seed_admin(db_session)
    project = await seed_project(db_session, admin, key="BO06")

    response = await db_client.patch(
        f"{API}/admin/projects/{project.project_id}", json={"name": "Tên mới", "key": "BO06"}
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_khong_sua_duoc_du_an_da_luu_tru(db_client, db_session):
    admin = await seed_admin(db_session)
    project = await seed_project(db_session, admin, status=ProjectStatus.ARCHIVED)

    response = await db_client.patch(
        f"{API}/admin/projects/{project.project_id}", json={"name": "Tên mới"}
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "PROJECT_ARCHIVED"


@pytest.mark.asyncio
async def test_ma_du_an_sai_dinh_dang_bi_tu_choi(db_client, db_session):
    admin = await seed_admin(db_session)
    project = await seed_project(db_session, admin)

    response = await db_client.patch(
        f"{API}/admin/projects/{project.project_id}", json={"key": "mã có dấu"}
    )
    assert response.status_code == 422


# ------------------------------------------------- đếm quyền chờ theo dự án


@pytest.mark.asyncio
async def test_dem_quyen_cho_cap_theo_du_an(db_client, db_session):
    admin = await seed_admin(db_session)
    project = await seed_project(db_session, admin)
    engineer = await seed_engineer(db_session)

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

    rows = (await db_client.get(f"{API}/admin/projects?page=1&page_size=20")).json()["items"]
    row = next(r for r in rows if r["project_id"] == project.project_id)
    assert row["pending_access_count"] == 4

    detail = (await db_client.get(f"{API}/admin/projects/{project.project_id}")).json()
    assert detail["pending_access_count"] == 4


@pytest.mark.asyncio
async def test_du_an_khong_co_thanh_vien_thi_khong_co_quyen_cho(db_client, db_session):
    admin = await seed_admin(db_session)
    project = await seed_project(db_session, admin)

    rows = (await db_client.get(f"{API}/admin/projects?page=1&page_size=20")).json()["items"]
    row = next(r for r in rows if r["project_id"] == project.project_id)
    assert row["pending_access_count"] == 0


# ------------------------------------------------------------- lọc theo PM


@pytest.mark.asyncio
async def test_loc_du_an_chua_co_pm(db_client, db_session):
    admin = await seed_admin(db_session)
    without_pm = await seed_project(db_session, admin, key="NOPM", name="Chưa có PM")
    with_pm = await seed_project(db_session, admin, key="HASPM", name="Đã có PM")

    pm = await seed_engineer(db_session, email="pm@onboarding.dev")
    db_session.add(
        ProjectMembership(
            user_id=pm.user_id,
            project_id=with_pm.project_id,
            project_role=ProjectRole.PM,
            status=MembershipStatus.ACTIVE,
            assigned_by_admin_id=admin.user_id,
        )
    )
    await db_session.commit()

    missing = (
        await db_client.get(f"{API}/admin/projects?page=1&page_size=20&pm_state=MISSING")
    ).json()["items"]
    assert {row["project_id"] for row in missing} == {without_pm.project_id}

    assigned = (
        await db_client.get(f"{API}/admin/projects?page=1&page_size=20&pm_state=ASSIGNED")
    ).json()["items"]
    assert {row["project_id"] for row in assigned} == {with_pm.project_id}


@pytest.mark.asyncio
async def test_pm_ngung_hoat_dong_thi_du_an_tinh_la_chua_co_pm(db_client, db_session):
    """Bộ lọc phải trả lời giống hệt cột "PM phụ trách" trong bảng.

    Cả hai cùng dùng `resolve_primary_pm`, nên PM đã ngừng membership không được tính.
    """
    admin = await seed_admin(db_session)
    project = await seed_project(db_session, admin, key="EXPM")
    pm = await seed_engineer(db_session, email="pm2@onboarding.dev")
    db_session.add(
        ProjectMembership(
            user_id=pm.user_id,
            project_id=project.project_id,
            project_role=ProjectRole.PM,
            status=MembershipStatus.INACTIVE,
            assigned_by_admin_id=admin.user_id,
        )
    )
    await db_session.commit()

    missing = (
        await db_client.get(f"{API}/admin/projects?page=1&page_size=20&pm_state=MISSING")
    ).json()["items"]
    assert project.project_id in {row["project_id"] for row in missing}


@pytest.mark.asyncio
async def test_gia_tri_loc_pm_la_bi_tu_choi(db_client, db_session):
    await seed_admin(db_session)
    response = await db_client.get(f"{API}/admin/projects?page=1&page_size=20&pm_state=XYZ")
    assert response.status_code == 422
