"""Read latency, token, cost and stage-timing telemetry back out of `llm_call_logs`.

`EVAL_GUIDE.md §10/§11` needs per-turn latency and token/cost data, and §17 Step 6 asks that it
be correlated with quality results through the same trace id. Ralion already records all of it:
`ChatService` writes one or more `llm_call_logs` rows per turn carrying `prompt_tokens`,
`completion_tokens`, `cost_estimate`, `total_latency_ms`, `generation_latency_ms` and a
`stage_timings_ms` map, keyed by the `trace_id` that `ChatResult` returns to the caller.

So this module measures the real system rather than wrapping a stopwatch around it: a client-side
timer would include eval-harness overhead and could not attribute time to the embed/dense/bm25/
gate/generate/verify stages. It also means NOTHING here changes production behavior -- it is a
read-only query against rows the application writes anyway (CLAUDE.md §7: one AI log table, no
parallel logging system).

Rows are written by a queued sink, so a row can land shortly AFTER `ask()` returns. `fetch` takes
a `settle_seconds` grace period and retries once rather than silently reporting zero tokens.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Iterable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_QUERY = text(
    """
    SELECT trace_id, module, stage, outcome, provider, model,
           prompt_tokens, completion_tokens, cost_estimate,
           latency_ms, total_latency_ms, generation_latency_ms,
           stage_timings_ms, retry_count, repair_retry_count, provider_retry_count,
           embedding_retry_count, error_stage, error_code,
           candidate_count, accepted_count, retrieval_attempt_count,
           selected_chunk_ids, retrieval_scores, decision_details,
           fallback_reason, gate_decision, validator_outcome
    FROM llm_call_logs
    WHERE trace_id = ANY(:trace_ids)
    ORDER BY created_at
    """
)


@dataclass
class TurnTelemetry:
    """Everything `llm_call_logs` recorded for one chat turn (possibly several rows)."""

    trace_id: str
    rows: list[dict] = field(default_factory=list)

    @property
    def llm_calls(self) -> int:
        return len(self.rows)

    @property
    def prompt_tokens(self) -> int:
        return sum(int(row.get("prompt_tokens") or 0) for row in self.rows)

    @property
    def completion_tokens(self) -> int:
        return sum(int(row.get("completion_tokens") or 0) for row in self.rows)

    @property
    def cost_estimate(self) -> float:
        return sum(float(row.get("cost_estimate") or 0.0) for row in self.rows)

    @property
    def total_latency_ms(self) -> float | None:
        """End-to-end turn latency.

        `total_latency_ms` is a per-TURN value repeated on each row of that turn, so it is
        max()'d rather than summed -- summing would multiply the turn's latency by its LLM-call
        count and silently inflate every percentile.
        """
        values = [float(row["total_latency_ms"]) for row in self.rows if row.get("total_latency_ms")]
        return max(values) if values else None

    @property
    def generation_latency_ms(self) -> float | None:
        values = [
            float(row["generation_latency_ms"]) for row in self.rows if row.get("generation_latency_ms")
        ]
        return sum(values) if values else None

    @property
    def retries(self) -> int:
        return sum(
            int(row.get(name) or 0)
            for row in self.rows
            for name in ("retry_count", "repair_retry_count", "provider_retry_count", "embedding_retry_count")
        )

    @property
    def had_error(self) -> bool:
        return any(row.get("error_stage") or row.get("error_code") for row in self.rows)

    @property
    def modules(self) -> set[str]:
        return {str(row.get("module")) for row in self.rows if row.get("module")}

    def stage_timings(self) -> dict[str, float]:
        """Merged stage timings across the turn's rows, summed per stage name."""
        merged: dict[str, float] = {}
        for row in self.rows:
            timings = row.get("stage_timings_ms") or {}
            if isinstance(timings, str):
                continue  # a driver that returned JSON as text; not worth guessing at parse time
            for stage, value in timings.items():
                try:
                    merged[stage] = merged.get(stage, 0.0) + float(value)
                except (TypeError, ValueError):
                    continue
        return merged

    def selected_chunk_ids(self) -> list[int]:
        for row in reversed(self.rows):
            chunks = row.get("selected_chunk_ids")
            if chunks:
                return [int(chunk) for chunk in chunks]
        return []


async def fetch(
    session: AsyncSession, trace_ids: Iterable[str], *, settle_seconds: float = 1.5
) -> dict[str, TurnTelemetry]:
    """Load telemetry for the given trace ids, keyed by trace id.

    Missing trace ids simply do not appear in the result: telemetry is best-effort observability,
    and a turn whose row has not landed must not fail the quality evaluation of that turn.
    """
    ids = [str(trace_id) for trace_id in trace_ids if trace_id]
    if not ids:
        return {}

    async def _query() -> dict[str, TurnTelemetry]:
        result = await session.execute(_QUERY, {"trace_ids": ids})
        found: dict[str, TurnTelemetry] = {}
        for row in result.mappings():
            trace_id = str(row["trace_id"])
            found.setdefault(trace_id, TurnTelemetry(trace_id)).rows.append(dict(row))
        return found

    telemetry = await _query()
    if len(telemetry) < len(ids) and settle_seconds > 0:
        # The queued sink may not have flushed yet. One grace period, then take what is there.
        await asyncio.sleep(settle_seconds)
        await session.rollback()  # release the snapshot so the retry sees newly committed rows
        telemetry = await _query()
    return telemetry


def aggregate(telemetry: dict[str, TurnTelemetry]) -> dict[str, Any]:
    """Roll several turns' telemetry up into the shape the scorecard reports."""
    latencies = [t.total_latency_ms for t in telemetry.values() if t.total_latency_ms is not None]
    stage_totals: dict[str, list[float]] = {}
    for turn in telemetry.values():
        for stage, value in turn.stage_timings().items():
            stage_totals.setdefault(stage, []).append(value)
    return {
        "turns_with_telemetry": len(telemetry),
        "llm_calls": sum(t.llm_calls for t in telemetry.values()),
        "prompt_tokens": sum(t.prompt_tokens for t in telemetry.values()),
        "completion_tokens": sum(t.completion_tokens for t in telemetry.values()),
        "cost_estimate": sum(t.cost_estimate for t in telemetry.values()),
        "retries": sum(t.retries for t in telemetry.values()),
        "turns_with_error": sum(1 for t in telemetry.values() if t.had_error),
        "latencies_ms": latencies,
        "stage_mean_ms": {
            stage: sum(values) / len(values) for stage, values in sorted(stage_totals.items())
        },
    }
