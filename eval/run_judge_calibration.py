"""Run the bounded F5 semantic-judge calibration subset with an independent judge model.

The chatbot stays on the repository's normal runtime configuration.  Only the semantic judge is
replaced with the requested provider/model/effort, so this is a calibration of the judge rather
than a model migration experiment. It deliberately selects 26 representative golden cases and
never enables stability repeats or the full suite.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from langchain_openai import ChatOpenAI

from eval.run_suite import RESULTS_DIR, run_live, score_run
from eval.shared.golden_schema import load_suite
from src.config import get_settings
from src.shared.ai.ports import ChatCompletion


CASE_IDS = (
    # Grounded factual, synthesis/cross-document, and false-refusal-sensitive answers.
    "F5V2-PRJ-001", "F5V2-PRJ-003", "F5V2-PRJ-005", "F5V2-PRJ-009", "F5V2-PRJ-021",
    "F5V2-POL-001", "F5V2-POL-010", "F5V2-POL-030", "F5V2-POL-045", "F5V2-POL-050",
    # Partial disclosure and intentionally unavailable facts.
    "F5V2-PRJ-022", "F5V2-PRJ-023", "F5V2-PRJ-024", "F5V2-PRJ-025",
    "F5V2-POL-015", "F5V2-POL-016", "F5V2-POL-018", "F5V2-POL-052",
    # General/strict switching, follow-up/topic state, language re-answer/persistence/BOTH.
    "F5V2-CNV-001", "F5V2-CNV-008", "F5V2-CNV-010", "F5V2-CNV-103", "F5V2-CNV-104",
    # The judge is not invoked here; these confirm deterministic safety remains authoritative.
    "F5V2-ADV-005", "F5V2-ADV-012", "F5V2-ADV-018",
)

JUDGE_MODEL = "gpt-5.6-luna"
JUDGE_REASONING_EFFORT = "medium"


class CalibrationJudgeCompletion:
    """Minimal completion port that records the requested judge-only model usage."""

    def __init__(self, provider: ChatOpenAI) -> None:
        self.provider = provider
        self.calls = 0
        self.usage: list[dict] = []

    async def complete(self, messages, budget, operation) -> ChatCompletion:
        self.calls += 1
        response = await self.provider.ainvoke(
            list(messages), reasoning_effort=JUDGE_REASONING_EFFORT
        )
        usage = getattr(response, "usage_metadata", {}) or {}
        self.usage.append(dict(usage))
        content = getattr(response, "content", None)
        if not isinstance(content, str):
            raise ValueError("judge returned non-text content")
        return ChatCompletion(content, getattr(response, "response_metadata", {}) or {}, usage)


def _usage_totals(records: list[dict]) -> dict:
    def total(*keys: str) -> int:
        return sum(int(record.get(key) or 0) for record in records for key in keys)

    return {
        "input_tokens": total("input_tokens", "prompt_tokens"),
        "output_tokens": total("output_tokens", "completion_tokens"),
        "total_tokens": total("total_tokens"),
        "cost": sum(float(record.get("cost") or 0.0) for record in records),
    }


async def main() -> Path:
    cases_by_id = {case.id: case for case in load_suite()}
    missing = [case_id for case_id in CASE_IDS if case_id not in cases_by_id]
    if missing:
        raise ValueError(f"calibration cases missing from active suite: {missing}")
    selected = [cases_by_id[case_id] for case_id in CASE_IDS]

    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for the requested calibration judge")
    judge = CalibrationJudgeCompletion(
        ChatOpenAI(
            model=JUDGE_MODEL,
            api_key=settings.openai_api_key,
            temperature=0,
            timeout=60,
            max_retries=1,
        )
    )
    live = await run_live(
        selected,
        repeats=1,
        judge_enabled=True,
        stability_cases=0,
        judge_completion=judge,
    )
    outcomes = live.pop("_outcome_objects")
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run_mode": "judge_calibration",
        "selection": list(CASE_IDS),
        "judge": {
            "model": JUDGE_MODEL,
            "reasoning_effort": JUDGE_REASONING_EFFORT,
            "calls": judge.calls,
            "usage": _usage_totals(judge.usage),
            "usage_records": judge.usage,
        },
        "score": score_run(outcomes, live["stability"], live["telemetry"]),
        "outcomes": live["outcomes"],
        "telemetry": live["telemetry"],
        "skipped": live["skipped"],
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"judge_calibration_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"Wrote {path}")
    print(f"Judge calls: {judge.calls}; usage: {payload['judge']['usage']}")
    return path


if __name__ == "__main__":
    asyncio.run(main())
