from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base
from src.model.enums import TaskStatus


class PlanTask(Base):
    __tablename__ = "plan_tasks"
    __table_args__ = (UniqueConstraint("plan_id", "display_order"),)

    plan_task_id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("onboarding_plans.plan_id"), nullable=False)
    template_task_id: Mapped[int] = mapped_column(ForeignKey("template_tasks.template_task_id"), nullable=False)
    title: Mapped[str] = mapped_column(nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(nullable=False)
    mandatory: Mapped[bool] = mapped_column(nullable=False, default=True)
    due_at: Mapped[datetime | None] = mapped_column(nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status"), nullable=False, default=TaskStatus.NOT_STARTED
    )
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
