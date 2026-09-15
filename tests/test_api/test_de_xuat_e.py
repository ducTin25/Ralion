"""Kiểm thử đề xuất E: buộc đổi mật khẩu, cảnh báo chính sách quá hạn, start_date, import CSV."""

from datetime import date, timedelta

import pytest

from src.api.dependencies import get_current_user, get_current_user_id
from src.main import app
from src.model.document_version import DocumentVersion
from src.model.enums import (
    DocumentDomain,
    DocumentStatus,
    PolicyCategory,
    UserRole,
    UserStatus,
    VersionStatus,
)
from src.model.knowledge_document import KnowledgeDocument
from src.model.user import User
from src.services.auth_service import hash_password

API = "/api/v1/console"


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    for dependency in (get_current_user, get_current_user_id):
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


# ------------------------------------------------- E2: buộc đổi mật khẩu lần đầu


@pytest.mark.asyncio
async def test_tai_khoan_moi_bi_bat_doi_mat_khau(db_client, db_session):
    await seed_admin(db_session)
    response = await db_client.post(
        f"{API}/admin/users",
        json={
            "display_name": "Nguyễn An",
            "email": "an@onboarding.dev",
            "temporary_password": "mat-khau-tam",
        },
    )
    assert response.status_code == 201
    assert response.json()["must_change_password"] is True


@pytest.mark.asyncio
async def test_dang_nhap_tra_outcome_must_change_password(db_client, db_session):
    await seed_admin(db_session)
    await db_client.post(
        f"{API}/admin/users",
        json={
            "display_name": "Trần Bình",
            "email": "binh@onboarding.dev",
            "temporary_password": "mat-khau-tam",
        },
    )
    # Chỉ gỡ override danh tính. `clear()` sẽ gỡ luôn get_db và request rơi xuống
    # PostgreSQL thật.
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_user_id, None)

    login = await db_client.post(
        "/api/v1/auth/login", json={"email": "binh@onboarding.dev", "password": "mat-khau-tam"}
    )
    assert login.status_code == 200
    body = login.json()
    assert body["outcome"] == "MUST_CHANGE_PASSWORD"
    assert body["redirect_to"] == "/change-password"


@pytest.mark.asyncio
async def test_endpoint_nghiep_vu_bi_chan_khi_con_no_doi_mat_khau(db_client, db_session):
    admin = await seed_admin(db_session)
    admin.must_change_password = True
    await db_session.commit()

    response = await db_client.get(f"{API}/admin/overview")
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PASSWORD_CHANGE_REQUIRED"


@pytest.mark.asyncio
async def test_van_doi_duoc_mat_khau_khi_con_no(db_client, db_session):
    """Ca quan trọng nhất của E2.

    Nếu chặn ở `get_current_user` thay vì dependency riêng, endpoint này cũng bị 403 và
    người dùng kẹt vĩnh viễn: phải đổi mật khẩu mới vào được, mà không vào được để đổi.
    """
    admin = await seed_admin(db_session)
    admin.must_change_password = True
    await db_session.commit()

    response = await db_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "admin-password", "new_password": "mat-khau-moi-123"},
    )
    assert response.status_code == 200
    await db_session.refresh(admin)
    assert admin.must_change_password is False


@pytest.mark.asyncio
async def test_admin_reset_mat_khau_bat_lai_co(db_client, db_session):
    admin = await seed_admin(db_session)
    target = User(
        email="chi@onboarding.dev",
        display_name="Lê Chi",
        password_hash=hash_password("mat-khau-cu"),
        status=UserStatus.ACTIVE,
        must_change_password=False,
    )
    db_session.add(target)
    await db_session.commit()
    await db_session.refresh(target)
    assert admin.system_role == UserRole.ADMIN

    response = await db_client.patch(
        f"{API}/admin/users/{target.user_id}/password", json={"new_password": "mat-khau-moi-123"}
    )
    assert response.status_code == 200
    assert response.json()["must_change_password"] is True


# ------------------------------------------- E3: cảnh báo chính sách quá hạn


