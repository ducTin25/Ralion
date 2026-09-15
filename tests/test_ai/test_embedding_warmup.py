"""Target design item 1: chat embedding warm-up must never crash or block on a failed ping."""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import pytest

from src.infrastructure.scheduling.embedding_warmup import (
    _warmup_once,
    on_demand_embedding_warmup_status,
    trigger_on_demand_embedding_warmup,
)
from src.shared.ai.external_failures import ExternalFailureCode, ExternalServiceFailure


class _OkEmbedder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    async def embed_query(self, text: str, budget) -> list[float]:
        self.calls.append((text, budget))
        return [0.0] * 1024


class _ColdStartEmbedder:
    """Simulates a Modal cold start timing out even inside the warm-up's own generous budget."""

    async def embed_query(self, text: str, budget) -> list[float]:
        raise ExternalServiceFailure("embedding", ExternalFailureCode.TIMEOUT, False, timeout_scope="attempt")


class _BlockingEmbedder:
    def __init__(self) -> None:
        self.calls = 0
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def embed_query(self, text: str, budget) -> list[float]:
        self.calls += 1
        self.started.set()
        await self.release.wait()
        return [0.0] * 1024


@pytest.mark.asyncio
async def test_warmup_pings_the_embedder() -> None:
    embedder = _OkEmbedder()

    assert await _warmup_once(embedder)

    assert len(embedder.calls) == 1
    text, budget = embedder.calls[0]
    assert text
    assert budget.remaining_embedding() > 0


@pytest.mark.asyncio
async def test_warmup_failure_never_raises() -> None:
    """A cold endpoint (or any other transient failure) must never crash the loop -- the next
    real chat request still degrades safely through the existing system_error fallback."""
    assert not await _warmup_once(_ColdStartEmbedder())


@pytest.mark.asyncio
async def test_on_demand_warmup_coalesces_concurrent_page_entries() -> None:
    embedder = _BlockingEmbedder()
    state = SimpleNamespace(
        on_demand_embedding_warmup_task=None,
        on_demand_embedding_warmup_ready_until=0.0,
    )

    assert trigger_on_demand_embedding_warmup(state, embedder, 60.0)
    await embedder.started.wait()
    assert on_demand_embedding_warmup_status(state) == "in_progress"
    assert not trigger_on_demand_embedding_warmup(state, embedder, 60.0)
    assert embedder.calls == 1

    embedder.release.set()
    await state.on_demand_embedding_warmup_task
    assert on_demand_embedding_warmup_status(state) == "ready"
    assert trigger_on_demand_embedding_warmup(state, embedder, 60.0)
    await state.on_demand_embedding_warmup_task
    assert embedder.calls == 2


def test_on_demand_readiness_expires_before_modal_scales_down() -> None:
    state = SimpleNamespace(
        on_demand_embedding_warmup_task=None,
        on_demand_embedding_warmup_ready_until=time.monotonic() - 1.0,
    )

    assert on_demand_embedding_warmup_status(state) == "unavailable"
