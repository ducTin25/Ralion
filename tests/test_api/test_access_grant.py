"""Kiểm thử đề xuất A (hàng đợi cấp quyền) và đề xuất D (thu hồi khi rời dự án)."""

from datetime import UTC, datetime, timedelta

import pytest

from src.api.dependencies import get_current_user, get_current_user_id, get_session_issued_at
from src.main import app
from src.model.access_grant import AccessGrant
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
from src.services.auth_service import hash_password

API = "/api/v1/console"


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    for dependency in (get_current_user, get_current_user_id, get_session_issued_at):
        app.dependency_overrides.pop(dependency, None)


def sign_in_as(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_user_id] = lambda: user.user_id


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
    sign_in_as(admin)
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


async def seed_engineer(db_session, *, email: str = "an@onboarding.dev") -> User:
    engineer = User(
        email=email,
        display_name="Nguyễn An",
        password_hash=hash_password("mat-khau-cua-an"),
        system_role=None,
        status=UserStatus.ACTIVE,
    )
    db_session.add(engineer)
    await db_session.commit()
    await db_session.refresh(engineer)
    return engineer


# --------------------------------------------------- A: tự sinh bộ quyền chuẩn


@pytest.mark.asyncio
async def test_gan_du_an_tu_sinh_bo_quyen_chuan(db_client, db_session):
    """Ca quan trọng nhất của đề xuất A.

    Người mới ngày đầu chưa biết mình cần quyền gì để mà xin — đó chính là vấn đề. Gán
    vào dự án phải sinh sẵn hàng đợi, không đợi ai bấm.
    """
    admin = await seed_admin(db_session)
    project = await seed_project(db_session, admin)
    engineer = await seed_engineer(db_session)

    response = await db_client.post(
        f"{API}/admin/memberships",
        json={
            "user_id": engineer.user_id,
            "project_id": project.project_id,
            "project_role": "ENGINEER",
        },
    )
    assert response.status_code == 201
    membership_id = response.json()["membership_id"]

    grants = (await db_client.get(f"{API}/admin/memberships/{membership_id}/access-grants")).json()
    assert {row["resource_type"] for row in grants["items"]} == {
        "REPOSITORY",
        "ISSUE_TRACKER",
        "CI_CD",
        "DATABASE",
    }
    assert all(row["status"] == "REQUESTED" for row in grants["items"])


@pytest.mark.asyncio
async def test_pm_duoc_them_quyen_secrets(db_client, db_session):
    admin = await seed_admin(db_session)
    project = await seed_project(db_session, admin)
    pm = await seed_engineer(db_session, email="pm@onboarding.dev")

    response = await db_client.post(
        f"{API}/admin/memberships",
        json={"user_id": pm.user_id, "project_id": project.project_id, "project_role": "PM"},
    )
    membership_id = response.json()["membership_id"]

    grants = (await db_client.get(f"{API}/admin/memberships/{membership_id}/access-grants")).json()
    assert "SECRETS" in {row["resource_type"] for row in grants["items"]}


@pytest.mark.asyncio
async def test_membership_inactive_khong_sinh_quyen(db_client, db_session):
    """Tạo membership ở trạng thái INACTIVE nghĩa là người đó chưa thực sự vào dự án."""
    admin = await seed_admin(db_session)
    project = await seed_project(db_session, admin)
    engineer = await seed_engineer(db_session)

    response = await db_client.post(
        f"{API}/admin/memberships",
        json={
            "user_id": engineer.user_id,
            "project_id": project.project_id,
            "project_role": "ENGINEER",
            "status": "INACTIVE",
        },
    )
    membership_id = response.json()["membership_id"]
    grants = (await db_client.get(f"{API}/admin/memberships/{membership_id}/access-grants")).json()
    assert grants["items"] == []


@pytest.mark.asyncio
async def test_nang_engineer_len_pm_sinh_them_quyen_khong_trung(db_client, db_session):
    """Gọi seed lần hai không được nhân đôi bộ quyền đã có."""
    admin = await seed_admin(db_session)
    project = await seed_project(db_session, admin)
    engineer = await seed_engineer(db_session)

    created = await db_client.post(
        f"{API}/admin/memberships",
        json={
            "user_id": engineer.user_id,
            "project_id": project.project_id,
            "project_role": "ENGINEER",
        },
    )
    membership_id = created.json()["membership_id"]

    await db_client.patch(
        f"{API}/admin/memberships/{membership_id}", json={"project_role": "PM"}
    )

    grants = (await db_client.get(f"{API}/admin/memberships/{membership_id}/access-grants")).json()
    resource_types = [row["resource_type"] for row in grants["items"]]
    assert len(resource_types) == len(set(resource_types)), "Sinh trùng khi gọi lại seed"
    assert "SECRETS" in resource_types


