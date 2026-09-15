from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.model.base import Base
from src.model.enums import ClaimSupportType

if TYPE_CHECKING:
    from src.model.chat_message import ChatMessage
    from src.model.citation import Citation


class AnswerClaim(Base):
    """A grounded claim that belongs to one assistant chat message."""

    __tablename__ = "answer_claims"
    __table_args__ = (
        UniqueConstraint("message_id", "claim_index"),
        # Composite citation ownership uses this candidate key to guarantee that a citation's
        # claim and denormalized message_id describe the same parent message.
        UniqueConstraint("claim_id", "message_id"),
    )

    claim_id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(
        ForeignKey("chat_messages.message_id", ondelete="CASCADE"), nullable=False
    )
    claim_index: Mapped[int] = mapped_column(nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    support_type: Mapped[ClaimSupportType] = mapped_column(
        Enum(
            ClaimSupportType,
            name="claim_support_type",
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        nullable=False,
    )
    # F-14 will define the final validator outcome vocabulary. ``pending`` makes this
    # foundational schema usable without prematurely coupling it to that later contract.
    verdict: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    redacted: Mapped[bool] = mapped_column(nullable=False, default=False)

    message: Mapped[ChatMessage] = relationship(back_populates="answer_claims")
    citations: Mapped[list[Citation]] = relationship(
        back_populates="claim",
        cascade="all, delete-orphan",
        order_by="Citation.citation_id",
    )
