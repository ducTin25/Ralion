from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.orchestration.answer_generator import AnswerGenerator
from src.ai.orchestration.conversation_memory import MemoryConfig
from src.ai.orchestration.evidence_sufficiency_gate import (
    EvidenceSufficiencyGate,
    EvidenceSufficiencyGateConfig,
)
from src.ai.orchestration.guidance_validation import GeneralKnowledgeConfig
from src.ai.orchestration.query_condenser import LlmQueryRewriter
from src.ai.orchestration.scope_gate import ScopeGate, ScopeGateConfig
from src.ai.orchestration.support_reply import SupportReplyConfig, SupportReplyGenerator
from src.ai.orchestration.turn_interpreter import TurnInterpreter, TurnInterpreterConfig
from src.ai.retrieval_engine.retrieval_engine import RetrievalEngine
from src.api.dependencies import get_session_user
from src.config import get_settings
from src.dto.request.chat_request_dto import ChatRequestDTO
from src.dto.response.chat_conversation_response_dto import (
    ChatConversationResponseDTO,
    ChatConversationTurnResponseDTO,
)
from src.dto.response.chat_response_dto import ChatGuidanceResponseDTO, ChatResponseDTO
from src.infrastructure.ai.resources import create_ai_resources
from src.infrastructure.observability import chat_telemetry_sink, fingerprint_question
from src.infrastructure.scheduling.embedding_warmup import (
    on_demand_embedding_warmup_status,
    trigger_on_demand_embedding_warmup,
)
from src.model.session import get_db
from src.model.user import User
from src.modules.chat.application.chat_budget_guard import (
    ChatBudgetExceededError,
    get_chat_budget_guard,
)
from src.modules.chat.application.chat_service import (
    ChatService,
    ConversationNotFoundError,
    ConversationScopeMismatchError,
)
from src.shared.ai.request_budget import RequestBudgetConfig

router = APIRouter(prefix="/chat", tags=["chat"])

# An unknown conversation and somebody else's conversation must be indistinguishable: a 403 on the
# latter would confirm the id exists.
_CONVERSATION_NOT_FOUND = "Conversation not found"


def _service(db: AsyncSession, request: Request) -> ChatService:
    memory = MemoryConfig.from_config()
    settings = get_settings()
    resources = getattr(request.app.state, "ai_resources", None)
    if resources is None:
        # ASGI test transports may not drive lifespan; still cache once on app.state.
        resources = create_ai_resources(settings)
        request.app.state.ai_resources = resources
    rewriter = (
        LlmQueryRewriter(
            resources.chat_completion,
            timeout_seconds=memory.llm_rewrite_timeout_seconds,
            max_output_chars=memory.llm_rewrite_max_output_chars,
        )
        if memory.llm_rewrite_enabled
        else None
    )
    scope_gate = ScopeGate(resources.chat_completion, ScopeGateConfig.from_config())
    evidence_sufficiency_gate = EvidenceSufficiencyGate(
        resources.chat_completion, EvidenceSufficiencyGateConfig.from_config()
    )
    turn_interpreter = TurnInterpreter(resources.chat_completion, TurnInterpreterConfig.from_config())
    return ChatService(
        db,
        RetrievalEngine(db, resources.chat_embedding),
        AnswerGenerator(resources.answer_generation_completion),
        query_rewriter=rewriter,
        scope_gate=scope_gate,
        evidence_sufficiency_gate=evidence_sufficiency_gate,
        turn_interpreter=turn_interpreter,
        support_reply=SupportReplyGenerator(
            resources.chat_completion, SupportReplyConfig.from_config()
        ),
        memory_config=memory,
        telemetry_sink=chat_telemetry_sink,
        general_knowledge_config=GeneralKnowledgeConfig.from_config(),
        budget_config=RequestBudgetConfig(
            settings.chat_overall_deadline_seconds,
            settings.chat_embedding_budget_seconds,
            settings.chat_llm_budget_seconds,
            settings.chat_persistence_reserve_seconds,
        ),
        chat_budget_guard=get_chat_budget_guard(),
    )


