from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base


class TaskDependency(Base):
    __tablename__ = "task_dependencies"
    __table_args__ = (UniqueConstraint("predecessor_task_id", "successor_task_id"),)

    dependency_id: Mapped[int] = mapped_column(primary_key=True)
    predecessor_task_id: Mapped[int] = mapped_column(
        ForeignKey("template_tasks.template_task_id"), nullable=False
    )
    successor_task_id: Mapped[int] = mapped_column(
        ForeignKey("template_tasks.template_task_id"), nullable=False
    )
