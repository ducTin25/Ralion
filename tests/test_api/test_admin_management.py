"""Kiểm thử nghiệp vụ quản trị tài khoản, dự án, membership và chính sách HR.

Chạy trên SQLite in-memory (fixture `db_client`) nên không cần dựng PostgreSQL.
Mỗi test tự tạo dữ liệu mẫu để không phụ thuộc thứ tự chạy.
"""

import pytest
from sqlalchemy import select

from src.api.dependencies import get_current_user, get_current_user_id
from src.main import app
from src.model.enums import (
    MembershipStatus,
    ProjectRole,
    ProjectStatus,
    TemplateScope,
    TemplateStatus,
    TemplateVersionStatus,
    UserRole,
    UserStatus,
)
from src.model.onboarding_template import OnboardingTemplate
from src.model.project import Project
from src.model.project_membership import ProjectMembership
from src.model.template_version import TemplateVersion
from src.model.user import User
from src.services.auth_service import hash_password

API = "/api/v1/console"


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_user_id, None)


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


async def seed_user(db_session, name: str, **kwargs) -> User:
    user = User(
        email=f"{name}@onboarding.dev",
        display_name=name.title(),
        password_hash=hash_password("member-password"),
        status=kwargs.pop("status", UserStatus.ACTIVE),
        system_role=kwargs.pop("system_role", None),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def seed_global_template(db_session) -> OnboardingTemplate:
    """Global Master Template đã APPROVED — điều kiện bắt buộc để tạo project mới (SoT §11.16),
    cả 2 luồng PM (`project_service.create_project`) lẫn Admin
    (`admin_console_service.create_project`)."""
    template = OnboardingTemplate(
        scope=TemplateScope.GLOBAL,
        name="Standard Engineer Onboarding",
        description="Global master template dùng cho test.",
        status=TemplateStatus.APPROVED,
    )
    db_session.add(template)
    await db_session.flush()
    version = TemplateVersion(
        template_id=template.template_id,
        version_no=1,
        status=TemplateVersionStatus.APPROVED,
    )
    db_session.add(version)
    await db_session.commit()
    await db_session.refresh(template)
    return template


async def seed_project(db_session, admin: User, key="ALP", name="Alpha", **kwargs) -> Project:
    project = Project(
        key=key,
        name=name,
        github_repo=f"example/{key.lower()}",
        default_branch="main",
        created_by_admin_id=admin.user_id,
        status=kwargs.pop("status", ProjectStatus.ACTIVE),
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


# ------------------------------------------------------------------ tài khoản


@pytest.mark.asyncio
async def test_tao_user_trung_email_tra_409(db_client, db_session):
    await seed_admin(db_session)
    body = {
        "display_name": "Nguyễn An",
        "email": "an@onboarding.dev",
        "temporary_password": "mat-khau-tam",
    }
    first = await db_client.post(f"{API}/admin/users", json=body)
    second = await db_client.post(f"{API}/admin/users", json=body)
    assert first.status_code == 201
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_khoa_tai_khoan_roi_khong_dang_nhap_duoc(db_client, db_session):
    admin = await seed_admin(db_session)
    user = await seed_user(db_session, "binh")

    locked = await db_client.patch(f"{API}/admin/users/{user.user_id}/status", json={"status": "INACTIVE"})
    assert locked.status_code == 200
    assert locked.json()["status"] == "INACTIVE"

    login = await db_client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "member-password"}
    )
    assert login.status_code == 403
    assert login.json()["detail"]["code"] == "ACCOUNT_INACTIVE"
    assert admin.system_role == UserRole.ADMIN  # admin không bị ảnh hưởng


