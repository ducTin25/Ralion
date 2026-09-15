"""Kiểm thử authentication và RBAC ở tầng HTTP.

Database được thay bằng stub trong bộ nhớ qua `dependency_overrides`, nên test chạy
được mà không cần PostgreSQL. Mục tiêu là kiểm tra *quyết định phân quyền*, không
phải truy vấn SQL.
"""

from datetime import datetime

import pytest

from src.api.dependencies import get_current_user, get_current_user_id
from src.main import app
from src.model.enums import ResponseLength, ResponseTone, UserRole, UserStatus
from src.model.session import get_db
from src.services.session_service import SESSION_COOKIE_NAME, issue_token


class FakeUser:
    def __init__(self, user_id: int, role: UserRole | None, status: UserStatus = UserStatus.ACTIVE):
        self.user_id = user_id
        self.email = f"user{user_id}@onboarding.dev"
        self.display_name = f"User {user_id}"
        self.system_role = role
        self.status = status
        self.created_at = datetime(2026, 1, 1)
        self.created_by_admin_id = None
        self.start_date = None
        self.session_invalid_before = None
        # `require_password_changed` đọc cờ này trước mọi kiểm tra vai trò.
        self.must_change_password = False
        # F5 chat personalization — `describe_current_user` đọc thẳng 2 cờ này.
        self.response_length = ResponseLength.STANDARD
        self.response_tone = ResponseTone.NEUTRAL


ADMIN = FakeUser(1, UserRole.ADMIN)
HR = FakeUser(2, UserRole.HR)
PLAIN = FakeUser(3, None)
LOCKED = FakeUser(4, UserRole.ADMIN, UserStatus.INACTIVE)
USERS = {user.user_id: user for user in (ADMIN, HR, PLAIN, LOCKED)}


class _EmptyResult:
    def scalars(self):
        return iter(())

    def all(self):
        """Truy vấn trả nhiều cột (ví dụ tài liệu kèm phiên bản) dùng .all() thay .scalars()."""
        return []


class FakeSession:
    """AsyncSession tối giản: tra user theo id, mọi truy vấn khác trả rỗng.

    Đủ để các endpoint chạy hết luồng mà không cần PostgreSQL, nhờ vậy test phân
    quyền không phụ thuộc vào việc máy có database hay không.
    """

    async def get(self, model, pk):
        return USERS.get(pk) if model.__name__ == "User" else None

    async def execute(self, stmt):
        return _EmptyResult()

    async def scalar(self, stmt):
        return None


def use_fake_db() -> None:
    app.dependency_overrides[get_db] = lambda: FakeSession()


def sign_in_as(user: FakeUser) -> None:
    """Ép danh tính phiên, giữ nguyên chuỗi require_admin/require_hr_or_admin thật."""
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_user_id] = lambda: user.user_id
    use_fake_db()


def session_cookie(user_id: int, **kwargs) -> dict[str, str]:
    """Header Cookie thay vì tham số cookies= (đã bị httpx đánh dấu deprecated)."""
    return {"Cookie": f"{SESSION_COOKIE_NAME}={issue_token(user_id, **kwargs)}"}


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


# --------------------------------------------------------------- authentication


@pytest.mark.asyncio
async def test_khong_co_danh_tinh_bi_tu_choi_401(client):
    """Tiêu chí 6.6: người chưa đăng nhập không truy cập được API nghiệp vụ."""
    response = await client.get("/api/v1/console/admin/overview")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "UNAUTHENTICATED"


@pytest.mark.asyncio
async def test_cookie_gia_mao_bi_tu_choi_401(client):
    response = await client.get(
        "/api/v1/console/admin/overview",
        headers={"Cookie": f"{SESSION_COOKIE_NAME}=1.0.9999999999.chu-ky-bia-dat"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "INVALID_SIGNATURE"


@pytest.mark.asyncio
async def test_cookie_het_han_bi_tu_choi_401(client):
    response = await client.get(
        "/api/v1/console/admin/overview", headers=session_cookie(1, now=0, ttl=1)
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "SESSION_EXPIRED"


@pytest.mark.asyncio
async def test_cookie_hop_le_mo_duoc_console(client):
    """Đường đi thuận: cookie do server ký mở được khu vực Admin."""
    use_fake_db()
    response = await client.get("/api/v1/console/admin/overview", headers=session_cookie(ADMIN.user_id))
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_logout_xoa_cookie_va_khong_can_dang_nhap(client):
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    assert response.json()["outcome"] == "SIGNED_OUT"
    # Cookie bị xoá bằng cách set lại rỗng với thời hạn trong quá khứ.
    assert SESSION_COOKIE_NAME in response.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_refresh_khong_co_phien_bi_tu_choi_401(client):
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


# ------------------------------------------------------------------------ RBAC


@pytest.mark.asyncio
async def test_hr_khong_vao_duoc_khu_vuc_admin_403(client):
    """HR không được quản lý tài khoản, dự án hay membership."""
    sign_in_as(HR)
    response = await client.get("/api/v1/console/admin/overview")
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ADMIN_REQUIRED"


@pytest.mark.asyncio
async def test_hr_khong_gan_duoc_membership_403(client):
    sign_in_as(HR)
    response = await client.post(
        "/api/v1/console/admin/memberships",
        json={"user_id": 3, "project_id": 1, "project_role": "ENGINEER", "status": "ACTIVE"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_nguoi_dung_thuong_khong_vao_duoc_console_403(client):
    """Engineer không sửa được dữ liệu quản trị, cũng không mở được thư viện HR."""
    sign_in_as(PLAIN)
    admin = await client.get("/api/v1/console/admin/users")
    hr = await client.get("/api/v1/console/hr/policies")
    assert admin.status_code == 403
    assert admin.json()["detail"]["code"] == "ADMIN_REQUIRED"
    assert hr.status_code == 403
    assert hr.json()["detail"]["code"] == "CONSOLE_ACCESS_REQUIRED"


@pytest.mark.asyncio
async def test_admin_vao_duoc_thu_vien_hr(client):
    """require_hr_or_admin cho phép Admin, không chỉ HR."""
    sign_in_as(ADMIN)
    response = await client.get("/api/v1/console/hr/policies")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_tai_khoan_bi_khoa_khong_dung_duoc_api_403(client):
    """Khoá tài khoản phải chặn cả phiên đang mở, không chỉ lần đăng nhập sau."""
    use_fake_db()
    response = await client.get(
        "/api/v1/console/admin/overview", headers=session_cookie(LOCKED.user_id)
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ACCOUNT_INACTIVE"


@pytest.mark.asyncio
async def test_auth_me_tra_ve_danh_tinh_phien(client):
    """Frontend lấy tên/quyền từ đây thay vì đoán từ localStorage."""
    use_fake_db()
    response = await client.get("/api/v1/auth/me", headers=session_cookie(HR.user_id))
    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == HR.user_id
    assert body["system_role"] == "HR"
    assert body["expires_at"] is not None


@pytest.mark.asyncio
async def test_refresh_cap_cookie_moi(client):
    use_fake_db()
    response = await client.post("/api/v1/auth/refresh", headers=session_cookie(ADMIN.user_id))
    assert response.status_code == 200
    assert SESSION_COOKIE_NAME in response.headers.get("set-cookie", "")