async def seed_policy(
    db_session,
    author: User,
    *,
    title: str,
    source_key: str,
    effective_date: date | None,
    document_status: DocumentStatus = DocumentStatus.ACTIVE,
) -> KnowledgeDocument:
    document = KnowledgeDocument(
        knowledge_domain=DocumentDomain.POLICY,
        project_id=None,
        policy_category=PolicyCategory.HR_POLICY,
        source_key=source_key,
        title=title,
        source_url="https://storage.example/p.pdf",
        status=document_status,
        created_by_user_id=author.user_id,
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    db_session.add(
        DocumentVersion(
            document_id=document.document_id,
            version_no="1.0",
            revision_no=1,
            embedding_model_version="fake-deterministic-v1",
            storage_uri="policies/p.pdf",
            checksum=f"checksum-{source_key}",
            effective_date=effective_date,
            status=VersionStatus.ACTIVE,
        )
    )
    await db_session.commit()
    return document


@pytest.mark.asyncio
async def test_chinh_sach_qua_han_sinh_canh_bao(db_client, db_session):
    admin = await seed_admin(db_session)
    await seed_policy(
        db_session,
        admin,
        title="Quy định nghỉ phép",
        source_key="HR_LEAVE",
        effective_date=date.today() - timedelta(days=400),
    )

    items = (await db_client.get(f"{API}/admin/risk-items")).json()["items"]
    stale = [item for item in items if item["kind"] == "STALE_POLICY"]
    assert len(stale) == 1
    assert stale[0]["title"] == "Quy định nghỉ phép"


@pytest.mark.asyncio
async def test_chinh_sach_con_moi_khong_sinh_canh_bao(db_client, db_session):
    admin = await seed_admin(db_session)
    await seed_policy(
        db_session,
        admin,
        title="Quy định mới",
        source_key="HR_NEW",
        effective_date=date.today() - timedelta(days=180),
    )

    items = (await db_client.get(f"{API}/admin/risk-items")).json()["items"]
    assert [item for item in items if item["kind"] == "STALE_POLICY"] == []


@pytest.mark.asyncio
async def test_chinh_sach_thieu_ngay_hieu_luc_sinh_canh_bao(db_client, db_session):
    admin = await seed_admin(db_session)
    document = await seed_policy(
        db_session, admin, title="Không ngày", source_key="HR_NODATE", effective_date=None
    )

    items = (await db_client.get(f"{API}/admin/risk-items")).json()["items"]
    missing = [item for item in items if item["kind"] == "POLICY_MISSING_EFFECTIVE_DATE"]
    assert len(missing) == 1
    assert missing[0]["document_id"] == document.document_id


@pytest.mark.asyncio
async def test_chinh_sach_da_luu_tru_khong_sinh_canh_bao(db_client, db_session):
    admin = await seed_admin(db_session)
    await seed_policy(
        db_session,
        admin,
        title="Đã bỏ",
        source_key="HR_OLD",
        effective_date=date.today() - timedelta(days=800),
        document_status=DocumentStatus.ARCHIVED,
    )

    items = (await db_client.get(f"{API}/admin/risk-items")).json()["items"]
    assert [item for item in items if item["kind"] == "STALE_POLICY"] == []


@pytest.mark.asyncio
async def test_risk_count_tren_tong_quan_khop_voi_danh_sach(db_client, db_session):
    """overview() gọi _build_risk_items riêng — quên truyền policies là hai số lệch nhau."""
    admin = await seed_admin(db_session)
    await seed_policy(
        db_session,
        admin,
        title="Quá hạn",
        source_key="HR_STALE",
        effective_date=date.today() - timedelta(days=500),
    )

    overview = (await db_client.get(f"{API}/admin/overview")).json()
    risks = (await db_client.get(f"{API}/admin/risk-items")).json()
    assert overview["risk_count"] == risks["total"]


# ---------------------------------------------------- E1: start_date


@pytest.mark.asyncio
async def test_loc_nhan_su_sap_vao_du_an(db_client, db_session):
    await seed_admin(db_session)
    await db_client.post(
        f"{API}/admin/users",
        json={
            "display_name": "Sắp Vào",
            "email": "sapvao@onboarding.dev",
            "temporary_password": "mat-khau-tam",
            "start_date": str(date.today() + timedelta(days=7)),
        },
    )
    await db_client.post(
        f"{API}/admin/users",
        json={
            "display_name": "Đang Làm",
            "email": "danglam@onboarding.dev",
            "temporary_password": "mat-khau-tam",
            "start_date": str(date.today() - timedelta(days=30)),
        },
    )

    upcoming = (await db_client.get(f"{API}/admin/users?start_status=UPCOMING")).json()
    started = (await db_client.get(f"{API}/admin/users?start_status=STARTED")).json()

    assert [row["email"] for row in upcoming["items"]] == ["sapvao@onboarding.dev"]
    assert "danglam@onboarding.dev" in [row["email"] for row in started["items"]]


@pytest.mark.asyncio
async def test_khong_co_ngay_vao_lam_coi_nhu_da_bat_dau(db_client, db_session):
    """Tài khoản cũ không có start_date. Xếp vào 'sắp vào' sẽ tạo danh sách chờ toàn
    người đang làm việc."""
    admin = await seed_admin(db_session)
    upcoming = (await db_client.get(f"{API}/admin/users?start_status=UPCOMING")).json()
    started = (await db_client.get(f"{API}/admin/users?start_status=STARTED")).json()

    assert admin.email not in [row["email"] for row in upcoming["items"]]
    assert admin.email in [row["email"] for row in started["items"]]


@pytest.mark.asyncio
async def test_ngay_vao_lam_hom_nay_thuoc_nhom_da_bat_dau(db_client, db_session):
    await seed_admin(db_session)
    await db_client.post(
        f"{API}/admin/users",
        json={
            "display_name": "Hôm Nay",
            "email": "homnay@onboarding.dev",
            "temporary_password": "mat-khau-tam",
            "start_date": str(date.today()),
        },
    )

    upcoming = (await db_client.get(f"{API}/admin/users?start_status=UPCOMING")).json()
    assert [row["email"] for row in upcoming["items"]] == []


# ---------------------------------------------------- E4: import CSV

PREVIEW = f"{API}/admin/users/import/preview"
IMPORT = f"{API}/admin/users/import"


def csv_file(text: str):
    return {"file": ("nhan-su.csv", text.encode("utf-8"), "text/csv")}


@pytest.mark.asyncio
async def test_import_csv_tao_du_tai_khoan(db_client, db_session):
    await seed_admin(db_session)
    content = (
        "display_name,email,system_role,start_date\n"
        "Nguyễn An,an@onboarding.dev,,01/09/2026\n"
        "Trần Bình,binh@onboarding.dev,,\n"
        "Lê Chi,chi@onboarding.dev,HR,\n"
    )
    response = await db_client.post(IMPORT, files=csv_file(content))

    assert response.status_code == 201
    body = response.json()
    assert len(body["created"]) == 3
    assert body["skipped"] == []
    # Mật khẩu tạm phải khác nhau cho từng người.
    passwords = {row["temporary_password"] for row in body["created"]}
    assert len(passwords) == 3


@pytest.mark.asyncio
async def test_dong_hong_bi_bo_qua_dong_tot_van_tao(db_client, db_session):
    await seed_admin(db_session)
    content = (
        "display_name,email\n"
        "Nguyễn An,an@onboarding.dev\n"
        "Thiếu Email,\n"
        "Trần Bình,binh@onboarding.dev\n"
    )
    body = (await db_client.post(IMPORT, files=csv_file(content))).json()

    assert len(body["created"]) == 2
    assert len(body["skipped"]) == 1
    assert body["skipped"][0]["error"] == "Thiếu tên hoặc email"
    assert body["skipped"][0]["line"] == 3


@pytest.mark.asyncio
async def test_email_trung_trong_file_chi_tao_mot(db_client, db_session):
    await seed_admin(db_session)
    content = (
        "display_name,email\n"
        "Nguyễn An,an@onboarding.dev\n"
        "An Nguyễn,an@onboarding.dev\n"
    )
    body = (await db_client.post(IMPORT, files=csv_file(content))).json()

    assert len(body["created"]) == 1
    assert body["skipped"][0]["error"] == "Email trùng trong file"


@pytest.mark.asyncio
async def test_email_da_ton_tai_bi_bo_qua(db_client, db_session):
    admin = await seed_admin(db_session)
    content = f"display_name,email\nTrùng,{admin.email}\n"
    body = (await db_client.post(IMPORT, files=csv_file(content))).json()

    assert body["created"] == []
    assert body["skipped"][0]["error"] == "Email đã tồn tại trong hệ thống"


@pytest.mark.asyncio
async def test_xem_truoc_khong_ghi_gi_vao_database(db_client, db_session):
    from sqlalchemy import func, select

    await seed_admin(db_session)
    before = await db_session.scalar(select(func.count(User.user_id)))

    content = "display_name,email\nNguyễn An,an@onboarding.dev\n"
    preview = (await db_client.post(PREVIEW, files=csv_file(content))).json()

    after = await db_session.scalar(select(func.count(User.user_id)))
    assert preview["valid_count"] == 1
    assert preview["invalid_count"] == 0
    assert before == after


@pytest.mark.asyncio
async def test_thieu_cot_bat_buoc_tra_422(db_client, db_session):
    await seed_admin(db_session)
    response = await db_client.post(PREVIEW, files=csv_file("ten,mail\nA,a@b.com\n"))

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "MISSING_COLUMNS"


@pytest.mark.asyncio
async def test_import_bat_doi_mat_khau_lan_dau(db_client, db_session):
    """Mật khẩu do hệ thống sinh, người dùng chưa biết -> phải đổi ngay lần đầu."""
    from sqlalchemy import select

    await seed_admin(db_session)
    await db_client.post(IMPORT, files=csv_file("display_name,email\nAn,an@onboarding.dev\n"))

    created = await db_session.scalar(select(User).where(User.email == "an@onboarding.dev"))
    assert created.must_change_password is True
