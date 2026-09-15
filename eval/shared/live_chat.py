"""Live `ChatService` wiring shared by the F5 `project_knowledge` harnesses.

Builds the exact same object graph `src/api/routers/chat_router.py:_service` builds for a real
HTTP request (same `RetrievalEngine`, `AnswerGenerator`, `RequestBudgetConfig`, real Modal
embedding endpoint, real LLM via OpenRouter/OpenAI) against the real Postgres DB — a --live run
exercises the production code path, not a stand-in. The only deliberate deviation: the chat
budget guard's rate/cost caps are disabled (all-zero), because eval traffic firing 20+ questions
in a loop is not the interactive-user traffic those caps exist to protect.

THANOS (project_id=19) is the project the golden datasets were written against (Phase 8b) — see
`eval/README.md`. `_phase_categories` in chat_service.py gates PROJECT document visibility by the
membership's most recent OnboardingPlan.status; membership 614 (user 657) must have a plan at
ACTIVE or PROJECT_READY or every case would spuriously read as `no_evidence`. `ensure_plan_ready`
below checks this once per run and fails loudly instead of producing a misleading 0% recall.
"""
from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import desc, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from src.ai.orchestration.answer_generator import AnswerGenerator  # noqa: E402
from src.ai.orchestration.conversation_memory import MemoryConfig  # noqa: E402
from src.ai.orchestration.evidence_sufficiency_gate import (  # noqa: E402
    EvidenceSufficiencyGate,
    EvidenceSufficiencyGateConfig,
)
from src.ai.orchestration.guidance_validation import GeneralKnowledgeConfig  # noqa: E402
from src.ai.orchestration.scope_gate import ScopeGate, ScopeGateConfig  # noqa: E402
from src.ai.orchestration.turn_interpreter import TurnInterpreter, TurnInterpreterConfig  # noqa: E402
from src.ai.retrieval_engine.retrieval_engine import RetrievalEngine  # noqa: E402
from src.config import get_settings  # noqa: E402
from src.core.telemetry import TelemetrySink  # noqa: E402
from src.infrastructure.ai.resources import AiResources, create_ai_resources  # noqa: E402
from src.infrastructure.scheduling.embedding_warmup import _warmup_once  # noqa: E402
from src.infrastructure.observability import chat_telemetry_sink  # noqa: E402
from src.model.enums import DocumentDomain, PlanStatus  # noqa: E402
from src.model.onboarding_plan import OnboardingPlan  # noqa: E402
from src.model.session import AsyncSessionLocal  # noqa: E402
from src.modules.chat.application.chat_budget_guard import ChatBudgetConfig, ChatBudgetGuard  # noqa: E402
from src.modules.chat.application.chat_service import ChatResult, ChatService  # noqa: E402
from src.shared.ai.request_budget import RequestBudgetConfig  # noqa: E402

THANOS_PROJECT_ID = 19
THANOS_USER_ID = 657
THANOS_MEMBERSHIP_ID = 614

# All-zero disables every cap (see ChatBudgetGuard._RateLimiter.allow: `max_requests <= 0` -> True).
_EVAL_BUDGET_GUARD_CONFIG = ChatBudgetConfig(0, 60.0, 0, 0.0, 0.0)


class PlanNotReadyError(RuntimeError):
    """The fixture membership's plan does not unlock PROJECT category visibility."""


