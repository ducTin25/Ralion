from sqlalchemy import Enum, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base
from src.model.enums import TaskCategory


class TemplateTask(Base):
    __tablename__ = "template_tasks"
    __table_args__ = (UniqueConstraint("version_id", "display_order"),)

    template_task_id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("template_versions.version_id"), nullable=False)
    category: Mapped[TaskCategory] = mapped_column(Enum(TaskCategory, name="task_category"), nullable=False)
    title_pattern: Mapped[str] = mapped_column(nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    instruction_template: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(nullable=False)
    mandatory: Mapped[bool] = mapped_column(nullable=False, default=True)
    estimated_minutes: Mapped[int] = mapped_column(nullable=False)
