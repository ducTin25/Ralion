"""Kiểm thử luồng HR upload tài liệu chính sách.

Phạm vi: phần TV4 chịu trách nhiệm — convert file, chuẩn hoá header, kiểm quyền,
giới hạn định dạng/kích thước, và dịch lỗi của TV3 sang thông báo tiếng Việt.

`ingest_policy_document` thật KHÔNG được gọi ở đây vì nó dùng `pg_advisory_xact_lock`,
hàm chỉ có trên PostgreSQL (đã kiểm chứng: SQLite báo "no such function: hashtext").
Nó được tiêm bản giả qua `get_policy_ingestor`. Phần ingest thật thuộc TV3 và do TV3 test.
"""

from datetime import date

import pytest

from src.ai.providers.embeddings_fake import FakeEmbedder
from src.api.dependencies import (
    get_current_user,
    get_current_user_id,
    get_embedder,
    get_policy_ingestor,
)
from src.main import app
from src.model.enums import DocumentDomain, DocumentStatus, PolicyCategory, UserRole, UserStatus
from src.model.knowledge_document import KnowledgeDocument
from src.model.user import User
from src.services import document_conversion_service, hr_policy_service, storage_service
from src.services.auth_service import hash_password
from src.services.document_conversion_service import DocumentConversionError

API = "/api/v1/console/hr/policies"

VALID_MARKDOWN = """# Quy định nghỉ phép

- **Mã tài liệu:** HR_LEAVE_POLICY
- **Phiên bản:** 3.2 — Ngày hiệu lực: 01/01/2026
- **Mục đích:** Quy định số ngày nghỉ phép hằng năm.

## 1. Phạm vi áp dụng

Áp dụng cho toàn bộ nhân viên chính thức.
"""

MARKDOWN_WITHOUT_HEADER = """# Quy định nghỉ phép

Nội dung chính sách không có dòng phiên bản.
"""


# --------------------------------------------------------------------- fixtures


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    for dependency in (get_current_user, get_current_user_id, get_embedder, get_policy_ingestor):
        app.dependency_overrides.pop(dependency, None)


@pytest.fixture(autouse=True)
def stub_storage(monkeypatch):
    """Không gọi Cloudinary thật trong test."""
    monkeypatch.setattr(
        storage_service,
        "upload_document_bytes",
        lambda content, folder, filename: f"https://storage.test/{folder}/{filename}",
    )


class RecordingIngestor:
    """Ghi lại request TV4 gửi sang, và tạo document tối thiểu để endpoint trả về được."""

    def __init__(self, *, raises: Exception | None = None):
        self.raises = raises
        self.calls: list = []

    async def __call__(self, session, request, embedder, *, config=None):
        self.calls.append(request)
        if self.raises is not None:
            raise self.raises
        document = KnowledgeDocument(
            created_by_user_id=request.created_by_user_id,
            knowledge_domain=DocumentDomain.POLICY,
            policy_category=request.policy_category,
            source_key=request.document_code.upper(),
            title=request.title,
            source_url=request.source_url,
            status=DocumentStatus.ACTIVE,
        )
        session.add(document)
        await session.flush()
        return document


async def seed_hr(db_session) -> User:
    user = User(
        email="hr@onboarding.dev",
        display_name="Linh Tran",
        password_hash=hash_password("hr-password"),
        system_role=UserRole.HR,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_user_id] = lambda: user.user_id
    app.dependency_overrides[get_embedder] = lambda: FakeEmbedder()
    return user


def use_ingestor(ingestor: RecordingIngestor) -> None:
    app.dependency_overrides[get_policy_ingestor] = lambda: ingestor


def upload_payload(**overrides) -> dict:
    payload = {
        "document_code": "HR_LEAVE_POLICY",
        "title": "Quy định nghỉ phép",
        "policy_category": "HR_POLICY",
    }
    payload.update(overrides)
    return payload


# ----------------------------------------------------------- convert + header


def test_convert_markdown_giu_nguyen_noi_dung():
    result = document_conversion_service.convert_to_markdown(
        VALID_MARKDOWN.encode("utf-8"), "policy.md"
    )
    assert result == VALID_MARKDOWN


