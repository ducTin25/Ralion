"""Evidence-sufficiency-gate calibration for F5 (project_knowledge domain).

CLAUDE.md discipline: "Đo trước khi tối ưu, đo trước khi tuyên bố đã sửa" / "Không hand-tune
threshold mà không có eval harness" -- applied here to a judge PROMPT exactly as
`sweep_relevance_gate.py` applied it to a numeric threshold. `chat.evidence_sufficiency_gate.
enabled` in `config/chunking_params.yaml` stays `false` until this script has produced a real
confusion matrix and CHANGE_LOG.md records the decision.

For every case in the golden fixture this calls the REAL `RetrievalEngine.retrieve()`, then the
REAL `RelevanceGate.accept()` (the exact accepted set `ChatService._ask_traced` would hand to the
gate today, post weakness #2 threshold retune), then the REAL `EvidenceSufficiencyGate.check()`
with `enabled` forced True regardless of the YAML default -- one real LLM call per case with
non-empty accepted evidence. Cases where `RelevanceGate` already rejects everything are recorded
but skipped for the gate call: `_ask_traced` never reaches this gate for those (they already
fall back as `no_evidence`), so a sufficiency-gate verdict for them would not describe production
behaviour.

Output: `eval/project_knowledge/ragas/sweep_evidence_sufficiency_gate_report.json` (gitignored)
-- one record per case with the RelevanceGate-accepted chunk ids and the gate's verdict. Run
`analyze_evidence_sufficiency_sweep.py` next to turn this into a confusion matrix against
`case_type` (answerable vs unanswerable).

Usage: python eval/project_knowledge/ragas/sweep_evidence_sufficiency_gate.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from src.ai.orchestration.evidence_sufficiency_gate import (  # noqa: E402
    EvidenceSufficiencyGate,
    EvidenceSufficiencyGateConfig,
)
from src.ai.retrieval_engine.retrieval_engine import RetrievalFilters  # noqa: E402
from src.model.enums import DocumentDomain  # noqa: E402

DATASET_PATH = Path(__file__).resolve().parent / "golden_dataset.jsonl"
REPORT_PATH = Path(__file__).resolve().parent / "sweep_evidence_sufficiency_gate_report.json"


def load_dataset() -> list[dict]:
    with DATASET_PATH.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


async def main() -> None:
    from eval.shared.live_chat import THANOS_MEMBERSHIP_ID, THANOS_USER_ID, live_chat

    cases = load_dataset()
    records: list[dict] = []

    async with live_chat() as chat:
        service = chat.service
        # Force-enabled for calibration regardless of the YAML default (still off in production
        # until this run proves the number) -- everything else (timeout, token budget) stays
        # config-driven, so this measures the real prompt against the real evidence-context
        # builder, not a stand-in.
        gate = EvidenceSufficiencyGate(
            chat.resources.chat_completion,
            EvidenceSufficiencyGateConfig(enabled=True, timeout_seconds=10.0),
        )

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
                        "error": f"retrieval: {type(exc).__name__}: {exc}",
                        "accepted_chunk_ids": [],
                        "gate_called": False,
                        "verdict": None,
                    }
                )
                print(f"{case['case_id']}: RETRIEVAL ERROR {type(exc).__name__}: {exc}")
                continue

            accepted = service.gate.accept(question, candidates)
            accepted_chunk_ids = [item.chunk.chunk_id for item in accepted]

            if not accepted:
                records.append(
                    {
                        "case_id": case["case_id"],
                        "case_type": case["case_type"],
                        "question": question,
                        "error": None,
                        "accepted_chunk_ids": [],
                        "gate_called": False,
                        "verdict": None,
                    }
                )
                print(f"{case['case_id']} ({case['case_type']}): RelevanceGate accepted 0 -- already no_evidence, gate skipped")
                continue

            try:
                result = await gate.check(question, accepted, budget)
            except Exception as exc:  # noqa: BLE001 - record and move on, don't abort the sweep
                records.append(
                    {
                        "case_id": case["case_id"],
                        "case_type": case["case_type"],
                        "question": question,
                        "error": f"gate: {type(exc).__name__}: {exc}",
                        "accepted_chunk_ids": accepted_chunk_ids,
                        "gate_called": True,
                        "verdict": None,
                    }
                )
                print(f"{case['case_id']}: GATE ERROR {type(exc).__name__}: {exc}")
                continue

            records.append(
                {
                    "case_id": case["case_id"],
                    "case_type": case["case_type"],
                    "question": question,
                    "error": None,
                    "accepted_chunk_ids": accepted_chunk_ids,
                    "gate_called": True,
                    "verdict": {
                        "sufficient": result.sufficient,
                        "errored": result.errored,
                        "supporting_chunk_ids": sorted(result.supporting_chunk_ids),
                    },
                }
            )
            print(
                f"{case['case_id']} ({case['case_type']}): accepted={accepted_chunk_ids} "
                f"sufficient={result.sufficient} errored={result.errored}"
            )

    REPORT_PATH.write_text(json.dumps({"records": records}, indent=2), encoding="utf-8")
    print(f"\nwrote {REPORT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
