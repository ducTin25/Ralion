"""Phase 3 ScopeGate-merge gate (`F5_SEMANTIC_TURN_INTERPRETER_REVIEW.md` rev. 2, §7.1/§10).

"Before any regex is deleted... guardrail parity 12/12 and false-reject 0/20 on the merged
prompt. Fail ⇒ stay at Phase 2's two-call shape indefinitely." This script is that check: it
calls `TurnInterpreter.interpret()` **directly** (no `ChatService`, no retrieval/generation) so it
tests the MERGED PROMPT's scope precision in isolation, exactly as `ScopeGate`'s own original
calibration did against these same two fixture files.

- The 12 `eval/project_knowledge/guardrails/test_cases.jsonl` cases are replayed as TURN 2 of a
  conversation (rev. 2 §7.3: "no current fixture does this" for the un-merged gate; §10 items
  16-27) -- a benign grounded turn 1 precedes each, so the interpreter also has real context to
  read (and, per §7.3, to potentially be misled by if the merge weakens topicality judgment).
  Required: verdict.scope == OUT_OF_SCOPE for all 12.
- The 20 `eval/project_knowledge/ragas/golden_dataset.jsonl` answerable/unanswerable cases are
  used as TURN 1 (standalone, §10 items 28-47). Required: verdict.scope == IN_SCOPE for all 20
  (an unanswerable case can still be IN_SCOPE -- "in scope but no evidence" is a different,
  legitimate outcome from "not addressed to this project at all").
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from eval.shared.report_format import CaseResult, build_report, print_summary, write_report  # noqa: E402

GUARDRAILS_PATH = REPO_ROOT / "eval/project_knowledge/guardrails/test_cases.jsonl"
RAGAS_PATH = REPO_ROOT / "eval/project_knowledge/ragas/golden_dataset.jsonl"
REPORT_PATH = Path(__file__).resolve().parent / "phase3_scope_merge_gate_report.json"

_BENIGN_TURN1_QUESTION = (
    "Khi dùng defer để đóng 1 resource mà Close() có thể lỗi, coding style guide của Thanos "
    "khuyên dùng cách nào để không bỏ sót lỗi?"
)
_BENIGN_ANSWER_SUMMARY = (
    "Dùng helper package runutil (ví dụ runutil.CloseWithErrCapture hoặc "
    "runutil.CloseWithLogOnErr) thay vì gọi defer f.Close() trực tiếp, vì lỗi trả về từ Close "
    "có thể bị bỏ qua."
)


def _load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


async def run(repeats: int) -> list[CaseResult]:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    from src.ai.orchestration.turn_interpreter import (
        InterpreterContext,
        InterpreterScope,
        PriorTurn,
        TurnInterpreter,
        TurnInterpreterConfig,
    )
    from src.config import get_settings
    from src.infrastructure.ai.resources import create_ai_resources
    from src.model.enums import DocumentDomain
    from src.shared.ai.request_budget import RequestBudget

    settings = get_settings()
    resources = create_ai_resources(settings)
    interpreter = TurnInterpreter(resources.chat_completion, TurnInterpreterConfig())

    guardrail_cases = _load_jsonl(GUARDRAILS_PATH)
    ragas_cases = _load_jsonl(RAGAS_PATH)
    results: list[CaseResult] = []

    try:
        for repeat in range(1, repeats + 1):
            print(f"--- repeat {repeat}/{repeats} ---", flush=True)
            for case in guardrail_cases:
                context = InterpreterContext(
                    knowledge_domain=DocumentDomain.PROJECT,
                    current_utterance=case["user_message"],
                    project_name="Thanos",
                    previous_turn=PriorTurn(
                        question=_BENIGN_TURN1_QUESTION,
                        grounded=True,
                        answer_summary=_BENIGN_ANSWER_SUMMARY,
                    ),
                    turn_before_that=None,
                    evidence_titles=("Coding Style Guide",),
                )
                verdict = await interpreter.interpret(context, RequestBudget(10.0, 0.0, 10.0))
                case_id = f"{case['case_id']}#rep{repeat}"
                if verdict.scope is InterpreterScope.OUT_OF_SCOPE:
                    results.append(CaseResult(case_id, "pass", f"scope={verdict.scope.value}"))
                else:
                    results.append(
                        CaseResult(
                            case_id, "fail",
                            f"expected OUT_OF_SCOPE, got scope={verdict.scope.value} "
                            f"route={verdict.route.value} malformed={verdict.malformed}",
                        )
                    )

            for case in ragas_cases:
                context = InterpreterContext(
                    knowledge_domain=DocumentDomain.PROJECT,
                    current_utterance=case["question"],
                    project_name="Thanos",
                    previous_turn=None,
                    turn_before_that=None,
                    evidence_titles=(),
                )
                verdict = await interpreter.interpret(context, RequestBudget(10.0, 0.0, 10.0))
                case_id = f"{case['case_id']}#rep{repeat}"
                if verdict.scope is InterpreterScope.IN_SCOPE:
                    results.append(CaseResult(case_id, "pass", f"scope={verdict.scope.value}"))
                else:
                    results.append(
                        CaseResult(
                            case_id, "fail",
                            f"false reject: expected IN_SCOPE, got scope={verdict.scope.value} "
                            f"(case_type={case['case_type']})",
                        )
                    )
    finally:
        await resources.aclose()
    return results


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=1)
    args = parser.parse_args()

    results = asyncio.run(run(args.repeats))
    report = build_report(
        domain="project_knowledge", eval_type="conversation_intelligence",
        run_mode="live", results=results,
    )
    write_report(report, REPORT_PATH)
    print_summary(report)
    guardrail_fails = [r for r in results if r.case_id.startswith("pk_guard") and r.status == "fail"]
    ragas_fails = [r for r in results if r.case_id.startswith("pk_0") and r.status == "fail"]
    print(f"guardrail fails: {len(guardrail_fails)}")
    for r in guardrail_fails:
        print(f"  {r.case_id}: {r.detail}")
    print(f"ragas false-rejects: {len(ragas_fails)}")
    for r in ragas_fails:
        print(f"  {r.case_id}: {r.detail}")


if __name__ == "__main__":
    main()
