from uuid import UUID

from pydantic import BaseModel


class ChatCitationResponseDTO(BaseModel):
    chunk_id: int
    quote: str
    knowledge_domain: str
    relevance_score: float
    redacted: bool
    document_id: int | None = None
    version_id: int | None = None
    source_title: str | None = None
    source_url: str | None = None
    section_heading: str | None = None
    anchor: str | None = None
    source_content: str | None = None


class ChatClaimResponseDTO(BaseModel):
    claim_index: int
    text: str
    support_type: str
    verdict: str
    redacted: bool
    citations: list[ChatCitationResponseDTO]


class ChatGuidanceResponseDTO(BaseModel):
    """F5_BOUNDED_GENERAL_KNOWLEDGE_SPEC.md §5.4. Deliberately has no citation field, mirroring
    `GuidanceRef`/`VerifiedGuidance` -- uncited general knowledge, never a claim."""

    text: str
    kind: str


class ChatResponseDTO(BaseModel):
    answer: str
    citations: list[ChatCitationResponseDTO]
    fallback: bool
    fallback_reason: str | None
    trace_id: str
    answer_status: str
    validator_outcome: str | None
    claims: list[ChatClaimResponseDTO]
    conflict: str | None
    # Always returned, including on fallback turns: the client needs it to continue the
    # conversation even when this turn found nothing.
    conversation_id: UUID
    # F5_BOUNDED_GENERAL_KNOWLEDGE_SPEC.md §5.4: additive, defaulted -- an older client that
    # ignores these fields keeps working unchanged. `general_guidance` renders as a visually
    # distinct, uncited block; `answer_shape` is internal_only | mixed | guidance_only.
    general_guidance: list[ChatGuidanceResponseDTO] = []
    answer_shape: str = "internal_only"
