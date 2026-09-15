"""Fixture dọn dẹp data test khỏi DB thật sau khi chạy — tests không có DB riêng biệt
(xem SETUP_GUIDE.md), nên phải tự dọn để không tích rác project/user TEST* qua nhiều lần chạy.
Đây là hành vi riêng của test (hard-delete thật), không phải convention soft-delete của app.

Gộp chung 1 fixture (thay vì 2 fixture độc lập) để đảm bảo đúng thứ tự xoá:
project_memberships trước, rồi projects, rồi users cuối cùng — tránh vi phạm FK
(user không xoá được khi vẫn còn membership tham chiếu).
"""

import uuid

import pytest_asyncio
from sqlalchemy import delete

from src.model.project import Project
from src.model.project_membership import ProjectMembership
from src.model.session import AsyncSessionLocal
from src.model.user import User


class _TestDataTracker:
    def __init__(self) -> None:
        self.project_ids: list[int] = []
        self.user_ids: list[int] = []


@pytest_asyncio.fixture
async def test_data():
    tracker = _TestDataTracker()
    yield tracker

    if not tracker.project_ids and not tracker.user_ids:
        return

    async with AsyncSessionLocal() as db:
        if tracker.project_ids:
            await db.execute(delete(ProjectMembership).where(ProjectMembership.project_id.in_(tracker.project_ids)))
        if tracker.user_ids:
            await db.execute(delete(ProjectMembership).where(ProjectMembership.user_id.in_(tracker.user_ids)))
        if tracker.project_ids:
            await db.execute(delete(Project).where(Project.project_id.in_(tracker.project_ids)))
        if tracker.user_ids:
            await db.execute(delete(User).where(User.user_id.in_(tracker.user_ids)))
        await db.commit()


@pytest_asyncio.fixture
async def admin_id(client, test_data) -> int:
    """Admin riêng cho mỗi test, không phụ thuộc ID hoặc dữ liệu seed của môi trường."""
    response = await client.post(
        "/api/v1/users",
        json={
            "email": f"test-admin-{uuid.uuid4().hex[:8]}@onboarding.dev",
            "display_name": "Test Admin",
            "system_role": "ADMIN",
        },
    )
    assert response.status_code == 201
    user_id = response.json()["user_id"]
    test_data.user_ids.append(user_id)
    return user_id
