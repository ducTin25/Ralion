"""Test PM Documents — kết nối GitHub repo thật + đồng bộ (bổ sung bên cạnh 2 lựa chọn cũ:
upload file đơn lẻ và quét folder local, xem RepoScanWizard). Trước đây project luôn mang
`github_repo="pending/<key>"` (giá trị đặt lúc tạo, xem project_service.create_project) và
`github_sync_worker.sync_docs` chưa từng được gọi từ bất kỳ endpoint nào — 2 test dưới đây pin lại
đúng phần mới nối dây, không test lại logic đồng bộ file thật (thuộc phạm vi github_sync_worker,
chưa có hạ tầng mock GitHub API trong repo test này).

Dùng chung fixture/pattern với test_knowledge_documents_project.py."""

import uuid

import pytest
from sqlalchemy import update

from src.model.enums import SyncStatus
from src.model.project import Project
from src.model.session import AsyncSessionLocal
from src.services import project_service


class _FakeGithubClient:
    """Stands in for the real `GithubClient` used to validate a PAT at connect-time — this
    suite runs against a real ASGI app/DB (see PM-test/conftest.py) but must not make real
    outbound calls to api.github.com just to pin the connect-repo wiring."""

    def __init__(self, token: str) -> None:
        self.token = token

    def get_branch_head_sha(self, repo: str, branch: str) -> str:
        return "abc123"


def _unique_key() -> str:
    return f"TEST{uuid.uuid4().hex[:8].upper()}"


async def _create_project(client, test_data, admin_id: int) -> int:
    response = await client.post(
        "/api/v1/projects/pm",
        json={"key": _unique_key(), "name": "GitHub Sync Test Project", "created_by_admin_id": admin_id},
    )
    assert response.status_code == 201
    project_id = response.json()["project_id"]
    test_data.project_ids.append(project_id)
    return project_id


@pytest.mark.asyncio
async def test_connect_github_repo_rejects_bad_format(client, test_data, admin_id):
    project_id = await _create_project(client, test_data, admin_id)

    response = await client.patch(
        f"/api/v1/knowledge-documents/pm/projects/{project_id}/github-repo",
        headers={"X-User-Id": str(admin_id)},
        json={"github_repo": "not-a-valid-repo"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_connect_github_repo_updates_project(client, test_data, admin_id, monkeypatch):
    monkeypatch.setattr(project_service, "GithubClient", _FakeGithubClient)
    project_id = await _create_project(client, test_data, admin_id)

    response = await client.patch(
        f"/api/v1/knowledge-documents/pm/projects/{project_id}/github-repo",
        headers={"X-User-Id": str(admin_id)},
        json={
            "github_repo": "octocat/Hello-World",
            "default_branch": "develop",
            "github_token": "ghp_test_token",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["github_repo"] == "octocat/Hello-World"

    async with AsyncSessionLocal() as db:
        project = await db.get(Project, project_id)
        assert project.default_branch == "develop"


@pytest.mark.asyncio
async def test_sync_now_fails_clearly_when_repo_not_configured(client, test_data, admin_id):
    """Project mới luôn có `github_repo="pending/<key>"` (chưa trỏ tới repo thật) — bấm "Đồng bộ
    ngay" lúc này phải báo lỗi rõ ràng (422), không rơi ra 500 trần (F-07 discipline)."""
    project_id = await _create_project(client, test_data, admin_id)

    response = await client.post(
        f"/api/v1/knowledge-documents/pm/projects/{project_id}/github-sync",
        headers={"X-User-Id": str(admin_id)},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_sync_now_rejects_when_already_syncing(client, test_data, admin_id):
    project_id = await _create_project(client, test_data, admin_id)
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Project).where(Project.project_id == project_id).values(sync_status=SyncStatus.SYNCING)
        )
        await db.commit()

    response = await client.post(
        f"/api/v1/knowledge-documents/pm/projects/{project_id}/github-sync",
        headers={"X-User-Id": str(admin_id)},
    )
    assert response.status_code == 409
