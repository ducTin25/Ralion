"""The LLM warm-up must touch the shared pool and never make startup depend on the ping."""

from __future__ import annotations

import httpx
import pytest

from src.infrastructure.scheduling.llm_warmup import LlmEndpoint, _warmup_once


@pytest.mark.asyncio
async def test_warmup_gets_the_provider_base_url_through_the_supplied_client() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(404, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await _warmup_once(LlmEndpoint(client, "https://provider.test/v1"))

    assert [str(request.url) for request in requests] == ["https://provider.test/v1"]


@pytest.mark.asyncio
async def test_warmup_transport_failure_is_swallowed() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("cold connection", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert not await _warmup_once(LlmEndpoint(client, "https://provider.test/v1"))
