"""CLAUDE.md Phase 5 §8 — run RuleMiningWorker's real steps 3-5 (LLM extraction, embedding,
connected-components clustering) against the Phase 4 fixture (golden-test/f6_eval_fixture.json),
to verify family reconstruction and tune the cosine merge threshold with real numbers before
trusting the pipeline (F6_RULE_MINING_SPEC.md §4.4).

Reuses the exact production functions (extract_rule_candidate, cluster_by_cosine,
confidence_from_cosine) — no duplicate pipeline logic. Runs entirely in-memory (no DB session):
this script's job is extraction+clustering quality, not DB plumbing — the eligibility guardrail
that DOES need a DB (the literal SQL in eligibility.py) already has a dedicated negative test in
tests/test_modules/test_rule_mining_worker.py. Here the >=2-distinct-PR guardrail is applied as
plain Python over in-memory components (same condition, no DB round-trip needed to check it).

Credentials:
- LLM: GPT-5 mini via direct OpenAI (`get_rule_mining_llm()`) — the production factory this
  worker actually calls (2026-08-20 patch: GPT-5 mini is the dev AND production/demo model
  for this pipeline, superseding the DeepSeek stand-in the first fixture run used; switched
  from OpenRouter to direct OpenAI later the same day when OpenRouter credit ran out — see
  CHANGE_LOG.md). Reads `OPENAI_API_KEY` from `.env`.
- Embedding: production BGE_M3_ENDPOINT (Modal) over HTTP, not a local BgeM3Embedder load —
  this workstation cannot load the ~2GB local model (see Phase 4 report for the OOM detail).

Usage:
    .venv/Scripts/python.exe scripts/run_f6_mining_fixture.py
    .venv/Scripts/python.exe scripts/run_f6_mining_fixture.py --skip-llm   # reuse cached extraction
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

FIXTURE_PATH = REPO_ROOT / "golden-test" / "f6_eval_fixture.json"
REPORT_PATH = REPO_ROOT / "golden-test" / "f6_mining_pipeline_fixture_report.json"

from src.infrastructure.ai.langchain_llm import get_rule_mining_llm  # noqa: E402
from src.model.enums import RuleEvidenceType  # noqa: E402
from src.model.raw_pr_comment import RawPrComment  # noqa: E402
from src.modules.knowledge.mining.clustering import cluster_by_cosine, confidence_from_cosine  # noqa: E402
from src.modules.knowledge.mining.evidence_grouping import EvidenceUnit  # noqa: E402
from src.modules.knowledge.mining.rule_extraction import RuleCandidateExtraction, extract_rule_candidate  # noqa: E402

_CANDIDATE_THRESHOLDS = [0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]


def _unit_from_case(case: dict, synthetic_id: int) -> EvidenceUnit:
    comments = tuple(
        RawPrComment(
            raw_pr_comment_id=synthetic_id * 100 + idx,
            repo="thanos-io/thanos",
            pr_number=case["pr_number"],
            pr_author="unknown",
            type="review_comment(diff)",
            author="unknown",
            is_bot_comment=False,
            body=body,
            review_state=None,
            in_reply_to_id=None,
            url="",
            created_at=datetime(2025, 1, 1),
            secret_scanned_at=datetime(2025, 1, 1),
        )
        for idx, body in enumerate(case["raw_comment_bodies"])
    )
    return EvidenceUnit(pr_number=case["pr_number"], comments=comments)


async def _run_extraction(cases: list[dict]) -> dict[str, RuleCandidateExtraction]:
    llm = get_rule_mining_llm()
    results: dict[str, RuleCandidateExtraction] = {}
    for i, case in enumerate(cases):
        unit = _unit_from_case(case, i)
        extraction = await extract_rule_candidate(llm, unit)
        results[case["evidence_unit_id"]] = extraction
        print(f"  extracted {case['evidence_unit_id']}: eligible={extraction.eligible} type={extraction.evidence_type.value}")
    return results


def _embed_via_modal(texts: list[str]) -> list[list[float]]:
    endpoint = os.environ["BGE_M3_ENDPOINT"]
    api_key = os.environ["BGE_M3_API_KEY"]
    resp = httpx.post(
        f"{endpoint.rstrip('/')}/embed",
        json={"texts": texts},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["vectors"]


def _evaluate_threshold(
    cases_by_id: dict[str, dict],
    eligible_ids: list[str],
    vectors: dict[str, list[float]],
    threshold: float,
) -> dict:
    components = cluster_by_cosine(vectors, merge_threshold=threshold)
    # Guardrail equivalent (eligibility.py's SQL, applied here in plain Python — no DB round
    # trip needed to check ">=2 distinct evidence units AND >=2 distinct PR").
    accepted_families = [
        c for c in components if len(c.node_ids) >= 2 and len({cases_by_id[n]["pr_number"] for n in c.node_ids}) >= 2
    ]

    # Compare against the 4 known families (8 fixture cases).
    known_family_ids = {cases_by_id[uid]["expected_rule_family_id"] for uid in eligible_ids if cases_by_id[uid]["expected_rule_family_id"]}
    reconstructed = 0
    per_family: dict[str, dict] = {}
    for family_id in sorted(known_family_ids):
        expected_members = {uid for uid in eligible_ids if cases_by_id[uid]["expected_rule_family_id"] == family_id}
        pipeline_component = next((c for c in accepted_families if expected_members.issubset(set(c.node_ids))), None)
        exact_match = pipeline_component is not None and set(pipeline_component.node_ids) == expected_members
        if exact_match:
            reconstructed += 1
        per_family[family_id] = {
            "expected_members": sorted(expected_members),
            "pipeline_component_members": sorted(pipeline_component.node_ids) if pipeline_component else None,
            "exact_match": exact_match,
        }

    false_positive_families = [
        sorted(c.node_ids)
        for c in accepted_families
        if not any(set(c.node_ids) == set(per_family[f]["expected_members"]) for f in per_family)
    ]

    return {
        "threshold": threshold,
        "accepted_family_count": len(accepted_families),
        "known_families_reconstructed": reconstructed,
        "known_families_total": len(known_family_ids),
        "per_family": per_family,
        "false_positive_families": false_positive_families,
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-llm", action="store_true")
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    cases = fixture["cases"]
    cases_by_id = {c["evidence_unit_id"]: c for c in cases}

    if args.skip_llm:
        cached = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        extractions = {
            uid: RuleCandidateExtraction(
                unit=_unit_from_case(cases_by_id[uid], i),
                evidence_type=RuleEvidenceType(r["evidence_type"]),
                reuse_scope=r["reuse_scope"],
                rule_text_draft=r["rule_text_draft"],
                rationale=r["rationale"],
                prompt_tokens=r["prompt_tokens"],
                completion_tokens=r["completion_tokens"],
                model=r["model"],
                latency_ms=r["latency_ms"],
                error=r["error"],
            )
            for i, (uid, r) in enumerate(cached["extractions"].items())
        }
    else:
        print("Running LLM extraction (step 3) via GPT-5 mini / OpenRouter (production factory)...")
        extractions = await _run_extraction(cases)
        serializable = {
            uid: {
                "evidence_type": e.evidence_type.value,
                "reuse_scope": e.reuse_scope,
                "rule_text_draft": e.rule_text_draft,
                "rationale": e.rationale,
                "prompt_tokens": e.prompt_tokens,
                "completion_tokens": e.completion_tokens,
                "model": e.model,
                "latency_ms": e.latency_ms,
                "error": e.error,
            }
            for uid, e in extractions.items()
        }
        REPORT_PATH.write_text(
            json.dumps({"extractions": serializable}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    eligible_ids = [uid for uid, e in extractions.items() if e.eligible]
    print(f"\n{len(eligible_ids)}/{len(cases)} cases eligible after step 3 (evidence_type/reuse_scope filter)")

    print("Embedding rule_text_draft (step 4) via BGE_M3_ENDPOINT...")
    texts = [extractions[uid].rule_text_draft for uid in eligible_ids]
    vector_list = _embed_via_modal(texts)
    vectors = dict(zip(eligible_ids, vector_list, strict=True))

    print("\nSweeping merge_threshold candidates (step 5 + guardrail)...")
    sweep = [_evaluate_threshold(cases_by_id, eligible_ids, vectors, t) for t in _CANDIDATE_THRESHOLDS]
    for result in sweep:
        print(
            f"  threshold={result['threshold']:.2f} "
            f"reconstructed={result['known_families_reconstructed']}/{result['known_families_total']} "
            f"accepted_families={result['accepted_family_count']} "
            f"false_positives={len(result['false_positive_families'])}"
        )

    report = json.loads(REPORT_PATH.read_text(encoding="utf-8")) if REPORT_PATH.exists() else {}
    report["threshold_sweep"] = sweep
    report["eligible_case_ids"] = eligible_ids
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nFull report written to {REPORT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
