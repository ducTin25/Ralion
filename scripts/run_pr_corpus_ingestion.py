"""Run the one-shot F2 Sub-flow B PR/comment corpus ingestion for F6 rule mining.

Repo is fixed to thanos-io/thanos. The default window is read straight from
scripts/thanos_summary.json's 'window' field — the ground truth already annotated
for gate R-1 — so it cannot silently drift from that annotation. Pass --since/
--until only to test against a smaller window; running the real ingest against a
different repo/window than what was annotated makes the F6 density numbers
describe different data than what got ingested.

Governance: thanos-io/thanos is public OSS, unrelated to Octn — used only to demo F6's
pipeline on real data. See scripts/DEMO_GOVERNANCE_NOTE.md before presenting results.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import get_settings
from src.model.session import AsyncSessionLocal
from src.modules.knowledge.ingestion.github_client import GithubClient
from src.modules.knowledge.ingestion.pr_corpus_ingestion import ingest_pr_corpus

REPO = "thanos-io/thanos"
_SUMMARY_PATH = Path(__file__).resolve().parent / "thanos_summary.json"


def _annotated_window() -> tuple[str, str]:
    since, until = json.loads(_SUMMARY_PATH.read_text(encoding="utf-8"))["window"]
    return since, until


async def _run(since: date, until: date) -> None:
    settings = get_settings()
    client = GithubClient(settings.github_token)
    async with AsyncSessionLocal() as session:
        summary = await ingest_pr_corpus(session, client, repo=REPO, since=since, until=until)
    print(
        f"repo={summary.repo} prs_total={summary.prs_total} "
        f"prs_bot_excluded={summary.prs_bot_excluded} prs_ingested={summary.prs_ingested} "
        f"secret_findings={summary.secret_findings}"
    )
    print(f"rows_by_type={summary.rows_by_type}")


def main() -> None:
    default_since, default_until = _annotated_window()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--since", default=default_since, help=f"YYYY-MM-DD (default: annotated window start {default_since})")
    parser.add_argument("--until", default=default_until, help=f"YYYY-MM-DD (default: annotated window end {default_until})")
    args = parser.parse_args()
    asyncio.run(_run(date.fromisoformat(args.since), date.fromisoformat(args.until)))


if __name__ == "__main__":
    main()