@router.post("/warmup", status_code=status.HTTP_202_ACCEPTED)
async def warmup_embedding(
    request: Request,
    _current_user: User = Depends(get_session_user),
) -> dict[str, str]:
    """Start BGE-M3 in the background when an authenticated user enters an AI workflow."""
    settings = get_settings()
    resources = getattr(request.app.state, "ai_resources", None)
    if resources is None:
        resources = create_ai_resources(settings)
        request.app.state.ai_resources = resources
    current_status = on_demand_embedding_warmup_status(request.app.state)
    started = trigger_on_demand_embedding_warmup(
        request.app.state,
        resources.warmup_embedding,
        settings.chat_embedding_warmup_timeout_seconds,
    )
    if current_status == "ready":
        return {"status": "ready"}
    return {"status": "started" if started else "in_progress"}


@router.get("/warmup")
async def embedding_warmup_status(
    request: Request,
    _current_user: User = Depends(get_session_user),
) -> dict[str, str]:
    """Report readiness without starting another Modal request."""
    return {"status": on_demand_embedding_warmup_status(request.app.state)}


@router.post("", response_model=ChatResponseDTO)
async def ask_chat(
    dto: ChatRequestDTO,
    request: Request,
    current_user: User = Depends(get_session_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponseDTO:
    try:
        result = await _service(db, request).ask(
            question=dto.question,
            user_id=current_user.user_id,
            knowledge_domain=dto.knowledge_domain,
            membership_id=dto.membership_id,
            conversation_id=dto.conversation_id,
            trace_id=request.state.trace_id,
            question_fingerprint=fingerprint_question(dto.question),
            response_length=current_user.response_length,
            response_tone=current_user.response_tone,
        )
    except PermissionError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project access denied") from exc
    except ConversationNotFoundError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_CONVERSATION_NOT_FOUND
        ) from exc
    except ConversationScopeMismatchError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conversation scope does not match this request; start a new conversation",
        ) from exc
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ChatBudgetExceededError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    return ChatResponseDTO(
        answer=result.answer,
        citations=list(result.citations),
        fallback=result.fallback,
        fallback_reason=result.fallback_reason,
        trace_id=result.trace_id,
        answer_status=result.answer_status,
        validator_outcome=result.validator_outcome,
        claims=list(result.claims),
        conflict=result.conflict,
        conversation_id=result.conversation_id,
        general_guidance=[ChatGuidanceResponseDTO(**item) for item in result.general_guidance],
        answer_shape=result.answer_shape,
    )


@router.get("/conversations/{conversation_id}", response_model=ChatConversationResponseDTO)
async def get_conversation(
    conversation_id: UUID,
    request: Request,
    current_user: User = Depends(get_session_user),
    db: AsyncSession = Depends(get_db),
) -> ChatConversationResponseDTO:
    """Rehydrate after a reload. History lives in the database, not in browser storage."""
    try:
        transcript = await _service(db, request).transcript(
            user_id=current_user.user_id, conversation_id=conversation_id
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_CONVERSATION_NOT_FOUND
        ) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project access denied") from exc
    return ChatConversationResponseDTO(
        conversation_id=transcript.conversation_id,
        mode=transcript.knowledge_domain.value,
        membership_id=transcript.membership_id,
        turns=[
            ChatConversationTurnResponseDTO(
                turn_index=turn.turn_index,
                question=turn.question,
                answer=turn.answer,
                fallback=turn.fallback,
                fallback_reason=turn.fallback_reason,
                trace_id=turn.trace_id,
                citations=list(turn.citations),
                answer_status=turn.answer_status,
                validator_outcome=turn.validator_outcome,
                claims=list(turn.claims),
                conflict=turn.conflict,
                general_guidance=[ChatGuidanceResponseDTO(**item) for item in turn.general_guidance],
                answer_shape=turn.answer_shape,
            )
            for turn in transcript.turns
        ],
    )
