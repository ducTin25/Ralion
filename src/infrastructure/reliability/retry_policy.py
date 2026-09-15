from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    connect_timeout_seconds: float
    read_timeout_seconds: float
    backoff_initial_seconds: float
    backoff_multiplier: float = 2.0
    backoff_max_seconds: float = 1.0

    def backoff(self, failed_attempt: int) -> float:
        return min(
            self.backoff_max_seconds,
            self.backoff_initial_seconds * self.backoff_multiplier ** max(0, failed_attempt - 1),
        )
