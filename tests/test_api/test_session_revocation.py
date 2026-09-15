"""Kiểm thử logic thu hồi phiên — phần dễ sai nhất của đề xuất D.

Token chỉ lưu `issued_at` theo GIÂY NGUYÊN, còn mốc thu hồi là datetime. Nếu hai bên
lệch nhau phần lẻ giây thì người dùng đổi mật khẩu xong đăng nhập lại vẫn bị đá ra, và
lặp vô hạn. Các test dưới đây khoá đúng đường biên đó.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.api.dependencies import get_current_user, get_current_user_id, get_session_issued_at
from src.main import app
from src.model.enums import UserRole, UserStatus
from src.model.user import User
from src.services.auth_service import hash_password
from src.services.session_service import is_revoked, issue_token, read_token, revocation_stamp


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    for dependency in (get_current_user, get_current_user_id, get_session_issued_at):
        app.dependency_overrides.pop(dependency, None)


# ------------------------------------------------------------- logic thuần tuý


def test_chua_tung_thu_hoi_thi_moi_token_deu_song():
    """None nghĩa là chưa thu hồi gì — đúng trạng thái mọi tài khoản sau migration.

    Nếu hàm này trả True với None thì việc chạy migration sẽ đăng xuất toàn bộ người
    dùng đang online.
    """
    assert is_revoked(1_700_000_000, None) is False


def test_token_phat_hanh_truoc_moc_thu_hoi_bi_tu_choi():
    stamp = datetime(2026, 8, 21, 10, 0, 0)
    issued_at = int(stamp.replace(tzinfo=UTC).timestamp()) - 1
    assert is_revoked(issued_at, stamp) is True


def test_token_phat_hanh_sau_moc_thu_hoi_van_song():
    stamp = datetime(2026, 8, 21, 10, 0, 0)
    issued_at = int(stamp.replace(tzinfo=UTC).timestamp()) + 1
    assert is_revoked(issued_at, stamp) is False


def test_token_cung_giay_voi_moc_thu_hoi_van_song():
    """Cửa sổ 1 giây có chủ ý.

    Đây là ca khiến người dùng kẹt vòng lặp nếu làm sai: đổi mật khẩu lúc 10:00:00.3,
    đăng nhập lại lúc 10:00:00.8 -> token ghi issued_at = 10:00:00. Nếu mốc thu hồi giữ
    phần lẻ giây thì token vừa tạo bị coi là "phát hành trước khi thu hồi" và chết ngay.
    """
    stamp = datetime(2026, 8, 21, 10, 0, 0)
    issued_at = int(stamp.replace(tzinfo=UTC).timestamp())
    assert is_revoked(issued_at, stamp) is False


def test_moc_thu_hoi_khong_giu_phan_le_giay():
    assert revocation_stamp().microsecond == 0


def test_moc_thu_hoi_la_naive_khop_kieu_cot():
    """Trộn datetime aware và naive trong cùng một cột là lỗi chỉ nổ ở production."""
    assert revocation_stamp().tzinfo is None


def test_dang_nhap_lai_ngay_sau_khi_thu_hoi_khong_bi_ket():
    """Đường đi trọn vẹn: thu hồi rồi phát token mới -> token mới phải sống."""
    now = int(datetime.now(UTC).timestamp())
    stamp = revocation_stamp(now=now)
    fresh_token = issue_token(42, now=now)
    _, issued_at, _ = read_token(fresh_token, now=now)
    assert is_revoked(issued_at, stamp) is False


# ------------------------------------------------------- đường đi qua HTTP


API = "/api/v1/console"


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
    app.dependency_overrides[get_current_user_id] = lambda: admin.user_id
    return admin


@pytest.mark.asyncio
async def test_token_cu_bi_tu_choi_sau_khi_thu_hoi(db_client, db_session):
    admin = await seed_admin(db_session)
    admin.session_invalid_before = datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=5)
    await db_session.commit()

    # Token phát hành "lúc này" -> nằm trước mốc thu hồi ở tương lai -> phải chết.
    app.dependency_overrides[get_session_issued_at] = lambda: int(datetime.now(UTC).timestamp())

    response = await db_client.get(f"{API}/admin/overview")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "SESSION_REVOKED"


@pytest.mark.asyncio
async def test_token_moi_van_dung_duoc_sau_khi_thu_hoi(db_client, db_session):
    admin = await seed_admin(db_session)
    admin.session_invalid_before = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5)
    await db_session.commit()

    app.dependency_overrides[get_session_issued_at] = lambda: int(datetime.now(UTC).timestamp())

    response = await db_client.get(f"{API}/admin/overview")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_khong_co_cookie_thi_khong_kiem_thu_hoi(db_client, db_session):
    """Lối tắt X-User-Id ở dev không mang issued_at — không được vì thế mà chặn nhầm."""
    admin = await seed_admin(db_session)
    admin.session_invalid_before = datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=5)
    await db_session.commit()

    app.dependency_overrides[get_session_issued_at] = lambda: None

    response = await db_client.get(f"{API}/admin/overview")
    assert response.status_code == 200
