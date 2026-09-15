"""Stored conversation, shaped for a client rehydrating after a reload."""

from uuid import UUID

from pydantic import BaseModel

from src.dto.response.chat_response_dto import (
    ChatCitationResponseDTO,
    ChatClaimResponseDTO,
    ChatGuidanceResponseDTO,
)


class ChatConversationTurnResponseDTO(BaseModel):
    turn_index: int
    question: str
    # None only for a turn that crashed between persisting the question and answering it.
    answer: str | None = None
    fallback: bool = False
    fallback_reason: str | None = None
    trace_id: str | None = None
    citations: list[ChatCitationResponseDTO] = []
    answer_status: str | None = None
    validator_outcome: str | None = None
    claims: list[ChatClaimResponseDTO] = []
    conflict: str | None = None
    general_guidance: list[ChatGuidanceResponseDTO] = []
    answer_shape: str = "internal_only"


class ChatConversationResponseDTO(BaseModel):
    conversation_id: UUID
    mode: str
    membership_id: int | None = None
    turns: list[ChatConversationTurnResponseDTO]