def test_inspect_doc_duoc_metadata_tu_header():
    converted = document_conversion_service.inspect(VALID_MARKDOWN.encode("utf-8"), "policy.md")
    assert converted.detected_version == "3.2"
    assert converted.detected_effective_date == date(2026, 1, 1)
    assert converted.detected_document_code == "HR_LEAVE_POLICY"
    assert converted.detected_title == "Quy định nghỉ phép"
    assert converted.has_valid_header
    assert converted.warnings == []


def test_inspect_thieu_header_khong_nem_loi():
    """PDF convert ra thường mất header — đây là trường hợp bình thường, không phải lỗi."""
    converted = document_conversion_service.inspect(
        MARKDOWN_WITHOUT_HEADER.encode("utf-8"), "policy.md"
    )
    assert converted.detected_version is None
    assert converted.has_valid_header is False
    assert any("phiên bản" in warning.lower() for warning in converted.warnings)


def test_ensure_policy_header_chen_khi_thieu():
    result = document_conversion_service.ensure_policy_header(
        MARKDOWN_WITHOUT_HEADER, version="1.0", effective_date=date(2026, 3, 15)
    )
    assert result.startswith("- **Phiên bản:** 1.0 — Ngày hiệu lực: 15/03/2026")
    # Chèn xong thì TV3 phải parse được
    from src.modules.knowledge.policy_metadata import parse_policy_version_metadata

    assert parse_policy_version_metadata(result) == ("1.0", date(2026, 3, 15))


def test_ensure_policy_header_giu_nguyen_khi_da_co():
    """Ưu tiên giá trị trong tài liệu gốc hơn giá trị HR gõ lại."""
    result = document_conversion_service.ensure_policy_header(
        VALID_MARKDOWN, version="9.9", effective_date=date(2030, 1, 1)
    )
    assert result == VALID_MARKDOWN
    assert "9.9" not in result


@pytest.mark.parametrize("filename", ["policy.exe", "policy.txt", "policy"])
def test_validate_chan_dinh_dang_khong_ho_tro(filename):
    with pytest.raises(DocumentConversionError):
        document_conversion_service.validate_upload(filename, 1024, max_mb=10)


def test_validate_chan_file_qua_lon():
    with pytest.raises(DocumentConversionError) as exc:
        document_conversion_service.validate_upload("a.md", 11 * 1024 * 1024, max_mb=10)
    assert "10 MB" in str(exc.value)


def test_validate_chan_file_rong():
    with pytest.raises(DocumentConversionError):
        document_conversion_service.validate_upload("a.md", 0, max_mb=10)


# ------------------------------------------------------------ dịch lỗi TV3


@pytest.mark.parametrize(
    ("message", "expected_status", "expected_code"),
    [
        ("Source version '3.2' already exists with a different checksum", 409, "VERSION_CONTENT_MISMATCH"),
        ("Policy source is missing '- **Phiên bản:** ... — Ngày hiệu lực: ...'", 422, "MISSING_VERSION_HEADER"),
        ("Unsupported effective date: '2026-01-01'; expected DD/MM/YYYY", 422, "INVALID_EFFECTIVE_DATE"),
        ("Policy content must not be empty", 422, "EMPTY_CONTENT"),
        ("document_code must not be empty", 422, "MISSING_DOCUMENT_CODE"),
        ("Một lỗi chưa từng gặp", 422, "INGESTION_FAILED"),
    ],
)
def test_dich_loi_tv3_sang_tieng_viet(message, expected_status, expected_code):
    status_code, code, vietnamese = hr_policy_service._translate_ingest_error(message)
    assert (status_code, code) == (expected_status, expected_code)
    assert vietnamese  # luôn có thông báo, không để HR thấy chuỗi tiếng Anh trống


# ------------------------------------------------------------------ endpoint


