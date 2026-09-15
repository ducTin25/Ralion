"""Vendor-neutral, privacy-safe telemetry primitives.

Business/application code may depend on this module.  Concrete logging, database
and tracing exporters belong to ``src.infrastructure.observability``.
"""

from __future__ import annotations

import contextvars
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

SafeValue = str | int | float | bool | None | list[int] | dict[str, Any]


@dataclass(frozen=True)
class StageSpan:
    name: str
    duration_ms: float
    start_offset_ms: float = 0.0
    attributes: dict[str, SafeValue] = field(default_factory=dict)


@dataclass(frozen=True)
class TelemetrySnapshot:
    trace_id: str
    started_at: datetime
    completed_at: datetime
    total_latency_ms: int
    stage_timings_ms: dict[str, float]
    spans: tuple[StageSpan, ...]
    attributes: dict[str, SafeValue]


class TelemetrySink(Protocol):
    async def submit(self, snapshot: TelemetrySnapshot) -> None: ...


class NullTelemetrySink:
    async def submit(self, snapshot: TelemetrySnapshot) -> None:
        del snapshot


class TraceRecorder:
    """One chat-turn trace. It stores measurements only, never business payloads."""

    def __init__(self, trace_id: str) -> None:
        self.trace_id = trace_id
        self._started_ns = time.monotonic_ns()
        self._started_at = datetime.now(UTC)
        self._spans: list[StageSpan] = []
        self._attributes: dict[str, SafeValue] = {}
        self._attempts: dict[str, int] = {}

    def annotate(self, **attributes: SafeValue) -> None:
        for key, value in attributes.items():
            if value is None:
                continue
            existing = self._attributes.get(key)
            if isinstance(existing, dict) and isinstance(value, dict):
                self._attributes[key] = {**existing, **value}
            else:
                self._attributes[key] = value

    def next_attempt(self, operation: str) -> int:
        attempt = self._attempts.get(operation, 0) + 1
        self._attempts[operation] = attempt
        return attempt

    def has_attribute(self, name: str) -> bool:
        return name in self._attributes

    def attribute(self, name: str) -> SafeValue | None:
        """Read back what was annotated. Exists so a caller can put a value it already recorded
        onto its own return type without recomputing it -- two sources for one fact drift."""
        return self._attributes.get(name)

    def increment(self, name: str, amount: int | None) -> None:
        if amount is not None:
            self._attributes[name] = int(self._attributes.get(name, 0)) + int(amount)

    def record_duration(
        self,
        name: str,
        duration_ms: float,
        *,
        start_offset_ms: float | None = None,
        **attributes: SafeValue,
    ) -> None:
        if start_offset_ms is None:
            elapsed_ms = (time.monotonic_ns() - self._started_ns) / 1_000_000
            start_offset_ms = max(0.0, elapsed_ms - duration_ms)
        self._spans.append(
            StageSpan(
                name=name,
                duration_ms=max(0.0, duration_ms),
                start_offset_ms=max(0.0, start_offset_ms),
                attributes={key: value for key, value in attributes.items() if value is not None},
            )
        )

    @contextmanager
    def span(self, name: str, **attributes: SafeValue) -> Iterator[None]:
        started = time.monotonic_ns()
        start_offset_ms = (started - self._started_ns) / 1_000_000
        try:
            yield
        except BaseException as exc:
            attributes.setdefault("status", "error")
            attributes.setdefault("error_code", type(exc).__name__)
            raise
        finally:
            self.record_duration(
                name,
                (time.monotonic_ns() - started) / 1_000_000,
                start_offset_ms=start_offset_ms,
                **attributes,
            )

    @asynccontextmanager
    async def async_span(self, name: str, **attributes: SafeValue) -> AsyncIterator[None]:
        with self.span(name, **attributes):
            yield

    def snapshot(self) -> TelemetrySnapshot:
        timings: dict[str, float] = {}
        for item in self._spans:
            timings[item.name] = round(timings.get(item.name, 0.0) + item.duration_ms, 3)
        return TelemetrySnapshot(
            trace_id=self.trace_id,
            started_at=self._started_at,
            completed_at=datetime.now(UTC),
            total_latency_ms=max(0, int((time.monotonic_ns() - self._started_ns) / 1_000_000)),
            stage_timings_ms=timings,
            spans=tuple(self._spans),
            attributes=dict(self._attributes),
        )


_CURRENT_TRACE: contextvars.ContextVar[TraceRecorder | None] = contextvars.ContextVar(
    "chat_telemetry_trace", default=None
)


@contextmanager
def bind_trace(trace: TraceRecorder) -> Iterator[TraceRecorder]:
    token = _CURRENT_TRACE.set(trace)
    try:
        yield trace
    finally:
        _CURRENT_TRACE.reset(token)


def current_trace() -> TraceRecorder | None:
    return _CURRENT_TRACE.get()


@contextmanager
def telemetry_span(name: str, **attributes: SafeValue) -> Iterator[None]:
    trace = current_trace()
    if trace is None:
        yield
        return
    with trace.span(name, **attributes):
        yield


@asynccontextmanager
async def telemetry_async_span(name: str, **attributes: SafeValue) -> AsyncIterator[None]:
    with telemetry_span(name, **attributes):
        yield


def record_duration(name: str, started_ns: int, **attributes: SafeValue) -> None:
    trace = current_trace()
    if trace is not None:
        trace.record_duration(name, (time.monotonic_ns() - started_ns) / 1_000_000, **attributes)
