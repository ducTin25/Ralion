from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Literal


class BudgetExhausted(TimeoutError):  # noqa: N818 - internal budget signal, not a public error
    def __init__(self, scope: Literal["stage", "overall"]) -> None:
        self.scope = scope
        super().__init__(f"{scope} budget exhausted")


@dataclass(frozen=True)
class RequestBudgetConfig:
    overall_seconds: float
    embedding_seconds: float
    llm_seconds: float
    persistence_reserve_seconds: float = 0.0

    def start(self) -> RequestBudget:
        return RequestBudget(
            self.overall_seconds,
            self.embedding_seconds,
            self.llm_seconds,
            self.persistence_reserve_seconds,
        )


@dataclass
class RequestBudget:
    overall_seconds: float
    embedding_seconds: float
    llm_seconds: float
    persistence_reserve_seconds: float = 0.0
    clock: Callable[[], float] = time.monotonic
    _started: float = field(init=False)
    _embedding_spent: float = field(default=0.0, init=False)
    _llm_spent: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        self._started = self.clock()

    def remaining_total(self) -> float:
        return max(0.0, self.overall_seconds - (self.clock() - self._started) - self.persistence_reserve_seconds)

    def remaining_embedding(self) -> float:
        return max(0.0, min(self.embedding_seconds - self._embedding_spent, self.remaining_total()))

    def remaining_llm(self) -> float:
        return max(0.0, min(self.llm_seconds - self._llm_spent, self.remaining_total()))

    def remaining(self, stage: Literal["embedding", "llm"]) -> float:
        return self.remaining_embedding() if stage == "embedding" else self.remaining_llm()

    def charge(self, stage: Literal["embedding", "llm"], started: float) -> None:
        elapsed = max(0.0, self.clock() - started)
        if stage == "embedding":
            self._embedding_spent += elapsed
        else:
            self._llm_spent += elapsed

    @contextmanager
    def concurrent(self, stage: Literal["embedding", "llm"]) -> Iterator[None]:
        """Charge a block of CONCURRENT calls once, by the block's wall time.

        `charge()` adds each call's own elapsed time, which is right for sequential calls and
        wrong for parallel ones: two 4s calls running together consume 4s of the user's wait but
        would record 8s of `_llm_spent`, so the budget would shrink at twice the real rate and
        starve whatever ran next. That is the same starvation bug that produced trace 72e4e5ed,
        arriving by a different route -- so parallelising without this would have paid for the
        latency win with a new correctness bug.

        Restores the stage's spend to `before + wall_elapsed`, discarding whatever the individual
        calls charged inside. Deliberately an assignment rather than an adjustment: the calls
        inside may each have charged, retried, or failed, and the only figure that is true of all
        of them together is how long the block actually took.
        """
        before = self._embedding_spent if stage == "embedding" else self._llm_spent
        started = self.clock()
        try:
            yield
        finally:
            elapsed = max(0.0, self.clock() - started)
            if stage == "embedding":
                self._embedding_spent = before + elapsed
            else:
                self._llm_spent = before + elapsed

    def require(self, stage: Literal["embedding", "llm"]) -> float:
        if self.remaining_total() <= 0:
            raise BudgetExhausted("overall")
        remaining = self.remaining(stage)
        if remaining <= 0:
            raise BudgetExhausted("stage")
        return remaining
