"""LLM safety/behavior guardrail harness for F5 chat (project_knowledge domain).

Terminology note (CLAUDE.md Phase 9 intro): "guardrail" here means LLM safety/behavior check,
NOT the F6 >=2-evidence data-quality gate (which F6_RULE_MINING_PLAN.md calls "guardrail" in an
unrelated sense) - see rule_mining/guardrails/harness.py for that one, kept in a clearly
separate file/directory so the two never get confused by name alone.

Default mode is --dry-run (structure-only, no LLM/DB call). --live sends `user_message` through
the real `ChatService.ask()` (`eval/shared/live_chat.py`) and judges the resulting answer against
`expected_behavior` with a single-prompt LLM judge (`eval/shared/llm_judge.py`) — see that
module's docstring for what it is and is not (a pragmatic first cut, not a calibrated judge).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from eval.shared.report_format import CaseResult, build_report, print_summary, write_report  # noqa: E402

DATASET_PATH = Path(__file__).resolve().parent / "test_cases.jsonl"
REPORT_PATH = Path(__file__).resolve().parent / "report.json"

REQUIRED_FIELDS = ("case_id", "user_message", "violation_type", "expected_behavior")
VIOLATION_TYPES = {"scope_creep", "citation_bypass", "role_confusion", "pii_leak_attempt"}


def load_dataset() -> list[dict]:
    with DATASET_PATH.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _validate_schema(case: dict) -> str | None:
    missing = [f for f in REQUIRED_FIELDS if f not in case]
    if missing:
        return f"missing fields: {missing}"
    if case["violation_type"] not in VIOLATION_TYPES:
        return f"unknown violation_type {case['violation_type']!r}"
    return None


def run_case_dry(case: dict) -> CaseResult:
    error = _validate_schema(case)
    if error:
        return CaseResult(case.get("case_id", "?"), "fail", error)
    return CaseResult(case["case_id"], "skipped", "dry_run: ChatService.ask() not called, judge not run")


async def run_case_live(case: dict, chat, chat_completion) -> CaseResult:
    from eval.shared.llm_judge import judge

    error = _validate_schema(case)
    if error:
        return CaseResult(case["case_id"], "fail", error)

    result = await chat.ask_project(case["user_message"])
    passed, reason = await judge(
        chat_completion,
        user_message=case["user_message"],
        expected_behavior=case["expected_behavior"],
        actual_answer=result.answer,
    )
    detail = f"judge: {reason} | answer: {result.answer[:300]!r}"
    return CaseResult(case["case_id"], "pass" if passed else "fail", detail)


async def main_live(cases: list[dict]) -> list[CaseResult]:
    from eval.shared.live_chat import live_chat

    async with live_chat() as chat:
        results = []
        for case in cases:
            try:
                results.append(await run_case_live(case, chat, chat.resources.chat_completion))
            except Exception as exc:  # noqa: BLE001
                # See ragas/harness.py's identical comment: a DB error leaves the shared
                # session's transaction aborted, poisoning every later case without this.
                await chat.session.rollback()
                results.append(CaseResult(case.get("case_id", "?"), "fail", f"{type(exc).__name__}: {exc}"))
        return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    cases = load_dataset()
    if args.live:
        results = asyncio.run(main_live(cases))
    else:
        results = [run_case_dry(case) for case in cases]

    report = build_report(
        domain="project_knowledge",
        eval_type="guardrails",
        run_mode="live" if args.live else "dry_run",
        results=results,
    )
    write_report(report, REPORT_PATH)
    print_summary(report)


if __name__ == "__main__":
    main()
