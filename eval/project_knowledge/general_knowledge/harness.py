"""F5_BOUNDED_GENERAL_KNOWLEDGE_SPEC.md (BGK) §15.2 live eval harness (project_knowledge domain).

Default mode is --dry-run (structure-only, no LLM/DB call). --live sends `user_message` through
the real `ChatService.ask()` (`eval/shared/live_chat.py`) with BGK's flags forced on for this run
(`knowledge_policy_enabled=True`, `general_knowledge.enabled=True`) regardless of what
`config/chunking_params.yaml` currently ships -- this harness is how those flags get *earned*,
not evidence that they are already safe to flip in production (§15.2's own closing line).

Each case carries both an `expect_path` (asserted from `ChatService.ask()`'s own `ChatResult` --
`answer_shape`, `citations`, `fallback_reason` -- and from the capturing telemetry sink's
`decision_details["knowledge_policy_effective"]`, the same Suite B pattern
`conversation_intelligence`'s stateful fixture already established) and an `expect_behavior`
judged by the single-prompt LLM judge (`eval/shared/llm_judge.py`) plus `forbidden_substrings`
checked directly against the answer text -- so a case can fail on EXECUTION PATH even when the
judge would have approved the prose, and vice versa.

**G1-G4 (§15.2) are NOT run by this file alone.** This harness is GK-01..GK-10 only. The full
gate set additionally requires:
  - G1: re-run `eval/project_knowledge/guardrails/` --live against `scope-gate-v2` (this repo's
    `scope_gate.py` after the §6.1(b) sentence) -- 12/12 must still be OUT_OF_SCOPE.
  - G2: re-run `eval/project_knowledge/ragas/` --live with BGK enabled -- recall/faithfulness on
    internal-fact cases must not regress.
  - G3: re-run this harness's GK-06 and every §11.2 sensitive case with
    `general_guidance_policy._SENSITIVE_MARKERS` emptied (monkeypatch or a temporary config) --
    the interpreter alone must still classify them STRICT_INTERNAL.
  - G4: re-run `eval/project_knowledge/prompt_injection/` --live with BGK enabled.
None of these have been run as part of this implementation pass (no live LLM/DB available) --
`general_knowledge.enabled`/`knowledge_policy_enabled` stay `false` in `config/chunking_params.yaml`
until they are, per this spec's own explicit "documented deferral, flag left off" discipline (§15.2
closing paragraph, mirroring `evidence_sufficiency_gate`'s precedent).
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

REQUIRED_FIELDS = ("case_id", "user_message", "expect_path", "expect_behavior")
_EXPECT_PATH_FIELDS = frozenset(
    {"knowledge_policy_effective", "answer_shape", "min_citations", "fallback_reason"}
)


def load_dataset() -> list[dict]:
    with DATASET_PATH.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _validate_schema(case: dict) -> str | None:
    missing = [f for f in REQUIRED_FIELDS if f not in case]
    if missing:
        return f"missing fields: {missing}"
    expect_path = case["expect_path"]
    if not isinstance(expect_path, dict):
        return "expect_path must be an object"
    unknown = set(expect_path) - _EXPECT_PATH_FIELDS
    if unknown:
        return f"expect_path has unknown fields: {sorted(unknown)}"
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
    path_failures: list[str] = []

    expect_path = case["expect_path"]
    if expect_path.get("knowledge_policy_effective") is not None:
        # Threaded from the last snapshot the capturing sink recorded for THIS turn.
        actual_policy = chat.telemetry_sink.decision_details().get("knowledge_policy_effective")
        if actual_policy != expect_path["knowledge_policy_effective"]:
            path_failures.append(
                f"knowledge_policy_effective: expected {expect_path['knowledge_policy_effective']!r}, got {actual_policy!r}"
            )
    if expect_path.get("answer_shape") is not None and result.answer_shape != expect_path["answer_shape"]:
        path_failures.append(f"answer_shape: expected {expect_path['answer_shape']!r}, got {result.answer_shape!r}")
    if len(result.citations) < int(expect_path.get("min_citations", 0)):
        path_failures.append(f"min_citations: expected >= {expect_path['min_citations']}, got {len(result.citations)}")
    if "fallback_reason" in expect_path and expect_path["fallback_reason"] is not None:
        if result.fallback_reason != expect_path["fallback_reason"]:
            path_failures.append(
                f"fallback_reason: expected {expect_path['fallback_reason']!r}, got {result.fallback_reason!r}"
            )

    forbidden_hits = [s for s in case.get("forbidden_substrings", []) if s.lower() in result.answer.lower()]
    if forbidden_hits:
        path_failures.append(f"forbidden_substrings present: {forbidden_hits}")

    if path_failures:
        return CaseResult(case["case_id"], "fail", "execution path: " + "; ".join(path_failures))

    passed, reason = await judge(
        chat_completion,
        user_message=case["user_message"],
        expected_behavior=case["expect_behavior"],
        actual_answer=result.answer,
    )
    detail = f"judge: {reason} | answer: {result.answer[:300]!r}"
    return CaseResult(case["case_id"], "pass" if passed else "fail", detail)


class _CapturingSinkAdapter:
    """Thin `decision_details()` accessor over the shared `_CapturingTelemetrySink` shape (same
    contract `conversation_intelligence`'s stateful fixture uses) -- kept local since this harness
    is the only eval consumer that needs it read back mid-run rather than only at the end."""

    def __init__(self) -> None:
        self.snapshots: list = []

    async def submit(self, snapshot) -> None:
        self.snapshots.append(snapshot)

    def decision_details(self) -> dict[str, object]:
        if not self.snapshots:
            return {}
        return dict(self.snapshots[-1].attributes.get("decision_details") or {})


async def main_live(cases: list[dict]) -> list[CaseResult]:
    from eval.shared.live_chat import live_chat
    from src.ai.orchestration.guidance_validation import GeneralKnowledgeConfig
    from src.ai.orchestration.turn_interpreter import TurnInterpreterConfig

    sink = _CapturingSinkAdapter()
    async with live_chat(
        telemetry_sink=sink,
        turn_interpreter_config=TurnInterpreterConfig(
            enabled=True, shadow=False, knowledge_policy_enabled=True
        ),
        general_knowledge_config=GeneralKnowledgeConfig(enabled=True),
    ) as chat:
        chat.telemetry_sink = sink  # exposed for run_case_live's decision_details() read
        results = []
        for case in cases:
            try:
                results.append(await run_case_live(case, chat, chat.resources.chat_completion))
            except Exception as exc:  # noqa: BLE001 - see guardrails/ragas harnesses' identical comment
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
        eval_type="general_knowledge",
        run_mode="live" if args.live else "dry_run",
        results=results,
    )
    write_report(report, REPORT_PATH)
    print_summary(report)


if __name__ == "__main__":
    main()
