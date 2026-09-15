from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from typing import Literal, TypeVar

from src.infrastructure.reliability.retry_policy import RetryPolicy
from src.shared.ai.external_failures import ExternalFailureCode, ExternalServiceFailure
from src.shared.ai.request_budget import BudgetExhausted, RequestBudget

T = TypeVar("T")


class RetryExecutor:
    def __init__(self, *, sleep=asyncio.sleep, clock=time.monotonic, jitter=random.uniform) -> None:
        self._sleep = sleep
        self._clock = clock
        self._jitter = jitter

    async def run(
        self,
        operation: Callable[[float, float], Awaitable[T]],
        *,
        service: Literal["embedding", "llm"],
        stage: Literal["embedding", "llm"],
        budget: RequestBudget,
        policy: RetryPolicy,
    ) -> T:
        started = self._clock()
        try:
            for attempt in range(1, policy.max_attempts + 1):
                try:
                    remaining = budget.require(stage)
                except BudgetExhausted as exc:
                    raise ExternalServiceFailure(
                        service, ExternalFailureCode.TIMEOUT, False, attempt - 1,
                        "overall" if exc.scope == "overall" else "stage",
                    ) from exc
                try:
                    async with asyncio.timeout(remaining):
                        return await operation(
                            min(policy.connect_timeout_seconds, remaining),
                            min(policy.read_timeout_seconds, remaining),
                        )
                except asyncio.CancelledError:
                    raise
                except TimeoutError as exc:
                    scope = "overall" if budget.remaining_total() <= 0 else "stage"
                    raise ExternalServiceFailure(
                        service, ExternalFailureCode.TIMEOUT, False, attempt, scope
                    ) from exc
                except ExternalServiceFailure as failure:
                    failure.attempts = attempt
                    if not failure.retryable or attempt >= policy.max_attempts:
                        raise
                    delay = failure.retry_after_seconds
                    if delay is None:
                        delay = self._jitter(0.0, policy.backoff(attempt))
                    if delay >= budget.remaining(stage) or delay >= budget.remaining_total():
                        raise
                    await self._sleep(delay)
            raise AssertionError("unreachable")
        finally:
            budget.charge(stage, started)
