"""F-21 — a legacy dirty chunk must not reach an external LLM provider.

Ingestion redacts now, but chunks written before that control existed are still in the
corpus, so both egress chokepoints (chat generation, plan-generation summarisation) are
tested against a chunk whose stored content still carries a credential.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.ai.orchestration.answer_generator import AnswerGenerator, GenerationFailure
from src.ai.retrieval_engine.retrieval_engine import RetrievalResult
from src.model.enums import DocumentDomain

SECRET = "ghp_16C7e42F292c6912E7710c838347Ae178B4a"
DIRTY_CONTENT = f"Deploy with the shared token={SECRET} before running the migration."


def _dirty_candidate() -> RetrievalResult:
    return RetrievalResult(
        chunk=SimpleNamespace(
            chunk_id=11,
            content=DIRTY_CONTENT,
            section_path="Deploy",
            heading=None,
            anchor=None,
        ),
        knowledge_domain=DocumentDomain.PROJECT,
        document_id=1,
        version_id=1,
        dense_score=0.51,
        hybrid_score=0.03,
    )


class Provider:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[list[tuple[str, str]]] = []

    async def complete(self, messages, _budget, _operation):
        self.calls.append(messages)
        return SimpleNamespace(content=self.response)


@pytest.mark.asyncio
async def test_chat_provider_payload_never_carries_the_secret() -> None:
    provider = Provider(
        '{"claims":[{"text":"Deploy before running the migration.","support":"direct",'
        '"citations":[{"chunk_id":11,"quote":"before running the migration."}]}]}'
    )
    candidate = _dirty_candidate()

    result = await AnswerGenerator(provider).generate("How do I deploy?", [candidate])

    assert provider.calls, "the provider must have been called"
    payload = "\n".join(content for _role, content in provider.calls[0])
    assert SECRET not in payload
    assert "[REDACTED]" in payload
    # Defense-in-depth only: the stored chunk is left exactly as it was found.
    assert candidate.chunk.content == DIRTY_CONTENT
    assert not isinstance(result, GenerationFailure)


@pytest.mark.asyncio
async def test_chat_fails_closed_when_the_scanner_is_unavailable(monkeypatch) -> None:
    from src.core.security import secret_scan

    def explode(_content: str):
        raise secret_scan.SecretScanUnavailableError("detect-secrets missing")

    monkeypatch.setattr("src.ai.orchestration.answer_generator.scan", explode)
    provider = Provider("{}")

    result = await AnswerGenerator(provider).generate("How do I deploy?", [_dirty_candidate()])

    assert isinstance(result, GenerationFailure)
    assert result.reason == "system_error"
    assert provider.calls == []
