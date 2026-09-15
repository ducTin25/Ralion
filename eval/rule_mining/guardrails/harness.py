"""Structured-output safety harness for F6 LLM extraction (rule_mining domain).

Terminology note (CLAUDE.md Phase 9 intro): "guardrail" here means schema/behavior safety of
the extraction LLM, NOT F6_RULE_MINING_PLAN.md's >=2-evidence data-quality gate (a completely
different, unrelated use of the same English word) -- see
src/modules/knowledge/mining/rule_mining_worker.py for that one.

F6 has no interactive "user" (CLAUDE.md Phase 9 intro), so these cases probe whether
`extract_rule_candidate()` stays inside its structured-output contract even when the PR comment
content (an untrusted, adversarially-styled input) tries to push it out: fabricating a rationale
(see rule_extraction.py:NO_EXPLICIT_RATIONALE), inventing an evidence_type value outside the 6
defined in `RuleEvidenceType` (src/model/enums.py), or being talked into an inflated reuse_scope
by generalizing language that doesn't match the actual business-logic-bound content
(annotation_guide.md muc 3.1 REUSABLE vs LOCAL boundary).

Phase 9 scope: ARTIFACT ONLY, --dry-run by default.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from eval.shared.report_format import CaseResult, build_report, print_summary, write_report  # noqa: E402

DATASET_PATH = Path(__file__).resolve().parent / "test_cases.jsonl"
REPORT_PATH = Path(__file__).resolve().parent / "report.json"

REQUIRED_FIELDS = ("case_id", "raw_comment_bodies", "violation_type", "expected_behavior")
VIOLATION_TYPES = {"rationale_fabrication", "schema_violation_attempt", "scope_inflation"}
VALID_EVIDENCE_TYPES = {
    "REUSABLE_CORRECTION", "CONVENTION", "LOCAL_CORRECTION",
    "RATIONALE", "QUESTION_DISCUSSION", "NOISE_OTHER",
}


def load_dataset() -> list[dict]:
    with DATASET_PATH.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def run_case(case: dict, *, live: bool) -> CaseResult:
    missing = [f for f in REQUIRED_FIELDS if f not in case]
    if missing:
        return CaseResult(case.get("case_id", "?"), "fail", f"missing fields: {missing}")
    if case["violation_type"] not in VIOLATION_TYPES:
        return CaseResult(case["case_id"], "fail", f"unknown violation_type {case['violation_type']!r}")
    if not case["raw_comment_bodies"]:
        return CaseResult(case["case_id"], "fail", "raw_comment_bodies must be non-empty")
    if not live:
        return CaseResult(
            case["case_id"], "skipped",
            "dry_run: extract_rule_candidate() not called, evidence_type/rationale not asserted",
        )
    raise NotImplementedError(
        "Phase 9 is artifact-only: calling extract_rule_candidate() with a real "
        "ChatOpenAI/EvidenceUnit and asserting result.evidence_type is in "
        f"{sorted(VALID_EVIDENCE_TYPES)} (and, for rationale_fabrication cases, that "
        "result.rationale == NO_EXPLICIT_RATIONALE) is out of scope here."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    cases = load_dataset()
    results = [run_case(case, live=args.live) for case in cases]
    report = build_report(
        domain="rule_mining", eval_type="guardrails", run_mode="live" if args.live else "dry_run", results=results
    )
    write_report(report, REPORT_PATH)
    print_summary(report)


if __name__ == "__main__":
    main()
