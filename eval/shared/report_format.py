"""One report JSON shape shared by all 6 harnesses (Phase 9 mục 8).

Every harness in eval/{project_knowledge,rule_mining}/{ragas,guardrails,prompt_injection}
builds its report through `build_report()` so a future CI aggregator needs exactly one parser,
not six.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

Domain = Literal["project_knowledge", "rule_mining"]
EvalType = Literal[
    "ragas", "guardrails", "prompt_injection", "conversation_intelligence", "general_knowledge"
]
RunMode = Literal["dry_run", "live"]
Status = Literal["pass", "fail", "skipped"]


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    status: Status
    detail: str
    score: float | None = None


@dataclass(frozen=True)
class Report:
    domain: Domain
    eval_type: EvalType
    run_mode: RunMode
    total_cases: int
    results: list[CaseResult]
    summary: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def build_report(
    *, domain: Domain, eval_type: EvalType, run_mode: RunMode, results: list[CaseResult]
) -> Report:
    summary = {"pass": 0, "fail": 0, "skipped": 0}
    for result in results:
        summary[result.status] += 1
    return Report(
        domain=domain,
        eval_type=eval_type,
        run_mode=run_mode,
        total_cases=len(results),
        results=results,
        summary=summary,
    )


def write_report(report: Report, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def print_summary(report: Report) -> None:
    print(
        f"[{report.domain}/{report.eval_type}] mode={report.run_mode} "
        f"total={report.total_cases} pass={report.summary['pass']} "
        f"fail={report.summary['fail']} skipped={report.summary['skipped']}"
    )
