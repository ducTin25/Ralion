from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Index, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base
from src.model.enums import TemplateVersionStatus


class TemplateVersion(Base):
    __tablename__ = "template_versions"
    __table_args__ = (
        UniqueConstraint("template_id", "version_no"),
        # Tối đa 1 version APPROVED cho mỗi template tại 1 thời điểm (SoT §11.18).
        Index(
            "uq_template_versions_one_approved_per_template",
            "template_id",
            unique=True,
            postgresql_where=text("status = 'APPROVED'"),
        ),
    )

    version_id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("onboarding_templates.template_id"), nullable=False)
    version_no: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[TemplateVersionStatus] = mapped_column(
        Enum(TemplateVersionStatus, name="template_version_status"),
        nullable=False,
        default=TemplateVersionStatus.DRAFT,
    )
    approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
