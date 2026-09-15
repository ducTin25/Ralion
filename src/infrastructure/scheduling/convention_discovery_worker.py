"""Dedicated worker for queued convention-discovery jobs."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from src.config import get_settings
from src.infrastructure.ai.langchain_llm import get_rule_mining_llm
from src.infrastructure.ai.resources import create_ai_resources
from src.model.session import AsyncSessionLocal
from src.modules.knowledge.ingestion import github_credential_provider
from src.modules.knowledge.mining.convention_discovery import (
    claim_next_discovery_job,
    fail_stale_discovery_jobs,
    run_reserved_discovery_job,
)

logger = logging.getLogger(__name__)
_POLL_SECONDS = 1.0
_STALE_AFTER = timedelta(minutes=15)


async def _run_once() -> bool:
    async with AsyncSessionLocal() as session:
        await fail_stale_discovery_jobs(
            session, before=datetime.now(UTC).replace(tzinfo=None) - _STALE_AFTER
        )
        job = await claim_next_discovery_job(session)
        if job is None:
            return False
        project_id = job.project_id
        github_client = await github_credential_provider.build_client_for_project(session, project_id)

    settings = get_settings()
    resources = create_ai_resources(settings)
    try:
        await run_reserved_discovery_job(
            job.ingestion_job_id,
            project_id,
            github_client=github_client,
            llm=get_rule_mining_llm(),
            embedder=resources.ingestion_embedding,
        )
    finally:
        await resources.aclose()
    return True


async def worker_loop() -> None:
    while True:
        try:
            if not await _run_once():
                await asyncio.sleep(_POLL_SECONDS)
        except Exception:  # noqa: BLE001
            logger.exception("convention_discovery_worker_iteration_failed")
            await asyncio.sleep(_POLL_SECONDS)


if __name__ == "__main__":
    asyncio.run(worker_loop())