@pytest.mark.asyncio
async def test_khong_cap_quyen_he_thong_cho_nguoi_dang_trong_du_an(db_client, db_session):
    """Ngăn tài khoản vừa là ADMIN/HR vừa là thành viên dự án — trạng thái mâu thuẫn."""
    admin = await seed_admin(db_session)
    user = await seed_user(db_session, "chi")
    project = await seed_project(db_session, admin)
    db_session.add(
        ProjectMembership(
            user_id=user.user_id,
            project_id=project.project_id,
            project_role=ProjectRole.ENGINEER,
            status=MembershipStatus.ACTIVE,
            assigned_by_admin_id=admin.user_id,
        )
    )
    await db_session.commit()

    response = await db_client.patch(f"{API}/admin/users/{user.user_id}", json={"system_role": "HR"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_reset_mat_khau_cho_phep_dang_nhap_bang_mat_khau_moi(db_client, db_session):
    await seed_admin(db_session)
    user = await seed_user(db_session, "dung")

    reset = await db_client.patch(
        f"{API}/admin/users/{user.user_id}/password", json={"new_password": "mat-khau-moi-123"}
    )
    assert reset.status_code == 200

    old = await db_client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "member-password"}
    )
    new = await db_client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "mat-khau-moi-123"}
    )
    assert old.status_code == 401
    assert new.status_code == 200


# ---------------------------------------------------------------- membership


