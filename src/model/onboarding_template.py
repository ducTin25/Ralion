from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Index, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base
from src.model.enums import TemplateScope, TemplateStatus


class OnboardingTemplate(Base):
    __tablename__ = "onboarding_templates"
    __table_args__ = (
        # Đúng 1 OnboardingTemplate cho mỗi project, bất kể status (SoT §24.1) — thay thế
        # index cũ chỉ chặn khi cả 2 đều APPROVED (yếu hơn, cho phép lỡ tạo 2 bản DRAFT song
        # song). NULL (scope=GLOBAL) không bị tính trùng — Postgres coi nhiều NULL là khác nhau.
        UniqueConstraint("project_id", name="uq_onboarding_templates_one_per_project"),
        # Đúng 1 record scope=GLOBAL toàn hệ thống (SoT §11.15 "đúng một Global Master Template").
        Index(
            "uq_onboarding_templates_one_global",
            "scope",
            unique=True,
            postgresql_where=text("scope = 'GLOBAL'"),
        ),
    )

    template_id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.project_id"), nullable=True)
    source_template_id: Mapped[int | None] = mapped_column(
        ForeignKey("onboarding_templates.template_id"), nullable=True
    )
    scope: Mapped[TemplateScope] = mapped_column(Enum(TemplateScope, name="template_scope"), nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TemplateStatus] = mapped_column(
        Enum(TemplateStatus, name="template_status"), nullable=False, default=TemplateStatus.DRAFT
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )
