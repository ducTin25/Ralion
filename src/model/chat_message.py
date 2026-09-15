from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Enum, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.model.base import Base
from src.model.enums import MessageRole

if TYPE_CHECKING:
    from src.model.answer_claim import AnswerClaim


class ChatMessage(Base):
    """Một message trong conversation. Mỗi turn ghi hai row: USER rồi ASSISTANT.

    USER được ghi *trước* retrieval nên audit trail sống sót khi crash giữa turn; hệ quả là có
    thể tồn tại USER lẻ không có ASSISTANT — window builder loại các turn lẻ đó.
    """

    __tablename__ = "chat_messages"
    __table_args__ = (
        # Chống double-insert cùng một turn và làm thứ tự turn trở thành bất biến tường minh.
        UniqueConstraint("session_id", "turn_index", "role"),
        Index("ix_chat_messages_session_id_message_id", "session_id", "message_id"),
    )

    message_id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.session_id"), nullable=False)
    turn_index: Mapped[int] = mapped_column(nullable=False, default=0)
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole, name="message_role"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    grounded: Mapped[bool] = mapped_column(nullable=False, default=False)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    # Nối message ↔ llm_call_logs.trace_id: debug một câu trả lời sai chỉ bằng một ID.
    trace_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Chỉ trên row ASSISTANT: no_evidence | system_error | validator_fail. NULL = grounded answer.
    fallback_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Grounding state belongs to the persisted assistant message so transcript reload never has
    # to infer it from prose or logs.
    answer_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    validator_outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    conflict: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Structured uncited general guidance is persisted separately from the composed answer so a
    # transcript reload can render mixed/guidance-only turns without parsing presentation prose.
    general_guidance: Mapped[list[dict[str, str]] | None] = mapped_column(JSON, nullable=True)
    # Chỉ trên row USER: string thực sự được embed sau condensation/rewrite. Không có cột này thì
    # không thể trả lời "vì sao turn này retrieve ra đúng/sai cái đó".
    retrieval_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    answer_claims: Mapped[list[AnswerClaim]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        order_by="AnswerClaim.claim_index",
    )
