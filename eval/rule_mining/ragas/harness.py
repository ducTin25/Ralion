"""Faithfulness-equivalent harness for F6 LLM extraction (rule_mining domain).

F6 has no "question"/"answer" in the chatbot sense (CLAUDE.md Phase 9 intro) -- what needs
measuring is whether `rule_text_draft`/`rationale` (produced by
`src/modules/knowledge/mining/rule_extraction.py:extract_rule_candidate`) stay grounded in
`raw_comment_bodies`, i.e. do not fabricate a reason the evidence text never stated (the
NO_EXPLICIT_RATIONALE invariant -- see rule_mining/guardrails/ for the direct test of that).

Ragas mapping note: this harness maps RAGAS's `faithfulness` metric (context, answer) onto
(context_for_ragas, rule_text_draft + " " + rationale) as an ANALOGY, not RAGAS's textbook
chatbot-QA usage -- documented here so a future reader does not mistake this for canonical RAGAS
usage.

Phase 9 scope: ARTIFACT ONLY, --dry-run by default. Dataset is `golden_dataset.jsonl`, a
generated copy of golden-test/f6_eval_fixture.json (Phase 4) -- the Phase 4 file itself is never
written to by this harness.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from eval.shared.report_format import CaseResult, build_report, print_summary, write_report  # noqa: E402

DATASET_PATH = Path(__file__).resolve().parent / "golden_dataset.jsonl"
REPORT_PATH = Path(__file__).resolve().parent / "report.json"
PHASE4_FIXTURE = REPO_ROOT / "eval" / "golden-test" / "f6_eval_fixture.json"

try:
    from ragas.metrics import faithfulness  # type: ignore  # noqa: F401

    RAGAS_AVAILABLE = True
except ImportError:
    RAGAS_AVAILABLE = False


def load_dataset() -> list[dict]:
    with DATASET_PATH.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def run_case(case: dict, *, live: bool) -> CaseResult:
    if not case.get("context_for_ragas"):
        return CaseResult(case["case_id"], "fail", "context_for_ragas is empty")
    if not live:
        return CaseResult(
            case["case_id"], "skipped",
            "dry_run: extract_rule_candidate() not called (no LLM), faithfulness not scored",
        )
    raise NotImplementedError(
        "Phase 9 is artifact-only: wiring extract_rule_candidate() with a real ChatOpenAI "
        "instance and mapping (context_for_ragas, rule_text_draft+rationale) through RAGAS "
        "faithfulness is out of scope here. See "
        "src/modules/knowledge/mining/rule_extraction.py:extract_rule_candidate."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    if not PHASE4_FIXTURE.is_file():
        print(f"warning: Phase 4 source fixture missing at {PHASE4_FIXTURE} (dataset was generated from it)")

    cases = load_dataset()
    results = [run_case(case, live=args.live) for case in cases]
    if not RAGAS_AVAILABLE:
        results = [
            CaseResult(r.case_id, r.status, r.detail + " | ragas not installed: faithfulness score not computed")
            if r.status != "fail"
            else r
            for r in results
        ]

    report = build_report(
        domain="rule_mining", eval_type="ragas", run_mode="live" if args.live else "dry_run", results=results
    )
    write_report(report, REPORT_PATH)
    print_summary(report)


if __name__ == "__main__":
    main()
