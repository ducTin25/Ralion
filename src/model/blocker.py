from datetime import datetime

from sqlalchemy import CheckConstraint, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base
from src.model.enums import BlockerCategory, BlockerStatus


class Blocker(Base):
    __tablename__ = "blockers"
    __table_args__ = (
        CheckConstraint(
            "status != 'RESOLVED' OR resolved_at IS NOT NULL",
            name="resolved_requires_resolved_at",
        ),
    )

    blocker_id: Mapped[int] = mapped_column(primary_key=True)
    plan_task_id: Mapped[int] = mapped_column(ForeignKey("plan_tasks.plan_task_id"), nullable=False)
    reported_by_membership_id: Mapped[int] = mapped_column(
        ForeignKey("project_memberships.membership_id"), nullable=False
    )
    category: Mapped[BlockerCategory] = mapped_column(
        Enum(BlockerCategory, name="blocker_category"), nullable=False
    )
    reason: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[BlockerStatus] = mapped_column(
        Enum(BlockerStatus, name="blocker_status"), nullable=False, default=BlockerStatus.OPEN
    )
    reported_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)