# ------------------------------------------------------------ A: cấp và thu hồi


async def seed_membership_with_grants(db_session, admin: User) -> tuple[ProjectMembership, list[AccessGrant]]:
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
    grants = await access_grant_service.seed_grants_for_membership(db_session, membership)
    await db_session.commit()
    return membership, grants


@pytest.mark.asyncio
async def test_cap_quyen_ghi_nguoi_cap_va_thoi_diem(db_client, db_session):
    admin = await seed_admin(db_session)
    _, grants = await seed_membership_with_grants(db_session, admin)

    response = await db_client.patch(
        f"{API}/admin/access-grants/{grants[0].grant_id}/grant",
        json={"resource_note": "github.com/cty/bo-06"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "GRANTED"
    assert body["granted_at"] is not None
    assert body["granted_by_name"] == "Admin Root"
    assert body["resource_note"] == "github.com/cty/bo-06"


@pytest.mark.asyncio
async def test_cap_quyen_hai_lan_khong_doi_thoi_diem_cap(db_client, db_session):
    """Idempotent: bấm nhầm lần hai không được ghi đè thời điểm cấp lần đầu."""
    admin = await seed_admin(db_session)
    _, grants = await seed_membership_with_grants(db_session, admin)
    grant_id = grants[0].grant_id

    first = (await db_client.patch(f"{API}/admin/access-grants/{grant_id}/grant", json={})).json()
    second = (await db_client.patch(f"{API}/admin/access-grants/{grant_id}/grant", json={})).json()
    assert first["granted_at"] == second["granted_at"]


@pytest.mark.asyncio
async def test_khong_cap_lai_duoc_quyen_da_thu_hoi(db_client, db_session):
    admin = await seed_admin(db_session)
    _, grants = await seed_membership_with_grants(db_session, admin)
    grant_id = grants[0].grant_id

    await db_client.patch(f"{API}/admin/access-grants/{grant_id}/revoke")
    response = await db_client.patch(f"{API}/admin/access-grants/{grant_id}/grant", json={})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "GRANT_REVOKED"


@pytest.mark.asyncio
async def test_thu_hoi_giu_lai_ban_ghi_lam_bang_chung(db_client, db_session):
    """Thu hồi không xoá dòng — `revoked_at` chính là thứ kiểm toán hỏi tới."""
    admin = await seed_admin(db_session)
    membership, grants = await seed_membership_with_grants(db_session, admin)

    await db_client.patch(f"{API}/admin/access-grants/{grants[0].grant_id}/revoke")
    rows = (
        await db_client.get(f"{API}/admin/memberships/{membership.membership_id}/access-grants")
    ).json()["items"]
    revoked = [row for row in rows if row["grant_id"] == grants[0].grant_id]
    assert len(revoked) == 1
    assert revoked[0]["status"] == "REVOKED"
    assert revoked[0]["revoked_at"] is not None


@pytest.mark.asyncio
async def test_them_quyen_trung_loai_bi_tu_choi(db_client, db_session):
    admin = await seed_admin(db_session)
    membership, _ = await seed_membership_with_grants(db_session, admin)

    response = await db_client.post(
        f"{API}/admin/access-grants",
        json={
            "membership_id": membership.membership_id,
            "resource_type": "REPOSITORY",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "GRANT_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_cap_lai_duoc_quyen_da_thu_hoi_bang_ban_ghi_moi(db_client, db_session):
    """Thu hồi rồi cấp lại phải được — kể cả ngay lập tức.

    Ràng buộc unique phải là partial (chỉ chặn bản ghi chưa REVOKED). Nếu là unique
    thường trên (membership, resource_type) thì thao tác này vỡ vì IntegrityError, và
    lịch sử thu hồi cũ cũng không giữ được.
    """
    admin = await seed_admin(db_session)
    membership, grants = await seed_membership_with_grants(db_session, admin)
    await db_client.patch(f"{API}/admin/access-grants/{grants[0].grant_id}/revoke")

    response = await db_client.post(
        f"{API}/admin/access-grants",
        json={"membership_id": membership.membership_id, "resource_type": "REPOSITORY"},
    )
    assert response.status_code == 201

    rows = (
        await db_client.get(f"{API}/admin/memberships/{membership.membership_id}/access-grants")
    ).json()["items"]
    repository_rows = [row for row in rows if row["resource_type"] == "REPOSITORY"]
    # Bản ghi cũ vẫn còn làm bằng chứng, bên cạnh yêu cầu mới.
    assert len(repository_rows) == 2
    assert {row["status"] for row in repository_rows} == {"REVOKED", "REQUESTED"}


@pytest.mark.asyncio
async def test_them_quyen_ngoai_bo_chuan(db_client, db_session):
    admin = await seed_admin(db_session)
    membership, _ = await seed_membership_with_grants(db_session, admin)

    response = await db_client.post(
        f"{API}/admin/access-grants",
        json={
            "membership_id": membership.membership_id,
            "resource_type": "VPN",
            "resource_note": "vpn.cty.vn",
        },
    )
    assert response.status_code == 201
    assert response.json()["resource_type"] == "VPN"


# ---------------------------------------------------------------- A: hàng đợi


@pytest.mark.asyncio
async def test_hang_doi_cu_nhat_len_truoc(db_client, db_session):
    """Sắp xếp giảm dần sẽ đẩy người chờ lâu nhất xuống cuối — đúng người cần xử lý trước."""
    admin = await seed_admin(db_session)
    membership, grants = await seed_membership_with_grants(db_session, admin)

    base = datetime.now(UTC).replace(tzinfo=None)
    for offset, grant in enumerate(grants):
        grant.requested_at = base - timedelta(hours=len(grants) - offset)
    await db_session.commit()

    items = (await db_client.get(f"{API}/admin/access-grants")).json()["items"]
    waited = [row["waiting_hours"] for row in items]
    assert waited == sorted(waited, reverse=True), "Người chờ lâu nhất phải nằm đầu"


@pytest.mark.asyncio
async def test_hang_doi_mac_dinh_chi_hien_yeu_cau_chua_xu_ly(db_client, db_session):
    admin = await seed_admin(db_session)
    _, grants = await seed_membership_with_grants(db_session, admin)
    await db_client.patch(f"{API}/admin/access-grants/{grants[0].grant_id}/grant", json={})

    items = (await db_client.get(f"{API}/admin/access-grants")).json()["items"]
    assert grants[0].grant_id not in {row["grant_id"] for row in items}
    assert all(row["status"] == "REQUESTED" for row in items)


@pytest.mark.asyncio
async def test_tom_tat_hang_doi_dem_dung_qua_han(db_client, db_session):
    admin = await seed_admin(db_session)
    _, grants = await seed_membership_with_grants(db_session, admin)

    old = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=30)
    grants[0].requested_at = old
    grants[1].requested_at = old
    await db_session.commit()

    summary = (await db_client.get(f"{API}/admin/access-grants/summary")).json()
    assert summary["pending"] == len(grants)
    assert summary["overdue"] == 2


@pytest.mark.asyncio
async def test_yeu_cau_qua_han_len_bang_canh_bao(db_client, db_session):
    admin = await seed_admin(db_session)
    _, grants = await seed_membership_with_grants(db_session, admin)

    old = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=30)
    for grant in grants:
        grant.requested_at = old
    await db_session.commit()

    items = (await db_client.get(f"{API}/admin/risk-items")).json()["items"]
    overdue = [item for item in items if item["kind"] == "PENDING_ACCESS_OVERDUE"]
    # Gom theo người + dự án: bốn quyền quá hạn của cùng một người là MỘT cảnh báo.
    assert len(overdue) == 1
    assert overdue[0]["severity"] == "HIGH"
    assert "4 quyền" in overdue[0]["message"]


@pytest.mark.asyncio
async def test_so_canh_bao_o_tong_quan_khop_voi_danh_sach(db_client, db_session):
    """Bẫy đã gặp một lần: `overview()` và `risk_items()` nhận dữ liệu khác nhau."""
    admin = await seed_admin(db_session)
    _, grants = await seed_membership_with_grants(db_session, admin)
    for grant in grants:
        grant.requested_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=30)
    await db_session.commit()

    overview = (await db_client.get(f"{API}/admin/overview")).json()
    listing = (await db_client.get(f"{API}/admin/risk-items")).json()
    assert overview["risk_count"] == listing["total"]


# ------------------------------------------------------- A: quyền của chính tôi


@pytest.mark.asyncio
async def test_ky_su_xem_duoc_quyen_cua_minh(db_client, db_session):
    admin = await seed_admin(db_session)
    membership, grants = await seed_membership_with_grants(db_session, admin)
    await db_client.patch(f"{API}/admin/access-grants/{grants[0].grant_id}/grant", json={})

    engineer = await db_session.get(User, membership.user_id)
    sign_in_as(engineer)

    items = (await db_client.get("/api/v1/me/access-grants")).json()["items"]
    assert len(items) == len(grants)
    assert any(row["status"] == "GRANTED" for row in items)
    assert any(row["status"] == "REQUESTED" for row in items)


@pytest.mark.asyncio
async def test_ky_su_khong_thay_quyen_cua_nguoi_khac(db_client, db_session):
    admin = await seed_admin(db_session)
    await seed_membership_with_grants(db_session, admin)

    outsider = await seed_engineer(db_session, email="khach@onboarding.dev")
    sign_in_as(outsider)

    items = (await db_client.get("/api/v1/me/access-grants")).json()["items"]
    assert items == []


@pytest.mark.asyncio
async def test_ky_su_khong_vao_duoc_hang_doi_admin(db_client, db_session):
    admin = await seed_admin(db_session)
    await seed_membership_with_grants(db_session, admin)

    engineer = await seed_engineer(db_session, email="thuong@onboarding.dev")
    sign_in_as(engineer)

    response = await db_client.get(f"{API}/admin/access-grants")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_danh_sach_chua_vao_du_an_khong_liet_ke_admin_hr(db_client, db_session):
    """Danh sách và con số phải dùng cùng một luật, nếu không màn hình tự mâu thuẫn.

    `overview()["unassigned_active_users"]` lọc `system_role IS NULL`. Nếu danh sách
    không lọc, giao diện hiện "2 tài khoản chưa gán" ngay cạnh "độ phủ 100%".

    Ngoài ra `create_membership` từ chối tài khoản có quyền hệ thống, nên nút "Gán
    membership" trên dòng của họ chắc chắn trả 422.
    """
    admin = await seed_admin(db_session)
    hr = User(
        email="hr@onboarding.dev",
        display_name="Le Van HR",
        password_hash=hash_password("mat-khau-hr"),
        system_role=UserRole.HR,
        status=UserStatus.ACTIVE,
    )
    db_session.add(hr)
    await db_session.commit()
    engineer = await seed_engineer(db_session)

    listing = (await db_client.get(f"{API}/admin/unassigned-users?page=1&page_size=20")).json()
    listed_ids = {row["user_id"] for row in listing["items"]}
    assert engineer.user_id in listed_ids
    assert admin.user_id not in listed_ids
    assert hr.user_id not in listed_ids

    overview = (await db_client.get(f"{API}/admin/overview")).json()
    assert overview["unassigned_active_users"] == listing["meta"]["total"]


# ------------------------------------------------- D: checklist và xem trước


@pytest.mark.asyncio
async def test_xem_truoc_khoa_tai_khoan_liet_ke_hau_qua(db_client, db_session):
    admin = await seed_admin(db_session)
    membership, grants = await seed_membership_with_grants(db_session, admin)
    await db_client.patch(f"{API}/admin/access-grants/{grants[0].grant_id}/grant", json={})
    await db_client.patch(f"{API}/admin/access-grants/{grants[1].grant_id}/grant", json={})

    preview = (
        await db_client.get(f"{API}/admin/users/{membership.user_id}/deactivation-preview")
    ).json()
    assert len(preview["memberships"]) == 1
    # Chỉ quyền ĐÃ CẤP mới cần thu hồi; yêu cầu chưa xử lý thì không có gì để gỡ.
    assert len(preview["granted_access"]) == 2
    assert preview["will_revoke_sessions"] is True


@pytest.mark.asyncio
async def test_xem_truoc_khong_thay_doi_du_lieu(db_client, db_session):
    """GET phải thuần đọc — gọi nhiều lần không được đụng vào trạng thái quyền."""
    admin = await seed_admin(db_session)
    membership, grants = await seed_membership_with_grants(db_session, admin)
    await db_client.patch(f"{API}/admin/access-grants/{grants[0].grant_id}/grant", json={})

    for _ in range(3):
        await db_client.get(f"{API}/admin/users/{membership.user_id}/deactivation-preview")

    rows = (
        await db_client.get(f"{API}/admin/memberships/{membership.membership_id}/access-grants")
    ).json()["items"]
    assert sum(row["status"] == "GRANTED" for row in rows) == 1
    assert sum(row["status"] == "REVOKED" for row in rows) == 0


@pytest.mark.asyncio
async def test_ngung_membership_khong_tu_thu_hoi_quyen(db_client, db_session):
    """Quyết định thiết kế then chốt của đề xuất D.

    Hệ thống không gỡ được quyền thật trên GitHub/Jira/VPN. Tự đánh dấu REVOKED sẽ tạo
    ra một danh sách sạch sẽ nói dối rằng mọi thứ đã được gỡ.
    """
    admin = await seed_admin(db_session)
    membership, grants = await seed_membership_with_grants(db_session, admin)
    await db_client.patch(f"{API}/admin/access-grants/{grants[0].grant_id}/grant", json={})

    await db_client.patch(
        f"{API}/admin/memberships/{membership.membership_id}", json={"status": "INACTIVE"}
    )

    rows = (
        await db_client.get(f"{API}/admin/memberships/{membership.membership_id}/access-grants")
    ).json()["items"]
    assert any(row["status"] == "GRANTED" for row in rows), "Quyền bị thu hồi tự động"


@pytest.mark.asyncio
async def test_tick_toan_bo_checklist_mot_luot(db_client, db_session):
    admin = await seed_admin(db_session)
    membership, grants = await seed_membership_with_grants(db_session, admin)
    await db_client.patch(f"{API}/admin/access-grants/{grants[0].grant_id}/grant", json={})

    response = await db_client.post(
        f"{API}/admin/memberships/{membership.membership_id}/revoke-access"
    )
    assert response.status_code == 200
    assert all(row["status"] == "REVOKED" for row in response.json()["items"])


@pytest.mark.asyncio
async def test_xem_truoc_ngung_membership_bao_primary_pm(db_client, db_session):
    admin = await seed_admin(db_session)
    project = await seed_project(db_session, admin)
    pm = await seed_engineer(db_session, email="pm2@onboarding.dev")

    created = await db_client.post(
        f"{API}/admin/memberships",
        json={"user_id": pm.user_id, "project_id": project.project_id, "project_role": "PM"},
    )
    membership_id = created.json()["membership_id"]

    preview = (
        await db_client.get(f"{API}/admin/memberships/{membership_id}/offboarding-preview")
    ).json()
    assert preview["is_primary_pm"] is True


# ------------------------------------------------------------ D: thu hồi phiên


@pytest.mark.asyncio
async def test_khoa_tai_khoan_dong_dau_thu_hoi_phien(db_client, db_session):
    admin = await seed_admin(db_session)
    engineer = await seed_engineer(db_session)
    assert engineer.session_invalid_before is None

    await db_client.patch(
        f"{API}/admin/users/{engineer.user_id}/status", json={"status": "INACTIVE"}
    )
    await db_session.refresh(engineer)
    assert engineer.session_invalid_before is not None
    assert admin.system_role == UserRole.ADMIN


@pytest.mark.asyncio
async def test_admin_reset_mat_khau_dong_dau_thu_hoi_phien(db_client, db_session):
    """Lý do phổ biến nhất để reset mật khẩu là nghi tài khoản bị chiếm."""
    await seed_admin(db_session)
    engineer = await seed_engineer(db_session)

    await db_client.patch(
        f"{API}/admin/users/{engineer.user_id}/password", json={"new_password": "mat-khau-moi-123"}
    )
    await db_session.refresh(engineer)
    assert engineer.session_invalid_before is not None


@pytest.mark.asyncio
async def test_tu_doi_mat_khau_dong_dau_thu_hoi_phien(db_client, db_session):
    admin = await seed_admin(db_session)
    response = await db_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "admin-password", "new_password": "mat-khau-moi-123"},
    )
    assert response.status_code == 200
    await db_session.refresh(admin)
    assert admin.session_invalid_before is not None
