"""Run a scoped PROJECT GitHub sync from the command line."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# When invoked as ``python scripts/run_github_sync.py``, Python adds only the
# scripts directory to sys.path.  The application package lives at repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ai.providers.embeddings import get_bge_m3_embedder
from src.model.project import Project
from src.model.session import AsyncSessionLocal
from src.modules.knowledge.ingestion.github_sync_worker import sync_docs


async def _run(project_id: int, *, force_rechunk: bool) -> None:
    async with AsyncSessionLocal() as session:
        project = await session.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id} does not exist")
        await sync_docs(session, project, get_bge_m3_embedder(), force_rechunk=force_rechunk)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True, type=int)
    parser.add_argument("--force-rechunk", action="store_true")
    args = parser.parse_args()
    asyncio.run(_run(args.project_id, force_rechunk=args.force_rechunk))


if __name__ == "__main__":
    main()
