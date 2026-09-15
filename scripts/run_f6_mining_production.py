"""F6 Phase 7 — one-shot production mining run against real thanos-io/thanos data already
ingested into Postgres (scripts/run_pr_corpus_ingestion.py). NOT the fixture harness
(scripts/run_f6_mining_fixture.py runs in-memory against golden-test/f6_eval_fixture.json).

Reuses the exact production entrypoint (mine_rules) and production factories
(get_rule_mining_llm — GPT-5 mini via OpenRouter; create_ai_resources(...).ingestion_embedding
— real BGE-M3 via Modal) — no duplicate pipeline logic. One-shot per CLAUDE.md Phase 7 scope
cut: no scheduling, no re-run automation.

Usage:
    .venv/Scripts/python.exe scripts/run_f6_mining_production.py

Governance: thanos-io/thanos is public OSS, unrelated to Octn — used only to demo F6's
pipeline on real data. See scripts/DEMO_GOVERNANCE_NOTE.md before presenting results.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

from src.config import get_settings  # noqa: E402
from src.infrastructure.ai.langchain_llm import get_rule_mining_llm  # noqa: E402
from src.infrastructure.ai.resources import create_ai_resources  # noqa: E402
from src.model.session import AsyncSessionLocal  # noqa: E402
from src.modules.knowledge.mining.rule_mining_worker import mine_rules  # noqa: E402

REPO = "thanos-io/thanos"


async def main() -> None:
    load_dotenv(REPO_ROOT / ".env")
    settings = get_settings()
    resources = create_ai_resources(settings)
    llm = get_rule_mining_llm()
    try:
        async with AsyncSessionLocal() as session:
            summary = await mine_rules(session, llm, resources.ingestion_embedding, repo=REPO)
        print(f"repo={summary.repo}")
        print(f"comments_loaded={summary.comments_loaded}")
        print(f"comments_after_noise_filter={summary.comments_after_noise_filter}")
        print(f"evidence_units_total={summary.evidence_units_total}")
        print(f"evidence_units_eligible={summary.evidence_units_eligible}")
        print(f"evidence_units_filtered_out={summary.evidence_units_filtered_out}")
        print(f"candidate_families={summary.candidate_families}")
        print(f"families_created={summary.families_created}")
        print(f"families_pruned_ineligible={summary.families_pruned_ineligible}")
    finally:
        await resources.aclose()


if __name__ == "__main__":
    asyncio.run(main())
