"""Kiểm thử lớp phiên đăng nhập dựa trên cookie có chữ ký.

Các test này thuần logic ký/kiểm chữ ký nên không cần database, chạy nhanh và
không phụ thuộc dữ liệu mẫu.
"""

import time

import pytest

from src.services.session_service import (
    SESSION_TTL_SECONDS,
    SessionError,
    issue_token,
    read_token,
    should_refresh,
)


def test_token_hop_le_doc_duoc_user_id():
    token = issue_token(42)
    user_id, issued_at, expires_at = read_token(token)
    assert user_id == 42
    assert expires_at - issued_at == SESSION_TTL_SECONDS


def test_thieu_token_bao_chua_dang_nhap():
    with pytest.raises(SessionError) as exc:
        read_token(None)
    assert exc.value.code == "NO_SESSION"


@pytest.mark.parametrize("token", ["", "abc", "1.2.3", "1.2.3.4.5"])
def test_token_sai_dinh_dang_bi_tu_choi(token):
    with pytest.raises(SessionError) as exc:
        read_token(token)
    assert exc.value.code in {"NO_SESSION", "MALFORMED_SESSION"}


def test_doi_user_id_lam_hong_chu_ky():
    """Đây là điểm mấu chốt: client không thể tự nâng mình thành user khác."""
    token = issue_token(7)
    _, issued_at, expires_at = read_token(token)
    signature = token.rsplit(".", 1)[1]
    forged = f"1.{issued_at}.{expires_at}.{signature}"
    with pytest.raises(SessionError) as exc:
        read_token(forged)
    assert exc.value.code == "INVALID_SIGNATURE"


def test_keo_dai_han_lam_hong_chu_ky():
    """Không thể tự gia hạn phiên bằng cách sửa expires_at."""
    token = issue_token(7)
    user_id, issued_at, expires_at = read_token(token)
    signature = token.rsplit(".", 1)[1]
    forged = f"{user_id}.{issued_at}.{expires_at + 86400}.{signature}"
    with pytest.raises(SessionError) as exc:
        read_token(forged)
    assert exc.value.code == "INVALID_SIGNATURE"


def test_token_het_han_bi_tu_choi():
    now = int(time.time())
    token = issue_token(7, now=now - SESSION_TTL_SECONDS - 1)
    with pytest.raises(SessionError) as exc:
        read_token(token, now=now)
    assert exc.value.code == "SESSION_EXPIRED"


def test_should_refresh_chi_bat_khi_qua_nua_thoi_han():
    now = int(time.time())
    assert should_refresh(now + 60, now=now) is True
    assert should_refresh(now + SESSION_TTL_SECONDS, now=now) is False
