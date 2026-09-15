"""F-22: chat request/cost budget guard.

Rejects a request *before* retrieval/LLM are touched when the caller is over a
configured rate limit or daily usage/cost cap. This is deliberately separate from
`src.shared.ai.request_budget.RequestBudget`, which is a per-request *time* budget
(embedding/LLM stage deadlines) — this module is a request-count/cost policy, not a
latency one.

No new infrastructure: the rate limiter is an in-process fixed-window counter (module-
level singleton, mirrors `get_settings()`), and daily usage/cost is read from the
existing `llm_call_logs` table (reusing the `cost_estimate` column that
`chat_telemetry._row` now populates), not a new table or an external store.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.model.llm_call_log import LlmCallLog


class ChatBudgetExceededError(Exception):
    """Raised before retrieval/LLM when the caller is over a configured budget.

    `reason` is a stable short code (also used as the `LlmCallLog.error_code`), the
    exception message is the human-readable detail returned to the client.
    """

    def __init__(self, reason: str, detail: str) -> None:
        self.reason = reason
        super().__init__(detail)


@dataclass(frozen=True)
class ChatBudgetConfig:
    rate_limit_max_requests: int
    rate_limit_window_seconds: float
    daily_request_cap_per_user: int
    daily_cost_cap_usd_per_user: float
    daily_cost_cap_usd_per_project: float


class _RateLimiter:
    """In-process fixed-window limiter keyed by user id. No Redis, no shared state."""

    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clock = clock
        self._hits: dict[int, deque[float]] = {}

    def allow(self, key: int) -> bool:
        if self.max_requests <= 0:
            return True
        now = self._clock()
        hits = self._hits.setdefault(key, deque())
        cutoff = now - self.window_seconds
        while hits and hits[0] < cutoff:
            hits.popleft()
        if len(hits) >= self.max_requests:
            return False
        hits.append(now)
        return True


class ChatBudgetGuard:
    def __init__(
        self,
        config: ChatBudgetConfig,
        *,
        rate_limiter: _RateLimiter | None = None,
        # Naive UTC on purpose: `llm_call_logs.created_at` is TIMESTAMP WITHOUT TIME ZONE (the
        # naive-UTC convention this codebase uses everywhere), and asyncpg rejects comparing a
        # tz-aware parameter against it outright — every real request hit this before the fix.
        now: Callable[[], datetime] = lambda: datetime.now(UTC).replace(tzinfo=None),
    ) -> None:
        self.config = config
        self._rate_limiter = rate_limiter or _RateLimiter(
            config.rate_limit_max_requests, config.rate_limit_window_seconds
        )
        self._now = now

    async def check(self, session: AsyncSession, *, user_id: int, project_id: int | None) -> None:
        if not self._rate_limiter.allow(user_id):
            raise ChatBudgetExceededError(
                "rate_limit",
                "Too many chat requests in a short period. Please wait a moment and try again.",
            )

        config = self.config
        if config.daily_request_cap_per_user <= 0 and config.daily_cost_cap_usd_per_user <= 0.0:
            user_count, user_cost = 0, 0.0
        else:
            day_start = self._now().replace(hour=0, minute=0, second=0, microsecond=0)
            user_count, user_cost = await self._daily_usage(
                session, user_id=user_id, project_id=None, since=day_start
            )

            if 0 < config.daily_request_cap_per_user <= user_count:
                raise ChatBudgetExceededError(
                    "daily_request_cap",
                    "Daily chat request limit reached for this account. Please try again tomorrow.",
                )
            if 0.0 < config.daily_cost_cap_usd_per_user <= user_cost:
                raise ChatBudgetExceededError(
                    "daily_cost_cap",
                    "Daily chat usage cap reached for this account. Please try again tomorrow.",
                )

        if project_id is not None and config.daily_cost_cap_usd_per_project > 0.0:
            day_start = self._now().replace(hour=0, minute=0, second=0, microsecond=0)
            _project_count, project_cost = await self._daily_usage(
                session, user_id=None, project_id=project_id, since=day_start
            )
            if project_cost >= config.daily_cost_cap_usd_per_project:
                raise ChatBudgetExceededError(
                    "project_daily_cost_cap",
                    "Daily chat usage cap reached for this project. Please try again tomorrow.",
                )

    @staticmethod
    async def _daily_usage(
        session: AsyncSession,
        *,
        user_id: int | None,
        project_id: int | None,
        since: datetime,
    ) -> tuple[int, float]:
        """Count + summed cost of today's chat turns, scoped by user or by project.

        Summed in Python rather than SQL because `cost_estimate` is a legacy VARCHAR
        column (not numeric) — a portable `CAST`/`SUM` across SQLite (tests) and
        Postgres (prod) is more fragile than reading the small daily row set and
        parsing here.
        """
        query = select(LlmCallLog.cost_estimate).where(
            LlmCallLog.module == "chat",
            LlmCallLog.stage == "chat_request",
            LlmCallLog.created_at >= since,
        )
        if user_id is not None:
            query = query.where(LlmCallLog.user_id == user_id)
        if project_id is not None:
            query = query.where(LlmCallLog.project_id == project_id)
        rows = (await session.scalars(query)).all()
        cost_total = 0.0
        for value in rows:
            if not value:
                continue
            try:
                cost_total += float(value)
            except ValueError:
                continue
        return len(rows), cost_total


@lru_cache
def get_chat_budget_guard() -> ChatBudgetGuard:
    """Process-wide singleton: the in-process rate limiter must not reset per request."""
    settings = get_settings()
    return ChatBudgetGuard(
        ChatBudgetConfig(
            rate_limit_max_requests=settings.chat_rate_limit_max_requests,
            rate_limit_window_seconds=settings.chat_rate_limit_window_seconds,
            daily_request_cap_per_user=settings.chat_daily_request_cap_per_user,
            daily_cost_cap_usd_per_user=settings.chat_daily_cost_cap_usd_per_user,
            daily_cost_cap_usd_per_project=settings.chat_daily_cost_cap_usd_per_project,
        )
    )