class LiveChatContext:
    def __init__(
        self,
        resources: AiResources,
        session: AsyncSession,
        *,
        telemetry_sink: TelemetrySink | None = None,
        turn_interpreter_config: TurnInterpreterConfig | None = None,
        general_knowledge_config: GeneralKnowledgeConfig | None = None,
    ) -> None:
        """`telemetry_sink`/`turn_interpreter_config` default to the PRODUCTION shape: the queued
        DB sink, and a `TurnInterpreter` built from `TurnInterpreterConfig.from_config()` exactly
        as `chat_router.py:69` builds it.

        The interpreter default changed on 2026-08-24. It used to be `None`, which silently ran
        every eval on the LEGACY routing path while this docstring claimed the harness "exercises
        the production code path". Measured consequence: a full 142-case suite run reported Route
        Accuracy 0.0% because `decision_details["interpreter_route"]` is only annotated on the
        interpreter path -- the metric was not failing, it was never being produced. Since
        `chat.turn_interpreter.enabled` is `true` in `config/chunking_params.yaml`, defaulting to
        the config is what makes the claim above true. Pass an explicit config to override.
        `general_knowledge_config` defaults to `GeneralKnowledgeConfig.from_config()` (the real
        `chat.general_knowledge` settings, `enabled: false` today) -- the
        `general_knowledge/harness.py` live gates (§15.2) pass an explicit enabled config.

        Suite B (F5_SEMANTIC_TURN_INTERPRETER_REVIEW.md rev. 2 §10) passes a capturing sink and a
        `shadow=True` `TurnInterpreterConfig` -- the interpreter then runs for real (real prompt,
        real LLM) but never influences the real answer, exactly as `ChatService`'s Phase 1 shadow
        wiring guarantees; only the logged `decision_details["shadow_interpreter_*"]` fields
        change what the caller can observe.
        """
        self.resources = resources
        self.session = session
        settings = get_settings()
        self.service = ChatService(
            session,
            RetrievalEngine(session, resources.chat_embedding),
            AnswerGenerator(resources.answer_generation_completion),
            scope_gate=ScopeGate(resources.chat_completion, ScopeGateConfig.from_config()),
            evidence_sufficiency_gate=EvidenceSufficiencyGate(
                resources.chat_completion, EvidenceSufficiencyGateConfig.from_config()
            ),
            turn_interpreter=TurnInterpreter(
                resources.chat_completion,
                turn_interpreter_config
                if turn_interpreter_config is not None
                else TurnInterpreterConfig.from_config(),
            ),
            memory_config=MemoryConfig.from_config(),
            telemetry_sink=telemetry_sink or chat_telemetry_sink,
            general_knowledge_config=general_knowledge_config or GeneralKnowledgeConfig.from_config(),
            budget_config=RequestBudgetConfig(
                settings.chat_overall_deadline_seconds,
                settings.chat_embedding_budget_seconds,
                settings.chat_llm_budget_seconds,
                settings.chat_persistence_reserve_seconds,
            ),
            chat_budget_guard=ChatBudgetGuard(_EVAL_BUDGET_GUARD_CONFIG),
        )

    async def ask_project(
        self,
        question: str,
        *,
        user_id: int = THANOS_USER_ID,
        membership_id: int = THANOS_MEMBERSHIP_ID,
        conversation_id=None,
    ) -> ChatResult:
        return await self.service.ask(
            question=question,
            user_id=user_id,
            knowledge_domain=DocumentDomain.PROJECT,
            membership_id=membership_id,
            conversation_id=conversation_id,
        )

    async def ask_policy(
        self, question: str, *, user_id: int = THANOS_USER_ID, conversation_id=None
    ) -> ChatResult:
        """POLICY-domain counterpart of `ask_project`.

        POLICY documents are company-wide (`scope_predicates` requires `project_id IS NULL`), so
        `ChatService._scope` REJECTS a membership_id on this domain -- passing one raises
        "membership_id must be omitted for POLICY chat". That is why this method takes no
        membership argument at all rather than defaulting one: the asymmetry with `ask_project`
        mirrors a real contract, and hiding it behind a default would only move the failure.
        """
        return await self.service.ask(
            question=question,
            user_id=user_id,
            knowledge_domain=DocumentDomain.POLICY,
            membership_id=None,
            conversation_id=conversation_id,
        )

    async def ask(self, question: str, domain: str, **kwargs) -> ChatResult:
        """Dispatch on a golden case's `domain` field ("POLICY" | "PROJECT")."""
        if domain == "POLICY":
            return await self.ask_policy(question, **kwargs)
        if domain == "PROJECT":
            return await self.ask_project(question, **kwargs)
        raise ValueError(f"unknown knowledge domain {domain!r}")


async def ensure_plan_ready(session: AsyncSession, membership_id: int = THANOS_MEMBERSHIP_ID) -> None:
    status = await session.scalar(
        select(OnboardingPlan.status)
        .where(OnboardingPlan.membership_id == membership_id)
        .order_by(desc(OnboardingPlan.created_at))
        .limit(1)
    )
    if status not in (PlanStatus.ACTIVE, PlanStatus.PROJECT_READY):
        raise PlanNotReadyError(
            f"membership {membership_id}'s latest plan status is {status!r}, not ACTIVE/"
            "PROJECT_READY -- _phase_categories() would hide every PROJECT document and every "
            "case would misleadingly report no_evidence. Fix the fixture data, don't relax this "
            "check."
        )


@asynccontextmanager
async def live_chat(
    *,
    telemetry_sink: TelemetrySink | None = None,
    turn_interpreter_config: TurnInterpreterConfig | None = None,
    general_knowledge_config: GeneralKnowledgeConfig | None = None,
):
    """`async with live_chat() as chat: await chat.ask_project(...)`"""
    settings = get_settings()
    resources = create_ai_resources(settings)
    try:
        # The web app starts this same warm-up in its lifespan/on-demand path.  A live eval builds
        # an isolated resource graph instead, so its first retrieval otherwise spends the normal
        # six-second interactive budget waiting for a scaled-to-zero Modal container (PRJ-001/003).
        # Warm-up has its own explicitly configured long budget and is fail-open: a real request
        # still reports its true runtime failure rather than masking it in the harness.
        if settings.chat_embedding_warmup_enabled:
            await _warmup_once(resources.warmup_embedding, settings.chat_embedding_warmup_timeout_seconds)
        async with AsyncSessionLocal() as session:
            await ensure_plan_ready(session)
            yield LiveChatContext(
                resources,
                session,
                telemetry_sink=telemetry_sink,
                turn_interpreter_config=turn_interpreter_config,
                general_knowledge_config=general_knowledge_config,
            )
    finally:
        await resources.aclose()
