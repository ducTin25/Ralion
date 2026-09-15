from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_readiness_checks_database(client, monkeypatch):
    check_database = AsyncMock()
    monkeypatch.setattr("src.main.check_database", check_database)

    response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "dependencies": {"database": "ok"}}
    check_database.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_readiness_reports_database_failure(client, monkeypatch):
    monkeypatch.setattr(
        "src.main.check_database",
        AsyncMock(side_effect=RuntimeError("connection failed")),
    )

    response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}


@pytest.mark.asyncio
async def test_rag_readiness_reports_configured_corpus(client, monkeypatch):
    check_rag = AsyncMock(return_value=192)
    monkeypatch.setattr("src.main.check_rag", check_rag)

    response = await client.get("/ready/rag")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "dependencies": {
            "database": "ok",
            "embedding": "configured",
            "active_chunks": 192,
        },
    }
    check_rag.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_rag_readiness_reports_failure(client, monkeypatch):
    monkeypatch.setattr(
        "src.main.check_rag",
        AsyncMock(side_effect=RuntimeError("embedding unavailable")),
    )

    response = await client.get("/ready/rag")

    assert response.status_code == 503
    assert response.json() == {"detail": "rag unavailable"}
