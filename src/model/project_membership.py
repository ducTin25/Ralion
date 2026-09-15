from datetime import datetime

from sqlalchemy import Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base
from src.model.enums import MembershipStatus, ProjectRole


class ProjectMembership(Base):
    __tablename__ = "project_memberships"
    __table_args__ = (UniqueConstraint("user_id", "project_id"),)

    membership_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.project_id"), nullable=False)
    project_role: Mapped[ProjectRole] = mapped_column(Enum(ProjectRole, name="project_role"), nullable=False)
    status: Mapped[MembershipStatus] = mapped_column(
        Enum(MembershipStatus, name="membership_status"), nullable=False, default=MembershipStatus.ACTIVE
    )
    assigned_by_admin_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
