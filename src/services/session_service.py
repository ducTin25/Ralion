"""Phiên đăng nhập dựa trên cookie có chữ ký HMAC.

Token là chuỗi tự chứa `user_id.issued_at.expires_at.signature`, ký bằng
`SESSION_SECRET`. Không cần bảng DB nên không phát sinh migration, và mỗi request
chỉ tốn một phép so sánh HMAC thay vì một truy vấn.

Đánh đổi đã biết: vì không có kho phiên phía server, `POST /auth/logout` chỉ xoá
cookie ở trình duyệt. Một token bị lộ vẫn hợp lệ cho tới khi hết hạn. Đây là lý do
TTL để ngắn (30 phút) và có `/auth/refresh` để gia hạn khi người dùng còn hoạt động.
Khi cần thu hồi tức thì, thay bằng bảng `user_sessions` và kiểm tra `revoked_at`.
"""

import hashlib
import hmac
import time
from datetime import UTC, datetime

from src.config import get_settings

SESSION_COOKIE_NAME = "ralion_session"
SESSION_TTL_SECONDS = 30 * 60
# Chỉ gia hạn khi phiên đã dùng quá một nửa TTL, tránh ghi cookie mới mỗi request.
REFRESH_THRESHOLD_SECONDS = SESSION_TTL_SECONDS // 2


class SessionError(Exception):
    """Token thiếu, sai định dạng, sai chữ ký hoặc đã hết hạn."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _secret() -> bytes:
    settings = get_settings()
    secret = settings.session_secret
    if not secret:
        raise SessionError("SESSION_SECRET_MISSING", "SESSION_SECRET chưa được cấu hình.")
    return secret.encode()


def _sign(payload: str) -> str:
    return hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()


def issue_token(user_id: int, *, now: int | None = None, ttl: int = SESSION_TTL_SECONDS) -> str:
    """Tạo token cho một user. `now` chỉ để test bơm thời gian giả."""
    issued_at = int(time.time()) if now is None else now
    expires_at = issued_at + ttl
    payload = f"{user_id}.{issued_at}.{expires_at}"
    return f"{payload}.{_sign(payload)}"


def read_token(token: str | None, *, now: int | None = None) -> tuple[int, int, int]:
    """Trả về (user_id, issued_at, expires_at) hoặc ném SessionError.

    Chữ ký được kiểm tra trước khi tin bất kỳ trường nào, và so sánh bằng
    `compare_digest` để không rò rỉ thông tin qua thời gian thực thi.
    """
    if not token:
        raise SessionError("NO_SESSION", "Chưa đăng nhập.")
    parts = token.split(".")
    if len(parts) != 4:
        raise SessionError("MALFORMED_SESSION", "Phiên đăng nhập không hợp lệ.")
    raw_user_id, raw_issued, raw_expires, signature = parts
    payload = f"{raw_user_id}.{raw_issued}.{raw_expires}"
    if not hmac.compare_digest(_sign(payload), signature):
        raise SessionError("INVALID_SIGNATURE", "Phiên đăng nhập không hợp lệ.")
    try:
        user_id, issued_at, expires_at = int(raw_user_id), int(raw_issued), int(raw_expires)
    except ValueError as exc:
        raise SessionError("MALFORMED_SESSION", "Phiên đăng nhập không hợp lệ.") from exc
    current = int(time.time()) if now is None else now
    if current >= expires_at:
        raise SessionError("SESSION_EXPIRED", "Phiên đăng nhập đã hết hạn.")
    return user_id, issued_at, expires_at


def revocation_stamp(*, now: int | None = None) -> datetime:
    """Mốc ghi vào `User.session_invalid_before` để giết mọi phiên đang mở.

    Cắt bỏ phần lẻ giây, và đó là điểm mấu chốt: token chỉ lưu `issued_at` theo giây
    nguyên. Nếu mốc này là 10:00:00.7 còn token vừa phát hành lúc 10:00:00.9 (ghi thành
    10:00:00) thì phép so sánh `issued_at < invalid_before` sẽ giết luôn token vừa tạo —
    người dùng đổi mật khẩu xong đăng nhập lại vẫn bị đá ra, lặp vô hạn.

    Cắt xuống giây khiến phép so sánh dùng `<` bỏ qua đúng một cửa sổ 1 giây: token phát
    hành trong cùng giây với lúc thu hồi vẫn sống. Đánh đổi này rẻ hơn nhiều so với việc
    khoá người dùng ra ngoài vĩnh viễn.

    Trả về datetime naive để khớp kiểu cột (xem `User.session_invalid_before`).
    """
    moment = datetime.now(UTC) if now is None else datetime.fromtimestamp(now, UTC)
    return moment.replace(microsecond=0, tzinfo=None)


def is_revoked(issued_at: int, invalid_before: datetime | None) -> bool:
    """Token phát hành trước mốc thu hồi thì không còn hợp lệ.

    `None` nghĩa là chưa từng thu hồi gì — đúng trạng thái của mọi tài khoản ngay sau
    khi chạy migration, nên không ai bị đăng xuất vì việc triển khai tính năng này.
    """
    if invalid_before is None:
        return False
    return issued_at < int(invalid_before.replace(tzinfo=UTC).timestamp())


def should_refresh(expires_at: int, *, now: int | None = None) -> bool:
    current = int(time.time()) if now is None else now
    return (expires_at - current) < REFRESH_THRESHOLD_SECONDS


def cookie_params() -> dict[str, object]:
    """Tham số cookie dùng chung cho set_cookie/delete_cookie.

    `secure` bật theo môi trường: localhost chạy HTTP nên bắt buộc secure sẽ khiến
    trình duyệt bỏ cookie. `samesite=lax` đủ chặn CSRF cho luồng điều hướng thường,
    vì mọi API ghi đều dùng POST/PATCH có Content-Type: application/json.
    """
    settings = get_settings()
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": settings.app_env == "production",
        "path": "/",
    }
