from datetime import datetime

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base


class BlockerAttachment(Base):
    """File đính kèm minh chứng cho 1 Blocker (1 blocker – nhiều attachment)."""

    __tablename__ = "blocker_attachments"

    attachment_id: Mapped[int] = mapped_column(primary_key=True)
    blocker_id: Mapped[int] = mapped_column(ForeignKey("blockers.blocker_id"), nullable=False)
    storage_key: Mapped[str] = mapped_column(nullable=False)
    file_name: Mapped[str] = mapped_column(nullable=False)
    mime_type: Mapped[str] = mapped_column(nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
