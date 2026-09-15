"""LLM connection warm-up (RC-1: interpreter cold start).

Same failure shape as `embedding_warmup.py`, one layer over: with an empty httpx pool the first
chat turn pays a TCP+TLS handshake to the LLM provider *inside* the stage timeout that wraps the
call. For the TurnInterpreter (`turn_interpreter.timeout_seconds`) that is fatal in a way a slow
answer is not: the interpreter returns a degraded verdict and the dispatcher safely stops the turn
before retrieval, losing control extraction, follow-up resolution and knowledge-policy selection
for that turn. Measured evidence that this is a cold-start effect and
not a slow model: interpreter `TimeoutError` occurs 96x at turn_index 0 and 8x at turn_index 1
against 2 occurrences across all later turns, and `scope_and_interpret` averages 2748/2716ms at
turns 0-1 versus 1141-1589ms from turn 2 onward.

Deliberately NOT a completion request:

* it mints no tokens, so it costs nothing and stays outside `llm_call_logs` (invariant 10 governs
  LLM calls; this is an HTTP GET that never reaches a model),
* the handshake is the entire cost being removed -- once a pooled connection exists, every
  subsequent chat turn reuses it for the whole `chat_http_keepalive_expiry_seconds` window.

Any HTTP status counts as success: a 401/404 from the provider's base URL still proves the
connection was established, which is the only thing this loop is for. Only transport errors are
failures, and they are logged and swallowed -- a cold provider still degrades safely through the
existing fallback path on the next real request.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass

import httpx

from src.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LlmEndpoint:
    """The pooled client and base URL the chat LLM adapter actually uses.

    Held as a pair so the warm-up shares the *same* `httpx.AsyncClient` as generation; warming a
    separate client would fill a pool nobody reads from.
    """

    client: httpx.AsyncClient
    base_url: str


async def _warmup_once(endpoint: LlmEndpoint, timeout_seconds: float = 10.0) -> bool:
    started = time.monotonic()
    try:
        response = await endpoint.client.get(endpoint.base_url, timeout=timeout_seconds)
    except Exception as exc:  # noqa: BLE001 - warm-up must never crash the loop or app startup
        logger.warning(
            json.dumps(
                {
                    "event": "chat_llm_warmup_failed",
                    "duration_ms": round((time.monotonic() - started) * 1000),
                    "error_type": type(exc).__name__,
                },
                sort_keys=True,
            )
        )
        return False
    logger.info(
        json.dumps(
            {
                "event": "chat_llm_warmup_ok",
                "duration_ms": round((time.monotonic() - started) * 1000),
                "status_code": response.status_code,
            },
            sort_keys=True,
        )
    )
    return True


async def llm_warmup_loop(settings: Settings, endpoint: LlmEndpoint) -> None:
    """Runs until cancelled (src/main.py cancels this task on shutdown).

    Pings immediately on start, before the first sleep, so the first real chat turn after a deploy
    already finds a pooled connection -- that first turn is exactly the one the measurements show
    timing out. The interval must stay below `chat_http_keepalive_expiry_seconds` or the pool drops
    the connection between pings and the warm-up achieves nothing.
    """
    while True:
        await _warmup_once(endpoint, settings.chat_llm_warmup_timeout_seconds)
        await asyncio.sleep(settings.chat_llm_warmup_interval_seconds)
