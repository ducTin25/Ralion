"""Fail-open embedding warm-up for periodic and user-triggered policies.

Modal's BGE-M3 endpoint scales to zero when idle; the first request after that pays a ~41s
cold start (measured). For chat, that exhausts the interactive retry budget and falls over to
the generic `system_error` apology. Non-chat callers (PM/HR upload and GitHub sync ingestion)
can receive `ExternalServiceFailure` directly. This loop calls the same `embed_query()` path
as retrieval to keep a container warm for every embedding-dependent use case. The periodic
loop is optional; the on-demand trigger starts while an authenticated user opens Chat or begins
repository scanning.

Same `asyncio.create_task`-in-`lifespan()` shape as `convention_discovery_scheduler_loop` -- no
new infrastructure, no new abstraction. A ping failing here is never a caller-facing error: the
loop only logs and keeps going, and a genuinely cold endpoint still fails safely through the
existing `ExternalServiceFailure` -> `system_error` fallback path on the next real chat request
(non-chat callers still need their own handling -- see the missing `/upload` handler noted in
CHANGE_LOG.md).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Protocol

from src.config import Settings
from src.shared.ai.request_budget import RequestBudget

logger = logging.getLogger(__name__)

_WARMUP_TEXT = "warmup"
# Modal retains the L4 for 120 seconds. Report it as ready for a slightly shorter period so the
# UI never promises readiness after the remote container may already have scaled to zero.
_ON_DEMAND_READY_TTL_SECONDS = 90.0


class _WarmableEmbedder(Protocol):
    async def embed_query(self, text: str, budget: RequestBudget) -> list[float]: ...


async def _warmup_once(embedder: _WarmableEmbedder, timeout_seconds: float = 60.0) -> bool:
    started = time.monotonic()
    try:
        await embedder.embed_query(
            _WARMUP_TEXT, RequestBudget(timeout_seconds, timeout_seconds, 0.0)
        )
    except Exception as exc:  # noqa: BLE001 - warm-up must never crash the loop or app startup
        logger.warning(
            json.dumps(
                {
                    "event": "chat_embedding_warmup_failed",
                    "duration_ms": round((time.monotonic() - started) * 1000),
                    "error_type": type(exc).__name__,
                    "failure_code": getattr(getattr(exc, "code", None), "value", None),
                },
                sort_keys=True,
            )
        )
        return False
    logger.info(
        '{"event":"chat_embedding_warmup_ok","duration_ms":%d}',
        round((time.monotonic() - started) * 1000),
    )
    return True


async def _run_on_demand_warmup(
    app_state: object,
    embedder: _WarmableEmbedder,
    timeout_seconds: float,
) -> bool:
    succeeded = await _warmup_once(embedder, timeout_seconds)
    setattr(
        app_state,
        "on_demand_embedding_warmup_ready_until",
        time.monotonic() + _ON_DEMAND_READY_TTL_SECONDS if succeeded else 0.0,
    )
    return succeeded


def on_demand_embedding_warmup_status(app_state: object) -> str:
    """Return a credential-free status suitable for the authenticated Chat UI."""
    ready_until = getattr(app_state, "on_demand_embedding_warmup_ready_until", 0.0)
    if time.monotonic() < ready_until:
        return "ready"
    current_task = getattr(app_state, "on_demand_embedding_warmup_task", None)
    if current_task is not None and not current_task.done():
        return "in_progress"
    return "unavailable"


def trigger_on_demand_embedding_warmup(
    app_state: object,
    embedder: _WarmableEmbedder,
    timeout_seconds: float,
) -> bool:
    """Start one fail-open warm-up task, coalescing concurrent page-entry requests."""
    current_task = getattr(app_state, "on_demand_embedding_warmup_task", None)
    if current_task is not None and not current_task.done():
        return False
    setattr(
        app_state,
        "on_demand_embedding_warmup_task",
        asyncio.create_task(
            _run_on_demand_warmup(app_state, embedder, timeout_seconds),
            name="on-demand-embedding-warmup",
        ),
    )
    return True


async def embedding_warmup_loop(settings: Settings, embedder: _WarmableEmbedder) -> None:
    """Runs until cancelled (src/main.py cancels this task on shutdown).

    Pings immediately on start, before the first sleep: other endpoints already serve traffic
    while this runs (it is a background task, not part of app startup), and chat alone degrades
    gracefully to `system_error` if a real request lands before the first ping completes.
    """
    while True:
        await _warmup_once(embedder, settings.chat_embedding_warmup_timeout_seconds)
        await asyncio.sleep(settings.chat_embedding_warmup_interval_seconds)
