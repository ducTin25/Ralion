from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, ForeignKeyConstraint, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.model.base import Base

if TYPE_CHECKING:
    from src.model.answer_claim import AnswerClaim


class Citation(Base):
    __tablename__ = "citations"
    __table_args__ = (
        # Multiple source spans in one chunk may support the same claim; only exact duplicate
        # anchors are forbidden.
        UniqueConstraint("claim_id", "chunk_id", "quote"),
        ForeignKeyConstraint(
            ["claim_id", "message_id"],
            ["answer_claims.claim_id", "answer_claims.message_id"],
            ondelete="CASCADE",
        ),
    )

    citation_id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("chat_messages.message_id"), nullable=False)
    # Nullable transition: Task 2 preserves citations generated before the claim-level
    # contract lands. F-14 persistence will populate this FK for every new citation.
    claim_id: Mapped[int | None] = mapped_column(nullable=True)
    chunk_id: Mapped[int] = mapped_column(ForeignKey("document_chunks.chunk_id"), nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    relevance_score: Mapped[float] = mapped_column(nullable=False)

    claim: Mapped["AnswerClaim | None"] = relationship(back_populates="citations")
