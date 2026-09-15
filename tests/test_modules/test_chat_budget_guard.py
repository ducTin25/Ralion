"""F-22: chat budget guard — rate limit + daily usage/cost caps.

Focused on two things: the guard's own decision logic against `llm_call_logs`, and
proof that a rejected `ChatService.ask()` call never reaches retrieval or generation.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from src.ai.orchestration.answer_generator import GenerationFailure
from src.ai.retrieval_engine.retrieval_engine import RetrievalFilters, RetrievalResult
from src.model.enums import DocumentDomain
from src.model.llm_call_log import LlmCallLog
from src.modules.chat.application.chat_budget_guard import (
    ChatBudgetConfig,
    ChatBudgetExceededError,
    ChatBudgetGuard,
    _RateLimiter,
)
from src.modules.chat.application.chat_service import ChatService

_FIXED_NOW = datetime(2026, 8, 20, 12, 0, 0, tzinfo=UTC)


def _now() -> datetime:
    return _FIXED_NOW


async def _seed_log(
    db_session,
    *,
    user_id: int | None = None,
    project_id: int | None = None,
    cost_estimate: str | None = None,
    created_at: datetime | None = None,
) -> None:
    db_session.add(
        LlmCallLog(
            trace_id="a" * 32,
            module="chat",
            stage="chat_request",
            gate_decision="accepted",
            user_id=user_id,
            project_id=project_id,
            cost_estimate=cost_estimate,
            created_at=created_at or _FIXED_NOW,
        )
    )
    await db_session.commit()


class RecordingRetriever:
    def __init__(self, results: list[RetrievalResult]) -> None:
        self.results = results
        self.calls: list[tuple[str, RetrievalFilters]] = []

    async def retrieve(self, question: str, *, filters: RetrievalFilters, budget) -> list[RetrievalResult]:
        self.calls.append((question, filters))
        return self.results


class FixedGenerator:
    def __init__(self, result) -> None:
        self.result = result
        self.calls = 0

    async def generate(self, *_args, **_kwargs):
        self.calls += 1
        return self.result


def test_rate_limiter_allows_up_to_max_then_denies_within_window() -> None:
    clock = iter([0.0, 1.0, 2.0, 3.0]).__next__
    limiter = _RateLimiter(2, 60.0, clock=clock)

    assert limiter.allow(1) is True
    assert limiter.allow(1) is True
    assert limiter.allow(1) is False


def test_rate_limiter_purges_expired_hits_outside_window() -> None:
    times = iter([0.0, 0.0, 100.0])
    limiter = _RateLimiter(1, 60.0, clock=lambda: next(times))

    assert limiter.allow(1) is True
    assert limiter.allow(1) is False
    # 100s later, the first hit (t=0) is outside the 60s window: the slot is free again.
    assert limiter.allow(1) is True


@pytest.mark.asyncio
async def test_disabled_guard_allows_unlimited_requests(db_session) -> None:
    guard = ChatBudgetGuard(ChatBudgetConfig(0, 60.0, 0, 0.0, 0.0), now=_now)
    for _ in range(5):
        await guard.check(db_session, user_id=1, project_id=None)


@pytest.mark.asyncio
async def test_rate_limit_rejects_before_daily_caps_are_checked(db_session) -> None:
    guard = ChatBudgetGuard(ChatBudgetConfig(1, 60.0, 0, 0.0, 0.0), now=_now)
    await guard.check(db_session, user_id=1, project_id=None)

    with pytest.raises(ChatBudgetExceededError) as excinfo:
        await guard.check(db_session, user_id=1, project_id=None)
    assert excinfo.value.reason == "rate_limit"


@pytest.mark.asyncio
async def test_daily_request_cap_per_user_is_enforced(db_session) -> None:
    await _seed_log(db_session, user_id=42)
    await _seed_log(db_session, user_id=42)
    guard = ChatBudgetGuard(ChatBudgetConfig(0, 60.0, 2, 0.0, 0.0), now=_now)

    with pytest.raises(ChatBudgetExceededError) as excinfo:
        await guard.check(db_session, user_id=42, project_id=None)
    assert excinfo.value.reason == "daily_request_cap"


@pytest.mark.asyncio
async def test_daily_request_cap_ignores_other_users(db_session) -> None:
    await _seed_log(db_session, user_id=999)
    await _seed_log(db_session, user_id=999)
    guard = ChatBudgetGuard(ChatBudgetConfig(0, 60.0, 2, 0.0, 0.0), now=_now)

    await guard.check(db_session, user_id=42, project_id=None)


@pytest.mark.asyncio
async def test_daily_request_cap_ignores_rows_from_a_previous_day(db_session) -> None:
    yesterday = _FIXED_NOW - timedelta(days=1)
    await _seed_log(db_session, user_id=42, created_at=yesterday)
    await _seed_log(db_session, user_id=42, created_at=yesterday)
    guard = ChatBudgetGuard(ChatBudgetConfig(0, 60.0, 2, 0.0, 0.0), now=_now)

    await guard.check(db_session, user_id=42, project_id=None)


@pytest.mark.asyncio
async def test_daily_cost_cap_per_user_is_enforced(db_session) -> None:
    await _seed_log(db_session, user_id=42, cost_estimate="0.60")
    await _seed_log(db_session, user_id=42, cost_estimate="0.50")
    guard = ChatBudgetGuard(ChatBudgetConfig(0, 60.0, 0, 1.0, 0.0), now=_now)

    with pytest.raises(ChatBudgetExceededError) as excinfo:
        await guard.check(db_session, user_id=42, project_id=None)
    assert excinfo.value.reason == "daily_cost_cap"


@pytest.mark.asyncio
async def test_project_daily_cost_cap_only_applies_to_project_scoped_chat(db_session) -> None:
    await _seed_log(db_session, user_id=1, project_id=7, cost_estimate="6.00")
    await _seed_log(db_session, user_id=2, project_id=7, cost_estimate="5.00")
    guard = ChatBudgetGuard(ChatBudgetConfig(0, 60.0, 0, 0.0, 10.0), now=_now)

    # POLICY chat (project_id=None) never queries the project cap, however much the
    # project's own usage has accrued.
    await guard.check(db_session, user_id=3, project_id=None)

    with pytest.raises(ChatBudgetExceededError) as excinfo:
        await guard.check(db_session, user_id=3, project_id=7)
    assert excinfo.value.reason == "project_daily_cost_cap"


@pytest.mark.asyncio
async def test_project_daily_cost_cap_ignores_other_projects(db_session) -> None:
    await _seed_log(db_session, user_id=1, project_id=99, cost_estimate="50.00")
    guard = ChatBudgetGuard(ChatBudgetConfig(0, 60.0, 0, 0.0, 10.0), now=_now)

    await guard.check(db_session, user_id=1, project_id=7)


def _candidate() -> RetrievalResult:
    return RetrievalResult(
        chunk=SimpleNamespace(
            chunk_id=11,
            content="Employees receive 12 leave days.",
            section_path="Leave",
            heading="Leave",
            lexical_identifiers="",
        ),
        knowledge_domain=DocumentDomain.POLICY,
        document_id=1,
        version_id=1,
        dense_score=0.99,
        hybrid_score=0.5,
    )


@pytest.mark.asyncio
async def test_rejected_chat_request_never_reaches_retrieval_or_generation(db_session) -> None:
    """The whole point of F-22: a caller over budget must not trigger retrieval/LLM work."""
    retriever = RecordingRetriever([_candidate()])
    generator = FixedGenerator(GenerationFailure("system_error", 0))
    guard = ChatBudgetGuard(ChatBudgetConfig(1, 60.0, 0, 0.0, 0.0), now=_now)
    service = ChatService(db_session, retriever, generator, chat_budget_guard=guard)

    # First call consumes the one allowed rate-limit slot; it still reaches retrieval.
    await service.ask(question="What is the leave policy?", user_id=1, knowledge_domain=DocumentDomain.POLICY)
    assert len(retriever.calls) == 1
    assert generator.calls == 1

    with pytest.raises(ChatBudgetExceededError):
        await service.ask(
            question="What is the leave policy again?", user_id=1, knowledge_domain=DocumentDomain.POLICY
        )

    # The rejected call must not have touched retrieval or generation.
    assert len(retriever.calls) == 1
    assert generator.calls == 1
