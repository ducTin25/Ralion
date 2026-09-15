"""Relevance-gate threshold measurement for F5 (project_knowledge domain).

CLAUDE.md discipline: "Đo trước khi tối ưu, đo trước khi tuyên bố đã sửa" / "Không hand-tune
threshold mà không có eval harness." This script is the measurement step that precedes any
change to `config/chunking_params.yaml:chat.relevance_gate`.

It calls the REAL `RetrievalEngine.retrieve()` (real Postgres, real Modal embedding, THANOS
project_id=19 fixture -- see `eval/shared/live_chat.py`) exactly once per golden-set case, and
records every candidate's raw `dense_score`/`bm25_score`/`bm25_rank`/lexical-identifier overlap.
It deliberately does NOT call `AnswerGenerator` (no LLM cost) and does NOT go through
`ChatService.ask()` (no conversation/message rows written) -- `RelevanceGate.accept()` only
consumes retrieval output, so a threshold sweep only needs that output, captured once, replayed
offline against as many candidate threshold values as needed.

Output: `eval/project_knowledge/ragas/sweep_report.json` (gitignored -- regenerable, not source of
truth) -- raw per-case candidate scores for the PROJECT/en config cell (THANOS fixture is 100%
English source text, so only `project.en` is exercised by this dataset -- see README.md domain
note). Run `analyze_sweep.py` next to replay `RelevanceGate.accept()`'s exact accept condition
against this file for a grid of `min_dense_cosine` values and print the resulting confusion
matrix (answerable-accepted vs unanswerable-accepted) per threshold.

Usage: python eval/project_knowledge/ragas/sweep_relevance_gate.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from src.ai.retrieval_engine.chunking_config import load_chunking_config  # noqa: E402
from src.ai.retrieval_engine.lexical import lexical_identifiers  # noqa: E402
from src.ai.retrieval_engine.retrieval_engine import RetrievalFilters  # noqa: E402
from src.model.enums import DocumentDomain  # noqa: E402

DATASET_PATH = Path(__file__).resolve().parent / "golden_dataset.jsonl"
REPORT_PATH = Path(__file__).resolve().parent / "sweep_report.json"


def load_dataset() -> list[dict]:
    with DATASET_PATH.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


async def main() -> None:
    from eval.shared.live_chat import live_chat

    cases = load_dataset()
    current_threshold = load_chunking_config()["chat"]["relevance_gate"]["project"]["en"]
    print(f"current config: project.en relevance_gate = {current_threshold}")

    records: list[dict] = []
    async with live_chat() as chat:
        service = chat.service
        from eval.shared.live_chat import THANOS_MEMBERSHIP_ID, THANOS_USER_ID

        membership, categories = await service._scope(
            user_id=THANOS_USER_ID,
            knowledge_domain=DocumentDomain.PROJECT,
            membership_id=THANOS_MEMBERSHIP_ID,
        )
        filters = RetrievalFilters(
            knowledge_domains=frozenset({DocumentDomain.PROJECT}),
            project_id=membership.project_id,
            document_categories=categories,
        )

        for case in cases:
            budget = service.budget_config.start()
            question = case["question"]
            query_identifiers = {
                item.casefold() for item in lexical_identifiers(question).splitlines()
            }
            try:
                candidates = await service.retrieval_engine.retrieve(
                    question, filters=filters, budget=budget
                )
            except Exception as exc:  # noqa: BLE001 - record and move on, don't abort the sweep
                records.append(
                    {
                        "case_id": case["case_id"],
                        "case_type": case["case_type"],
                        "question": question,
                        "error": f"{type(exc).__name__}: {exc}",
                        "candidates": [],
                    }
                )
                print(f"{case['case_id']}: RETRIEVAL ERROR {type(exc).__name__}: {exc}")
                continue

            candidate_records = []
            for candidate in candidates:
                chunk_identifiers = {
                    item.casefold() for item in candidate.chunk.lexical_identifiers.splitlines()
                }
                candidate_records.append(
                    {
                        "chunk_id": candidate.chunk.chunk_id,
                        "document_title": candidate.document_title,
                        "dense_score": candidate.dense_score,
                        "dense_rank": candidate.dense_rank,
                        "bm25_score": candidate.bm25_score,
                        "bm25_rank": candidate.bm25_rank,
                        "hybrid_score": candidate.hybrid_score,
                        "lexical_overlap": bool(query_identifiers & chunk_identifiers),
                    }
                )
            records.append(
                {
                    "case_id": case["case_id"],
                    "case_type": case["case_type"],
                    "question": question,
                    "error": None,
                    "candidates": candidate_records,
                }
            )
            top_dense = max((c["dense_score"] or 0.0) for c in candidate_records) if candidate_records else None
            print(f"{case['case_id']} ({case['case_type']}): {len(candidate_records)} candidates, max dense_score={top_dense}")

    REPORT_PATH.write_text(json.dumps({"records": records}, indent=2), encoding="utf-8")
    print(f"\nwrote {REPORT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
