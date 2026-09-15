"""Hai lỗi cấu hình/chẩn đoán đã sửa, ghim lại để không tái diễn.

1. `CORS_ORIGINS` bị xuống dòng trong `.env` (AUDIT F-27f) từng sinh ra origin rác `http://`
   và làm mất origin cuối. Giá trị trong `.env` đã sửa, nhưng bản thân parser cũng phải chịu
   được lỗi định dạng — nếu không, lần sau ai đó gõ lại y hệt là bug quay về.
2. `POST /projects/pm` trước đây báo mọi `IntegrityError` là "Project key already exists", kể
   cả khi nguyên nhân thật là FK `created_by_admin_id` trỏ tới user không tồn tại.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from src.api.routers.project_router import _violated_constraint
from src.config import Settings


def _settings(cors: str) -> Settings:
    # `_env_file=None` để test không phụ thuộc `.env` của máy đang chạy.
    return Settings(cors_origins=cors, _env_file=None)


def test_cors_origins_drops_the_empty_fragment_left_by_a_wrapped_env_line():
    settings = _settings("http://localhost:3000,http://127.0.0.1:3000,http://\n  localhost:5173")

    origins = settings.cors_origin_list

    assert "" not in origins
    # Mảnh vỡ do xuống dòng không được lọt vào cấu hình CORS như một origin hợp lệ.
    assert "http://" not in origins


def test_cors_origins_trims_whitespace_and_keeps_declared_order():
    settings = _settings(" http://a.test , http://b.test ,, http://a.test ")

    assert settings.cors_origin_list == ["http://a.test", "http://b.test"]


class _OrigError(Exception):
    def __init__(self, constraint_name: str | None = None, message: str = ""):
        super().__init__(message)
        if constraint_name is not None:
            self.constraint_name = constraint_name


def _integrity_error(orig: Exception) -> IntegrityError:
    return IntegrityError("INSERT ...", {}, orig)


def test_violated_constraint_reads_the_name_postgres_reports():
    exc = _integrity_error(_OrigError(constraint_name="fk_projects_created_by_admin_id_users"))

    assert _violated_constraint(exc) == "fk_projects_created_by_admin_id_users"


def test_violated_constraint_falls_back_to_the_message_on_sqlite():
    # sqlite3.IntegrityError không có `constraint_name`; tên ràng buộc chỉ nằm trong thông điệp.
    exc = _integrity_error(_OrigError(message="UNIQUE constraint failed: uq_projects_key"))

    assert _violated_constraint(exc) == "uq_projects_key"


@pytest.mark.parametrize("orig", [_OrigError(message="something entirely unrelated"), _OrigError()])
def test_violated_constraint_returns_none_rather_than_guessing(orig):
    assert _violated_constraint(_integrity_error(orig)) is None
