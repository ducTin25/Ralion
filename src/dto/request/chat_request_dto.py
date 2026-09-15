from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from src.model.enums import DocumentDomain


class ChatMode(StrEnum):
    """User-facing chat scopes; mapped to the internal knowledge domain at the API boundary."""

    PROJECT = "PROJECT"
    POLICY = "POLICY"


class ChatRequestDTO(BaseModel):
    question: str = Field(min_length=1, max_length=8000)
    mode: ChatMode = ChatMode.PROJECT
    membership_id: int | None = Field(default=None, gt=0)
    # Omitted => start a new conversation. Present => continue that one, if it belongs to the
    # authenticated user and its frozen scope matches this request.
    conversation_id: UUID | None = None

    @model_validator(mode="after")
    def validate_scope(self) -> "ChatRequestDTO":
        if self.mode is ChatMode.PROJECT and self.membership_id is None:
            raise ValueError("membership_id is required for PROJECT chat")
        if self.mode is ChatMode.POLICY and self.membership_id is not None:
            raise ValueError("membership_id must be omitted for POLICY chat")
        return self

    @property
    def knowledge_domain(self) -> DocumentDomain:
        """Keep persistence/retrieval types behind the transport contract."""
        return DocumentDomain(self.mode.value)
