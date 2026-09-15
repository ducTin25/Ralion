"""Kiểm thử luồng xác nhận đã đọc chính sách.

Hai test đáng chú ý nhất là `test_phien_ban_moi_lam_moi_trang_thai_xac_nhan` và
`test_phan_biet_chinh_sach_moi_va_ban_cap_nhat`: chúng kiểm chính quyết định thiết kế
cốt lõi — bản ghi xác nhận gắn vào `version_id` chứ không phải `document_id`. Nếu sau này
ai đó "tối ưu" bằng cách chuyển sang document_id, hai test này sẽ đỏ.
"""

from datetime import date

import pytest

from src.api.dependencies import get_current_user, get_current_user_id
from src.main import app
from src.model.document_chunk import DocumentChunk
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
from src.model.policy_acknowledgement import PolicyAcknowledgement
from src.model.user import User
from src.services.auth_service import hash_password

CONSOLE = "/api/v1/console/hr/policies"
ME = "/api/v1/me/policies"


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    for dependency in (get_current_user, get_current_user_id):
        app.dependency_overrides.pop(dependency, None)


def sign_in_as(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_user_id] = lambda: user.user_id


async def seed_user(
    db_session,
    name: str,
    *,
    system_role: UserRole | None = None,
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    user = User(
        email=f"{name}@onboarding.dev",
        display_name=name.title(),
        password_hash=hash_password("mat-khau-test"),
        system_role=system_role,
        status=status,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def seed_policy(
    db_session,
    author: User,
    *,
    source_key: str = "HR_LEAVE_POLICY",
    title: str = "Quy định nghỉ phép",
    requires_ack: bool = True,
    document_status: DocumentStatus = DocumentStatus.ACTIVE,
    version_status: VersionStatus = VersionStatus.ACTIVE,
    version_no: str = "1.0",
    revision_no: int = 1,
) -> tuple[KnowledgeDocument, DocumentVersion]:
    document = KnowledgeDocument(
        knowledge_domain=DocumentDomain.POLICY,
        project_id=None,
        policy_category=PolicyCategory.HR_POLICY,
        source_key=source_key,
        title=title,
        source_url="https://storage.example/policy.pdf",
        status=document_status,
        created_by_user_id=author.user_id,
        requires_acknowledgement=requires_ack,
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    version = DocumentVersion(
        document_id=document.document_id,
        version_no=version_no,
        revision_no=revision_no,
        embedding_model_version="fake-deterministic-v1",
        storage_uri="policies/policy.pdf",
        checksum=f"checksum-{revision_no}",
        effective_date=date(2026, 1, 1),
        status=version_status,
    )
    db_session.add(version)
    await db_session.commit()
    await db_session.refresh(version)
    return document, version


async def add_version(
    db_session, document: KnowledgeDocument, *, version_no: str, revision_no: int
) -> DocumentVersion:
    """Thêm phiên bản mới và hạ phiên bản cũ xuống ARCHIVED, giống luồng ingest của TV3."""
    from sqlalchemy import select

    old = list(
        (
            await db_session.execute(
                select(DocumentVersion).where(
                    DocumentVersion.document_id == document.document_id,
                    DocumentVersion.status == VersionStatus.ACTIVE,
                )
            )
        ).scalars()
    )
    for version in old:
        version.status = VersionStatus.ARCHIVED

    fresh = DocumentVersion(
        document_id=document.document_id,
        version_no=version_no,
        revision_no=revision_no,
        embedding_model_version="fake-deterministic-v1",
        storage_uri="policies/policy-v2.pdf",
        checksum=f"checksum-{revision_no}",
        effective_date=date(2026, 6, 1),
        status=VersionStatus.ACTIVE,
    )
    db_session.add(fresh)
    await db_session.commit()
    await db_session.refresh(fresh)
    return fresh


async def add_chunk(db_session, version: DocumentVersion, content: str) -> None:
    db_session.add(
        DocumentChunk(
            version_id=version.version_id,
            heading="Nội dung",
            content=content,
            embedding_text=content,
            lexical_identifiers="",
            lexical_technical=content,
            section_path="Nội dung",
            content_hash=f"hash-{version.version_id}",
            embedding_model_version=version.embedding_model_version,
            chunk_index=0,
            token_count=len(content.split()),
            embedding=None,
        )
    )
    await db_session.commit()


# ------------------------------------------------------------------ luồng chính


@pytest.mark.asyncio
async def test_xac_nhan_thanh_cong_ghi_dung_phien_ban(db_client, db_session):
    hr = await seed_user(db_session, "hr", system_role=UserRole.HR)
    engineer = await seed_user(db_session, "an")
    document, version = await seed_policy(db_session, hr)

    sign_in_as(engineer)
    response = await db_client.post(f"{ME}/{document.document_id}/acknowledge")

    assert response.status_code == 201
    body = response.json()
    assert body["version_id"] == version.version_id
    assert body["already_acknowledged"] is False


@pytest.mark.asyncio
async def test_xac_nhan_hai_lan_khong_tao_ban_ghi_thu_hai(db_client, db_session):
    from sqlalchemy import func, select

    hr = await seed_user(db_session, "hr", system_role=UserRole.HR)
    engineer = await seed_user(db_session, "binh")
    document, version = await seed_policy(db_session, hr)

    sign_in_as(engineer)
    first = await db_client.post(f"{ME}/{document.document_id}/acknowledge")
    second = await db_client.post(f"{ME}/{document.document_id}/acknowledge")

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["already_acknowledged"] is True

    count = await db_session.scalar(
        select(func.count(PolicyAcknowledgement.ack_id)).where(
            PolicyAcknowledgement.version_id == version.version_id
        )
    )
    assert count == 1


@pytest.mark.asyncio
async def test_phien_ban_moi_lam_moi_trang_thai_xac_nhan(db_client, db_session):
    """Lý do tồn tại của thiết kế gắn ack vào version_id.

    Nếu gắn vào document_id, sau khi HR tải bản mới thì hệ thống vẫn báo "đã đọc" cho
    một nội dung người dùng chưa từng nhìn thấy.
    """
    hr = await seed_user(db_session, "hr", system_role=UserRole.HR)
    engineer = await seed_user(db_session, "chi")
    document, _ = await seed_policy(db_session, hr)

    sign_in_as(engineer)
    await db_client.post(f"{ME}/{document.document_id}/acknowledge")
    assert await db_client.get(ME) is not None
    assert (await db_client.get(ME)).json()["items"] == []

    await add_version(db_session, document, version_no="2.0", revision_no=2)

    pending = (await db_client.get(ME)).json()["items"]
    assert [row["document_id"] for row in pending] == [document.document_id]
    assert pending[0]["version_no"] == "2.0"


@pytest.mark.asyncio
async def test_phan_biet_chinh_sach_moi_va_ban_cap_nhat(db_client, db_session):
    hr = await seed_user(db_session, "hr", system_role=UserRole.HR)
    engineer = await seed_user(db_session, "dung")
    updated, _ = await seed_policy(db_session, hr, source_key="HR_LEAVE", title="Nghỉ phép")
    brand_new, _ = await seed_policy(
        db_session, hr, source_key="SEC_ACCESS", title="Bảo mật thông tin"
    )

    sign_in_as(engineer)
    await db_client.post(f"{ME}/{updated.document_id}/acknowledge")
    await add_version(db_session, updated, version_no="2.0", revision_no=2)

    flags = {row["document_id"]: row["is_new_version"] for row in (await db_client.get(ME)).json()["items"]}
    assert flags[updated.document_id] is True  # đã đọc bản cũ → đây là bản cập nhật
    assert flags[brand_new.document_id] is False  # chưa đọc bao giờ → chính sách mới


# --------------------------------------------------------------- điều kiện lọc


@pytest.mark.asyncio
async def test_khong_bat_buoc_thi_khong_hien_trong_danh_sach(db_client, db_session):
    hr = await seed_user(db_session, "hr", system_role=UserRole.HR)
    engineer = await seed_user(db_session, "en")
    await seed_policy(db_session, hr, requires_ack=False)

    sign_in_as(engineer)
    assert (await db_client.get(ME)).json()["items"] == []


@pytest.mark.asyncio
async def test_khong_co_phien_ban_active_tra_409(db_client, db_session):
    """Tài liệu chưa có phiên bản nào đang hiệu lực thì chưa xác nhận được.

    TV3 đã rút gọn VersionStatus còn ACTIVE/ARCHIVED, nên trạng thái "đang xử lý" biểu
    hiện bằng việc chưa có version ACTIVE, chứ không còn là một giá trị enum riêng.
    """
    hr = await seed_user(db_session, "hr", system_role=UserRole.HR)
    engineer = await seed_user(db_session, "phuc")

    # VersionStatus không còn PROCESSING/FAILED (bị bỏ ở commit f0a23cc, đơn giản hoá state
    # machine version). `_active_version()` (policy_acknowledgement_service.py) giờ chỉ còn xét
    # "có version ACTIVE hay không" — ARCHIVED tái tạo đúng nhánh "chưa có version sẵn sàng"
    # (POLICY_NOT_READY) mà không cần trạng thái đã bị xoá.
    document, _ = await seed_policy(db_session, hr, version_status=VersionStatus.ARCHIVED)

    sign_in_as(engineer)
    response = await db_client.post(f"{ME}/{document.document_id}/acknowledge")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "POLICY_NOT_READY"


@pytest.mark.asyncio
async def test_chinh_sach_da_luu_tru_khong_xac_nhan_duoc(db_client, db_session):
    hr = await seed_user(db_session, "hr", system_role=UserRole.HR)
    engineer = await seed_user(db_session, "giang")
    document, _ = await seed_policy(db_session, hr, document_status=DocumentStatus.ARCHIVED)

    sign_in_as(engineer)
    response = await db_client.post(f"{ME}/{document.document_id}/acknowledge")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "POLICY_ARCHIVED"
    assert (await db_client.get(ME)).json()["items"] == []


@pytest.mark.asyncio
async def test_hr_xem_duoc_noi_dung_archived_nhung_ky_su_khong_xem_duoc(
    db_client, db_session
):
    hr = await seed_user(db_session, "hr", system_role=UserRole.HR)
    engineer = await seed_user(db_session, "archived-reader")
    document, version = await seed_policy(
        db_session,
        hr,
        document_status=DocumentStatus.ARCHIVED,
        version_status=VersionStatus.ARCHIVED,
    )
    await add_chunk(db_session, version, "Nội dung chính sách đã lưu trữ")

    sign_in_as(hr)
    hr_response = await db_client.get(f"{CONSOLE}/{document.document_id}/content")
    assert hr_response.status_code == 200
    assert hr_response.json()["content"] == "Nội dung chính sách đã lưu trữ"

    sign_in_as(engineer)
    member_response = await db_client.get(f"{ME}/{document.document_id}/content")
    assert member_response.status_code == 409
    assert member_response.json()["detail"]["code"] == "POLICY_NOT_READY"


@pytest.mark.asyncio
async def test_restore_policy_kich_hoat_revision_moi_nhat_va_idempotent(
    db_client, db_session
):
    from sqlalchemy import func, select

    hr = await seed_user(db_session, "restore-hr", system_role=UserRole.HR)
    document, old = await seed_policy(
        db_session,
        hr,
        document_status=DocumentStatus.ARCHIVED,
        version_status=VersionStatus.ARCHIVED,
    )
    latest = await add_version(db_session, document, version_no="2.0", revision_no=2)
    latest.status = VersionStatus.ARCHIVED
    await db_session.commit()

    version_count_before = await db_session.scalar(
        select(func.count(DocumentVersion.version_id)).where(
            DocumentVersion.document_id == document.document_id
        )
    )
    sign_in_as(hr)
    first = await db_client.patch(f"{CONSOLE}/{document.document_id}/restore", json={})
    second = await db_client.patch(f"{CONSOLE}/{document.document_id}/restore", json={})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "ACTIVE"
    await db_session.refresh(document)
    await db_session.refresh(old)
    await db_session.refresh(latest)
    assert document.status == DocumentStatus.ACTIVE
    assert latest.status == VersionStatus.ACTIVE
    assert old.status == VersionStatus.ARCHIVED
    version_count_after = await db_session.scalar(
        select(func.count(DocumentVersion.version_id)).where(
            DocumentVersion.document_id == document.document_id
        )
    )
    assert version_count_after == version_count_before


# -------------------------------------------------------------------- coverage


@pytest.mark.asyncio
async def test_ty_le_xac_nhan_dem_dung(db_client, db_session):
    hr = await seed_user(db_session, "hr", system_role=UserRole.HR)
    engineers = [await seed_user(db_session, name) for name in ("hoa", "khanh", "linh", "minh", "nam")]
    document, _ = await seed_policy(db_session, hr)

    for engineer in engineers[:3]:
        sign_in_as(engineer)
        await db_client.post(f"{ME}/{document.document_id}/acknowledge")

    sign_in_as(hr)
    items = (await db_client.get(f"{CONSOLE}/coverage")).json()["items"]

    assert len(items) == 1
    assert items[0]["acknowledged_count"] == 3
    assert items[0]["required_count"] == 5
    assert items[0]["coverage_percent"] == 60.0


@pytest.mark.asyncio
async def test_admin_va_hr_khong_nam_trong_mau_so(db_client, db_session):
    """Chính sách nhân sự áp cho nhân viên; ADMIN/HR là người ban hành."""
    hr = await seed_user(db_session, "hr", system_role=UserRole.HR)
    await seed_user(db_session, "admin", system_role=UserRole.ADMIN)
    await seed_user(db_session, "oanh")
    document, _ = await seed_policy(db_session, hr)

    sign_in_as(hr)
    items = (await db_client.get(f"{CONSOLE}/coverage")).json()["items"]

    assert items[0]["required_count"] == 1  # chỉ mình "oanh"


@pytest.mark.asyncio
async def test_tai_khoan_khoa_khong_keo_ty_le_xuong(db_client, db_session):
    """Người đã nghỉ mà vẫn tính thì tỷ lệ không bao giờ đạt 100%, và HR sẽ bỏ qua con số đó."""
    hr = await seed_user(db_session, "hr", system_role=UserRole.HR)
    await seed_user(db_session, "quang")
    await seed_user(db_session, "da-nghi", status=UserStatus.INACTIVE)
    document, _ = await seed_policy(db_session, hr)

    sign_in_as(hr)
    items = (await db_client.get(f"{CONSOLE}/coverage")).json()["items"]

    assert items[0]["required_count"] == 1


@pytest.mark.asyncio
async def test_chi_tiet_tach_danh_sach_da_va_chua_xac_nhan(db_client, db_session):
    hr = await seed_user(db_session, "hr", system_role=UserRole.HR)
    done = await seed_user(db_session, "son")
    await seed_user(db_session, "tuan")
    document, _ = await seed_policy(db_session, hr)

    sign_in_as(done)
    await db_client.post(f"{ME}/{document.document_id}/acknowledge")

    sign_in_as(hr)
    body = (await db_client.get(f"{CONSOLE}/{document.document_id}/coverage")).json()

    assert [row["display_name"] for row in body["acknowledged"]] == ["Son"]
    assert [row["display_name"] for row in body["pending"]] == ["Tuan"]
    assert body["acknowledged"][0]["acknowledged_at"] is not None
    assert body["pending"][0]["acknowledged_at"] is None


@pytest.mark.asyncio
async def test_co_yeu_cau_xac_nhan_hien_trong_thu_vien(db_client, db_session):
    """Cờ phải có trong danh sách + chi tiết chính sách.

    Nếu không, HR không có đường bật lần đầu: màn hình tỷ lệ xác nhận chỉ liệt kê
    những tài liệu ĐÃ bật cờ, nên công tắc chỉ nằm bên đó là bế tắc.
    """
    hr = await seed_user(db_session, "hr", system_role=UserRole.HR)
    document, _ = await seed_policy(db_session, hr, requires_ack=False)

    sign_in_as(hr)
    listing = (await db_client.get(CONSOLE)).json()["items"]
    assert listing[0]["requires_acknowledgement"] is False

    await db_client.patch(
        f"{CONSOLE}/{document.document_id}/acknowledgement-required", json={"required": True}
    )
    detail = (await db_client.get(f"{CONSOLE}/{document.document_id}")).json()
    assert detail["requires_acknowledgement"] is True


@pytest.mark.asyncio
async def test_hr_bat_tat_yeu_cau_xac_nhan(db_client, db_session):
    hr = await seed_user(db_session, "hr", system_role=UserRole.HR)
    engineer = await seed_user(db_session, "uyen")
    document, _ = await seed_policy(db_session, hr, requires_ack=False)

    sign_in_as(hr)
    response = await db_client.patch(
        f"{CONSOLE}/{document.document_id}/acknowledgement-required", json={"required": True}
    )
    assert response.status_code == 200
    assert response.json()["requires_acknowledgement"] is True

    sign_in_as(engineer)
    assert len((await db_client.get(ME)).json()["items"]) == 1


# ------------------------------------------------------------------------ RBAC


@pytest.mark.asyncio
async def test_ky_su_khong_xem_duoc_ty_le_toan_cong_ty(db_client, db_session):
    hr = await seed_user(db_session, "hr", system_role=UserRole.HR)
    engineer = await seed_user(db_session, "viet")
    await seed_policy(db_session, hr)

    sign_in_as(engineer)
    assert (await db_client.get(f"{CONSOLE}/coverage")).status_code == 403


@pytest.mark.asyncio
async def test_chua_dang_nhap_khong_goi_duoc_danh_sach_cua_toi(db_client, db_session):
    hr = await seed_user(db_session, "hr", system_role=UserRole.HR)
    await seed_policy(db_session, hr)

    # Không sign_in_as -> không có cookie, không có override.
    assert (await db_client.get(ME)).status_code == 401