@pytest.mark.asyncio
async def test_inspect_tra_metadata_cho_man_hinh_review(db_client, db_session):
    await seed_hr(db_session)
    response = await db_client.post(
        f"{API}/inspect",
        files={"file": ("policy.md", VALID_MARKDOWN.encode("utf-8"), "text/markdown")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["detected_version"] == "3.2"
    assert body["detected_document_code"] == "HR_LEAVE_POLICY"
    assert body["existing_document_id"] is None
    assert "Quy định nghỉ phép" in body["markdown_preview"]


@pytest.mark.asyncio
async def test_upload_thanh_cong_gui_dung_du_lieu_cho_tv3(db_client, db_session):
    await seed_hr(db_session)
    ingestor = RecordingIngestor()
    use_ingestor(ingestor)

    response = await db_client.post(
        f"{API}/upload",
        files={"file": ("policy.md", VALID_MARKDOWN.encode("utf-8"), "text/markdown")},
        data=upload_payload(),
    )
    assert response.status_code == 201, response.text

    assert len(ingestor.calls) == 1
    request = ingestor.calls[0]
    assert request.document_code == "HR_LEAVE_POLICY"
    assert request.policy_category == PolicyCategory.HR_POLICY
    assert request.content == VALID_MARKDOWN          # header sẵn có nên không bị chèn thêm
    assert request.source_url.startswith("https://storage.test/")


@pytest.mark.asyncio
async def test_upload_thieu_header_thi_chen_tu_gia_tri_hr_nhap(db_client, db_session):
    """Đây là điểm mấu chốt để nhận được PDF: TV4 vá header trước khi giao cho TV3."""
    await seed_hr(db_session)
    ingestor = RecordingIngestor()
    use_ingestor(ingestor)

    response = await db_client.post(
        f"{API}/upload",
        files={"file": ("policy.md", MARKDOWN_WITHOUT_HEADER.encode("utf-8"), "text/markdown")},
        data=upload_payload(version="2.0", effective_date="2026-06-01"),
    )
    assert response.status_code == 201, response.text

    content = ingestor.calls[0].content
    assert content.startswith("- **Phiên bản:** 2.0 — Ngày hiệu lực: 01/06/2026")


@pytest.mark.asyncio
async def test_upload_trung_version_khac_noi_dung_tra_409(db_client, db_session):
    await seed_hr(db_session)
    use_ingestor(
        RecordingIngestor(
            raises=ValueError("Source version '3.2' already exists with a different checksum")
        )
    )
    response = await db_client.post(
        f"{API}/upload",
        files={"file": ("policy.md", VALID_MARKDOWN.encode("utf-8"), "text/markdown")},
        data=upload_payload(),
    )
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "VERSION_CONTENT_MISMATCH"
    assert "tăng số phiên bản" in detail["message"]


@pytest.mark.asyncio
async def test_upload_dinh_dang_khong_ho_tro_tra_422(db_client, db_session):
    await seed_hr(db_session)
    use_ingestor(RecordingIngestor())
    response = await db_client.post(
        f"{API}/upload",
        files={"file": ("policy.exe", b"MZ\x00\x00", "application/octet-stream")},
        data=upload_payload(),
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "FILE_NOT_READABLE"


@pytest.mark.asyncio
async def test_upload_thieu_ma_tai_lieu_tra_422(db_client, db_session):
    await seed_hr(db_session)
    use_ingestor(RecordingIngestor())
    response = await db_client.post(
        f"{API}/upload",
        files={"file": ("policy.md", VALID_MARKDOWN.encode("utf-8"), "text/markdown")},
        data=upload_payload(document_code="   "),
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "MISSING_DOCUMENT_CODE"


@pytest.mark.asyncio
async def test_nguoi_dung_thuong_khong_upload_duoc(db_client, db_session):
    """Chỉ HR và ADMIN mới quản lý được tài liệu tổ chức."""
    plain = User(
        email="engineer@onboarding.dev",
        display_name="An Nguyen",
        password_hash=hash_password("member-password"),
        system_role=None,
        status=UserStatus.ACTIVE,
    )
    db_session.add(plain)
    await db_session.commit()
    await db_session.refresh(plain)
    app.dependency_overrides[get_current_user] = lambda: plain
    app.dependency_overrides[get_current_user_id] = lambda: plain.user_id

    response = await db_client.post(
        f"{API}/upload",
        files={"file": ("policy.md", VALID_MARKDOWN.encode("utf-8"), "text/markdown")},
        data=upload_payload(),
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "CONSOLE_ACCESS_REQUIRED"


# ------------------------------------------------------------- FakeEmbedder


@pytest.mark.asyncio
async def test_fake_embedder_tat_dinh_va_chuan_hoa():
    embedder = FakeEmbedder()
    first, second = await embedder.embed(["xin chào", "xin chào"])
    assert first == second                       # tất định → test so sánh được
    assert len(first) == embedder.dimension
    norm = sum(value * value for value in first) ** 0.5
    assert abs(norm - 1.0) < 1e-9                # pgvector dùng cosine nên phải chuẩn hoá
