from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from src.config import get_settings
from src.model.enums import DocumentCategory
from src.services import repo_scanner_service


class _Classifier:
    def __init__(self, response: str = "OVERVIEW|1.4", failure: Exception | None = None) -> None:
        self.response = response
        self.failure = failure
        self.active = 0
        self.max_active = 0

    async def ainvoke(self, _prompt: str):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(0)
            if self.failure:
                raise self.failure
            return SimpleNamespace(content=self.response)
        finally:
            self.active -= 1


@pytest.mark.asyncio
async def test_ambiguous_text_uses_deepseek_and_clamps_confidence(monkeypatch) -> None:
    classifier = _Classifier()
    monkeypatch.setattr(repo_scanner_service, "get_classifier_llm", lambda: classifier)

    category, confidence, reason = await repo_scanner_service.classify_candidate(
        "docs/notes.md", b"material deliberately containing no classification terms"
    )

    assert category is DocumentCategory.OVERVIEW
    assert confidence == 1.0
    assert reason == "AI (DeepSeek) phân loại"


@pytest.mark.asyncio
@pytest.mark.parametrize("response", ["OVERVIEW", "UNKNOWN|0.5", "SETUP|nan"])
async def test_invalid_deepseek_response_falls_back_to_manual_selection(monkeypatch, response) -> None:
    monkeypatch.setattr(
        repo_scanner_service, "get_classifier_llm", lambda: _Classifier(response=response)
    )

    category, confidence, reason = await repo_scanner_service.classify_candidate(
        "docs/notes.md", b"material deliberately containing no classification terms"
    )

    assert category is None
    assert confidence == 0.0
    assert "không hợp lệ" in reason


@pytest.mark.asyncio
async def test_deepseek_failure_does_not_abort_the_scan(monkeypatch) -> None:
    monkeypatch.setattr(
        repo_scanner_service,
        "get_classifier_llm",
        lambda: _Classifier(failure=TimeoutError("provider timeout")),
    )

    scan_id, report, _ = await repo_scanner_service.build_coverage_report(
        [("docs/notes.md", b"material deliberately containing no classification terms")],
        set(),
    )

    assert scan_id
    assert report.candidates[0].suggested_category is None
    assert report.candidates[0].status is repo_scanner_service.CandidateStatus.UNCLASSIFIED


@pytest.mark.asyncio
async def test_scan_limits_parallel_deepseek_calls(monkeypatch) -> None:
    classifier = _Classifier()
    monkeypatch.setattr(repo_scanner_service, "get_classifier_llm", lambda: classifier)
    settings = get_settings()
    original = settings.deepseek_classifier_max_concurrency
    settings.deepseek_classifier_max_concurrency = 2
    try:
        files = [
            (f"docs/note-{index}.md", f"unrelated material number {index}".encode())
            for index in range(6)
        ]
        _, report, _ = await repo_scanner_service.build_coverage_report(files, set())
    finally:
        settings.deepseek_classifier_max_concurrency = original

    assert len(report.candidates) == 6
    assert classifier.max_active <= 2


@pytest.mark.asyncio
async def test_scan_deadline_falls_back_pending_ai_candidates_to_manual_selection(monkeypatch) -> None:
    class _SlowClassifier:
        async def ainvoke(self, _prompt: str):
            await asyncio.sleep(1)
            return SimpleNamespace(content="OVERVIEW|0.9")

    monkeypatch.setattr(repo_scanner_service, "get_classifier_llm", lambda: _SlowClassifier())
    settings = get_settings()
    original_timeout = settings.deepseek_classifier_timeout_seconds
    settings.deepseek_classifier_timeout_seconds = 0.01
    try:
        _, report, _ = await repo_scanner_service.build_coverage_report(
            [("docs/notes.md", b"material deliberately containing no classification terms")],
            set(),
        )
    finally:
        settings.deepseek_classifier_timeout_seconds = original_timeout

    assert report.candidates[0].status is repo_scanner_service.CandidateStatus.UNCLASSIFIED
    assert "thời gian" in report.candidates[0].reason
