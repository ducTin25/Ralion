"""F-20 — the ingest cores must redact before anything is chunked, embedded or stored.

These call the cores **directly**, not through their HTTP/worker adapters: the invariant is
that a caller cannot bypass the scan by forgetting to call it, so the test must not use a
caller that already scans.

No database is involved.  A recording embedder is the tripwire — it sees exactly the text
that would be embedded and persisted, and raises to stop the flow before any SQL runs.
"""

from __future__ import annotations

import pytest

from src.model.enums import DocumentCategory, PolicyCategory
from src.modules.knowledge.ingestion.versioning import ProjectIngestRequest, ingest_or_update
from src.modules.knowledge.policy_ingestion import PolicyIngestRequest, ingest_policy_document

SECRET = "ghp_16C7e42F292c6912E7710c838347Ae178B4a"
DIRTY_MARKDOWN = (
    "# Runbook\n\n"
    "## Truy cập\n\n"
    f"- **token:** {SECRET}\n\n"
    "Đọc phần này trước khi deploy.\n"
)


# `ingest_policy_document` refuses a policy without its version header, so the POLICY
# fixture carries one. The header must survive redaction untouched.
POLICY_HEADER = "- **Phiên bản:** 1.0 — Ngày hiệu lực: 01/01/2026\n\n"


class _StopAfterEmbeddingError(RuntimeError):
    """Raised by the recording embedder so the test never needs a database."""


class RecordingEmbedder:
    model_version = "test-embedder-v1"

    def __init__(self) -> None:
        self.texts: list[str] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.texts.extend(texts)
        raise _StopAfterEmbeddingError


class FakeSession:
    """Enough AsyncSession surface for the pre-embedding half of both cores."""

    def __init__(self) -> None:
        self.added: list[object] = []

    async def scalar(self, statement):
        # First ingest: no document, no active version, no cached embedding. The only
        # aggregate the cores read is the revision counter, which starts at zero.
        return 0 if "coalesce" in str(statement).lower() else None

    async def execute(self, _statement):
        return None

    def add(self, entity) -> None:
        self.added.append(entity)

    async def flush(self) -> None:
        for entity in self.added:
            # Stand in for the identity the database would assign.
            for attribute in ("document_id", "version_id"):
                if getattr(entity, attribute, None) is None and hasattr(entity, attribute):
                    setattr(entity, attribute, 1)

    async def commit(self) -> None:  # pragma: no cover - not reached
        raise AssertionError("commit must not happen before embedding succeeds")

    async def refresh(self, _entity) -> None:  # pragma: no cover - not reached
        raise AssertionError("refresh must not happen before embedding succeeds")


@pytest.mark.asyncio
async def test_project_core_redacts_before_embedding() -> None:
    embedder = RecordingEmbedder()
    request = ProjectIngestRequest(
        project_id=1,
        created_by_user_id=1,
        source_key="repo:docs/runbook.md",
        source_url="https://github.test/repo/blob/abc/docs/runbook.md",
        source_repo="org/repo",
        source_path="docs/runbook.md",
        document_category=DocumentCategory.SETUP,
        raw_content=DIRTY_MARKDOWN,
        source_ref="abc123",
        title="Runbook",
    )

    with pytest.raises(_StopAfterEmbeddingError):
        await ingest_or_update(FakeSession(), request, embedder)

    assert embedder.texts, "the core must reach embedding for this test to prove anything"
    for text in embedder.texts:
        assert SECRET not in text
    assert any("[REDACTED]" in text for text in embedder.texts)


@pytest.mark.asyncio
async def test_policy_core_redacts_before_embedding() -> None:
    embedder = RecordingEmbedder()
    request = PolicyIngestRequest(
        title="Chính sách truy cập",
        content=POLICY_HEADER + DIRTY_MARKDOWN,
        document_code="HR-ACCESS-01",
        policy_category=PolicyCategory.SECURITY_POLICY,
        created_by_user_id=1,
        source_url="https://storage.test/hr/access.md",
    )

    with pytest.raises(_StopAfterEmbeddingError):
        await ingest_policy_document(FakeSession(), request, embedder)

    assert embedder.texts
    for text in embedder.texts:
        assert SECRET not in text
    assert any("[REDACTED]" in text for text in embedder.texts)
