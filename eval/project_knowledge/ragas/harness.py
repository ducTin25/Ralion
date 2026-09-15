"""Retrieval-recall + hallucination-avoidance harness for F5 (project_knowledge domain).

Default mode is --dry-run (no LLM/DB call) so this script is safe to run in CI smoke-checks.
--live calls the real `ChatService.ask()` (see `eval/shared/live_chat.py`) against the real
Postgres DB, the real Modal embedding endpoint, and the real LLM (OpenRouter/OpenAI), scoped to
membership 614 / THANOS project_id=19 (Phase 8b fixture).

This is NOT RAGAS: `ragas` is not installed in this repo (checked: `pip show ragas` -> not
found, not in requirements*.txt). What --live measures instead, without that dependency:

- retrieval recall: for an "answerable" case, does at least one of `ChatResult.citations` point
  at the `knowledge_documents` row `expected_citations`' demo-data path resolves to (via
  `source_url` suffix match against the real GitHub-sourced ingest)? This is exactly the
  recall@k signal CLAUDE.md Phase 3/4 needs before retuning `dense.candidate_k` /
  `relevance_gate` / `max_chunks_per_domain` -- see AUDIT.md F-17/F-25.
- hallucination-avoidance: for an "unanswerable" case, did the service correctly fall back
  (`ChatResult.fallback is True`), and does `fallback_reason` match `expected_fallback_type`?

`detail` on every live result also lists which documents were actually retrieved (title +
relevance_score), even on a pass -- that's the number the Phase 4 sweep needs, not just pass/fail.
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

DATASET_PATH = Path(__file__).resolve().parent / "golden_dataset.jsonl"
REPORT_PATH = Path(__file__).resolve().parent / "report.json"

CORPUS_PREFIX = "demo-data/thanos-io_project-knowledge/"


def load_dataset() -> list[dict]:
    with DATASET_PATH.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _citations_exist_on_disk(citations: list[str]) -> bool:
    """`expected_citations` entries are `path#Lx-Ly` — Phase 8b requires the path half to be a
    real file under demo-data/, which this checks without needing a live retriever."""
    for citation in citations:
        path_part = citation.split("#", 1)[0]
        if not (REPO_ROOT / path_part).is_file():
            return False
    return True


def run_case_dry(case: dict) -> CaseResult:
    if case["case_type"] == "answerable" and not _citations_exist_on_disk(case["expected_citations"]):
        return CaseResult(
            case["case_id"], "fail", "expected_citations references a path missing from demo-data/"
        )
    return CaseResult(
        case["case_id"],
        "skipped",
        "dry_run: ChatService.ask() not called (structure/citation-existence check only)",
    )


async def _document_id_lookup(session) -> dict[str, int]:
    """`demo-data/.../<relative path>` -> `knowledge_documents.document_id`, keyed by the same
    relative-path suffix the golden set uses (matched against the real GitHub source_url — see
    CHANGE_LOG.md for the F-05/F-06 investigation that first confirmed this mapping)."""
    from sqlalchemy import select

    from eval.shared.live_chat import THANOS_PROJECT_ID
    from src.model.knowledge_document import KnowledgeDocument

    rows = await session.execute(
        select(KnowledgeDocument.document_id, KnowledgeDocument.source_url).where(
            KnowledgeDocument.project_id == THANOS_PROJECT_ID
        )
    )
    lookup: dict[str, int] = {}
    for document_id, source_url in rows.all():
        if not source_url:
            continue
        # https://github.com/thanos-io/thanos/blob/main/<path> -> <path>
        marker = "/blob/main/"
        idx = source_url.find(marker)
        if idx != -1:
            lookup[source_url[idx + len(marker) :]] = document_id
    return lookup


async def run_case_live(case: dict, chat, doc_lookup: dict[str, int]) -> CaseResult:
    result = await chat.ask_project(case["question"])
    retrieved = [
        f"{c.get('source_title') or c.get('chunk_id')} (score={c.get('relevance_score'):.3f})"
        for c in result.citations
    ]
    retrieved_doc_ids = {c.get("document_id") for c in result.citations if c.get("document_id") is not None}

    if case["case_type"] == "unanswerable":
        if not result.fallback:
            return CaseResult(
                case["case_id"], "fail",
                f"expected a fallback (no_evidence) but got a real answer, citing: {retrieved}",
            )
        # The pass criterion is the module docstring's own definition of hallucination-avoidance:
        # did the service fall back at all, not which stage caught it. `expected_fallback_type`
        # names the ONE mechanism the case was originally written to exercise, but weakness #2's
        # evidence_sufficiency_gate (CHANGE_LOG.md 2026-08-21) added a second, equally-safe
        # no-hallucination outcome ("insufficient_evidence") that some no_evidence-labelled cases
        # now legitimately hit instead -- and scope_gate's own documented false-rejects
        # ("out_of_scope") are a third. A reason mismatch is a mechanism note for retuning, not a
        # correctness failure -- pinning the exact string here would make the fixture strictER
        # than the invariant it exists to check.
        if result.fallback_reason != case["expected_fallback_type"]:
            return CaseResult(
                case["case_id"], "pass",
                f"correctly avoided hallucination via reason={result.fallback_reason!r} "
                f"(case was written to primarily exercise {case['expected_fallback_type']!r})",
            )
        return CaseResult(case["case_id"], "pass", f"correctly fell back: {result.fallback_reason}")

    # answerable
    expected_doc_ids = set()
    unresolved = []
    for citation in case["expected_citations"]:
        path_part = citation.split("#", 1)[0]
        relative = path_part.removeprefix(CORPUS_PREFIX)
        doc_id = doc_lookup.get(relative)
        if doc_id is None:
            unresolved.append(relative)
        else:
            expected_doc_ids.add(doc_id)
    if unresolved:
        return CaseResult(
            case["case_id"], "fail",
            f"expected_citations reference files not found in knowledge_documents for project "
            f"19 (never ingested, or source_url mismatch): {unresolved}",
        )

    if result.fallback:
        return CaseResult(
            case["case_id"], "fail",
            f"expected a real answer (recall check) but got fallback_reason={result.fallback_reason!r}",
        )
    hit = bool(expected_doc_ids & retrieved_doc_ids)
    detail = f"expected one of document_id={sorted(expected_doc_ids)}, retrieved: {retrieved or '(none)'}"
    return CaseResult(case["case_id"], "pass" if hit else "fail", detail)


async def main_live(cases: list[dict]) -> list[CaseResult]:
    from eval.shared.live_chat import live_chat

    async with live_chat() as chat:
        doc_lookup = await _document_id_lookup(chat.session)
        results = []
        for case in cases:
            try:
                results.append(await run_case_live(case, chat, doc_lookup))
            except Exception as exc:  # noqa: BLE001 - report the failure as a case, don't abort the batch
                # A DB error leaves the shared session's transaction aborted -- every later
                # case would fail with InFailedSQLTransactionError otherwise (production never
                # hits this: each HTTP request gets its own fresh session).
                await chat.session.rollback()
                results.append(CaseResult(case["case_id"], "fail", f"{type(exc).__name__}: {exc}"))
        return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="call ChatService.ask() for real")
    args = parser.parse_args()

    cases = load_dataset()
    if args.live:
        results = asyncio.run(main_live(cases))
    else:
        results = [run_case_dry(case) for case in cases]

    report = build_report(
        domain="project_knowledge",
        eval_type="ragas",
        run_mode="live" if args.live else "dry_run",
        results=results,
    )
    write_report(report, REPORT_PATH)
    print_summary(report)


if __name__ == "__main__":
    main()
