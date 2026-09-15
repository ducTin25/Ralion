import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks, HTTPException

from src.model.enums import SyncStatus

knowledge_document_router = importlib.import_module("src.api.routers.knowledge_document_router")


@pytest.mark.asyncio
async def test_github_sync_hides_internal_database_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    project = SimpleNamespace(
        project_id=1,
        sync_status=SyncStatus.NOT_STARTED,
        github_repo="owner/repo",
        default_branch="main",
    )
    monkeypatch.setattr(
        knowledge_document_router.project_service,
        "get_project",
        AsyncMock(return_value=project),
    )
    monkeypatch.setattr(
        knowledge_document_router.github_sync_worker,
        "ensure_repo_target_configured",
        lambda _project: None,
    )
    monkeypatch.setattr(
        knowledge_document_router.github_credential_provider,
        "get_token",
        AsyncMock(return_value="token"),
    )
    db = AsyncMock()
    db.execute.return_value.rowcount = 1
    db.commit.side_effect = Exception("raw database invariant details")

    with pytest.raises(HTTPException) as captured:
        await knowledge_document_router.sync_project_from_github(
            project_id=1,
            background_tasks=BackgroundTasks(),
            _membership=None,
            db=db,
            embedder=object(),
        )

    assert captured.value.status_code == 502
    assert captured.value.detail == (
        "Không thể đồng bộ tài liệu từ GitHub. Vui lòng thử lại hoặc liên hệ quản trị viên."
    )
    assert "database" not in captured.value.detail.lower()
