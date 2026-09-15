from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from src.api.dependencies import get_session_user
from src.main import app


class _BlockingEmbedder:
    def __init__(self) -> None:
        self.calls = 0
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def embed_query(self, _text, _budget) -> list[float]:
        self.calls += 1
        self.started.set()
        await self.release.wait()
        return [0.0] * 1024


@pytest.mark.asyncio
async def test_warmup_requires_a_signed_session(client) -> None:
    response = await client.post("/api/v1/chat/warmup", headers={"X-User-Id": "7"})
    status_response = await client.get("/api/v1/chat/warmup", headers={"X-User-Id": "7"})

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "NO_SESSION"
    assert status_response.status_code == 401


@pytest.mark.asyncio
async def test_warmup_returns_immediately_and_coalesces_concurrent_requests(client) -> None:
    missing = object()
    previous_resources = getattr(app.state, "ai_resources", missing)
    previous_task = getattr(app.state, "on_demand_embedding_warmup_task", missing)
    previous_ready_until = getattr(app.state, "on_demand_embedding_warmup_ready_until", missing)
    embedder = _BlockingEmbedder()
    app.dependency_overrides[get_session_user] = lambda: SimpleNamespace(user_id=7)
    app.state.ai_resources = SimpleNamespace(warmup_embedding=embedder)
    app.state.on_demand_embedding_warmup_task = None
    app.state.on_demand_embedding_warmup_ready_until = 0.0
    try:
        first = await client.post("/api/v1/chat/warmup")
        second = await client.post("/api/v1/chat/warmup")

        assert first.status_code == 202
        assert first.json() == {"status": "started"}
        assert second.status_code == 202
        assert second.json() == {"status": "in_progress"}
        await embedder.started.wait()
        assert embedder.calls == 1

        warming = await client.get("/api/v1/chat/warmup")
        assert warming.json() == {"status": "in_progress"}

        embedder.release.set()
        await app.state.on_demand_embedding_warmup_task
        ready = await client.get("/api/v1/chat/warmup")
        refreshed = await client.post("/api/v1/chat/warmup")
        assert ready.json() == {"status": "ready"}
        assert refreshed.json() == {"status": "ready"}
    finally:
        embedder.release.set()
        task = getattr(app.state, "on_demand_embedding_warmup_task", None)
        if task is not None:
            await task
        app.dependency_overrides.pop(get_session_user, None)
        if previous_resources is missing:
            delattr(app.state, "ai_resources")
        else:
            app.state.ai_resources = previous_resources
        if previous_task is missing:
            delattr(app.state, "on_demand_embedding_warmup_task")
        else:
            app.state.on_demand_embedding_warmup_task = previous_task
        if previous_ready_until is missing:
            delattr(app.state, "on_demand_embedding_warmup_ready_until")
        else:
            app.state.on_demand_embedding_warmup_ready_until = previous_ready_until