@pytest.mark.asyncio
async def test_khong_gan_membership_cho_tai_khoan_co_quyen_he_thong(db_client, db_session):
    admin = await seed_admin(db_session)
    hr = await seed_user(db_session, "hr-user", system_role=UserRole.HR)
    project = await seed_project(db_session, admin)

    response = await db_client.post(
        f"{API}/admin/memberships",
        json={
            "user_id": hr.user_id,
            "project_id": project.project_id,
            "project_role": "ENGINEER",
            "status": "ACTIVE",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_khong_gan_membership_vao_du_an_da_luu_tru(db_client, db_session):
    admin = await seed_admin(db_session)
    user = await seed_user(db_session, "en")
    project = await seed_project(db_session, admin, key="BET", name="Beta", status=ProjectStatus.ARCHIVED)

    response = await db_client.post(
        f"{API}/admin/memberships",
        json={
            "user_id": user.user_id,
            "project_id": project.project_id,
            "project_role": "ENGINEER",
            "status": "ACTIVE",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_pm_dau_tien_tu_dong_thanh_pm_chinh(db_client, db_session):
    admin = await seed_admin(db_session)
    user = await seed_user(db_session, "phuc")
    project = await seed_project(db_session, admin)

    created = await db_client.post(
        f"{API}/admin/memberships",
        json={
            "user_id": user.user_id,
            "project_id": project.project_id,
            "project_role": "PM",
            "status": "ACTIVE",
        },
    )
    assert created.status_code == 201

    detail = await db_client.get(f"{API}/admin/projects/{project.project_id}")
    body = detail.json()
    assert body["primary_pm_name"] == user.display_name
    assert body["active_pm_count"] == 1


@pytest.mark.asyncio
async def test_gan_hang_loat_bo_qua_nguoi_khong_du_dieu_kien(db_client, db_session):
    """Một tài khoản khoá không được phép chặn những người còn lại."""
    admin = await seed_admin(db_session)
    ok_one = await seed_user(db_session, "giang")
    ok_two = await seed_user(db_session, "hoa")
    locked = await seed_user(db_session, "khoa", status=UserStatus.INACTIVE)
    hr = await seed_user(db_session, "nhan-su", system_role=UserRole.HR)
    project = await seed_project(db_session, admin)

    response = await db_client.post(
        f"{API}/admin/memberships/bulk",
        json={
            "project_id": project.project_id,
            "project_role": "ENGINEER",
            "user_ids": [ok_one.user_id, locked.user_id, hr.user_id, ok_two.user_id, 9999],
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert {row["user_name"] for row in body["created"]} == {ok_one.display_name, ok_two.display_name}
    reasons = {row["user_id"]: row["reason"] for row in body["skipped"]}
    assert reasons[locked.user_id] == "Tài khoản đã khóa"
    assert reasons[hr.user_id] == "Tài khoản có quyền hệ thống"
    assert reasons[9999] == "Không tìm thấy tài khoản"


# -------------------------------------------------------------------- dự án


@pytest.mark.asyncio
async def test_luu_tru_du_an_kem_ngung_membership(db_client, db_session):
    """Lưu trữ dự án mà để nguyên membership chính là nguồn sinh mục 'cần xử lý'."""
    admin = await seed_admin(db_session)
    user = await seed_user(db_session, "lan")
    project = await seed_project(db_session, admin)
    db_session.add(
        ProjectMembership(
            user_id=user.user_id,
            project_id=project.project_id,
            project_role=ProjectRole.PM,
            status=MembershipStatus.ACTIVE,
            assigned_by_admin_id=admin.user_id,
        )
    )
    await db_session.commit()

    response = await db_client.patch(
        f"{API}/admin/projects/{project.project_id}/status",
        json={"status": "ARCHIVED", "deactivate_memberships": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ARCHIVED"
    assert body["active_member_count"] == 0
    assert body["primary_pm_name"] is None


@pytest.mark.asyncio
async def test_ma_du_an_trung_tra_409(db_client, db_session):
    await seed_admin(db_session)
    await seed_global_template(db_session)
    body = {"name": "Alpha", "key": "ALP"}
    first = await db_client.post(f"{API}/admin/projects", json=body)
    second = await db_client.post(f"{API}/admin/projects", json={"name": "Alpha 2", "key": "alp"})
    assert first.status_code == 201
    assert second.status_code == 409  # key được viết hoa trước khi so sánh


@pytest.mark.asyncio
async def test_tao_du_an_qua_admin_tu_co_master_template(db_client, db_session):
    """SoT §11.16: project tạo qua Admin Console phải tự có Master Template ngay, fork từ Global
    Master Template — trước đây luồng Admin bỏ sót bước này (chỉ luồng PM /projects/pm làm đúng)."""
    await seed_admin(db_session)
    global_template = await seed_global_template(db_session)
    response = await db_client.post(f"{API}/admin/projects", json={"name": "Beta", "key": "BET"})
    assert response.status_code == 201
    project_id = response.json()["project_id"]

    project_template = await db_session.scalar(
        select(OnboardingTemplate).where(OnboardingTemplate.project_id == project_id)
    )
    assert project_template is not None
    assert project_template.scope == TemplateScope.PROJECT
    assert project_template.source_template_id == global_template.template_id


@pytest.mark.asyncio
async def test_tao_du_an_qua_admin_khi_chua_co_global_template_tra_422(db_client, db_session):
    await seed_admin(db_session)
    response = await db_client.post(f"{API}/admin/projects", json={"name": "Gamma", "key": "GAM"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_xem_global_master_template_qua_admin(db_client, db_session):
    await seed_admin(db_session)
    global_template = await seed_global_template(db_session)
    response = await db_client.get(f"{API}/admin/master-template")
    assert response.status_code == 200
    body = response.json()
    assert body["template_id"] == global_template.template_id
    assert body["scope"] == "GLOBAL"


@pytest.mark.asyncio
async def test_xem_global_master_template_khi_chua_co_tra_404(db_client, db_session):
    await seed_admin(db_session)
    response = await db_client.get(f"{API}/admin/master-template")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_xem_global_master_template_khong_phai_admin_tra_403(db_client, db_session):
    pm = await seed_user(db_session, "pm")
    app.dependency_overrides[get_current_user] = lambda: pm
    app.dependency_overrides[get_current_user_id] = lambda: pm.user_id
    await seed_global_template(db_session)
    response = await db_client.get(f"{API}/admin/master-template")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_tong_quan_phat_hien_du_an_thieu_pm_va_nguoi_chua_gan(db_client, db_session):
    admin = await seed_admin(db_session)
    await seed_user(db_session, "moi")  # active, chưa có membership
    await seed_project(db_session, admin)  # active, chưa có PM

    response = await db_client.get(f"{API}/admin/risk-items")
    assert response.status_code == 200
    kinds = {item["kind"] for item in response.json()["items"]}
    assert "PROJECT_WITHOUT_PM" in kinds
    assert "ACTIVE_USER_NO_MEMBERSHIP" in kinds
