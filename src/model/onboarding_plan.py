from datetime import datetime

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base
from src.model.enums import PlanStatus


class OnboardingPlan(Base):
    """Hai loại row, phân biệt bằng cột sở hữu nào có giá trị (CHECK ép đúng 1 trong 2):

    | Loại            | project_id | membership_id | Vòng đời                          |
    |-----------------|-----------|---------------|-----------------------------------|
    | Bản chuẩn dự án | có        | NULL          | luôn DRAFT, PM sửa/tạo lại tự do  |
    | Plan của kỹ sư  | NULL      | có            | DRAFT → APPROVED → ... (INV7)     |

    Bản chuẩn là nội dung mẫu PM soạn 1 lần cho cả dự án; mỗi kỹ sư được cấp plan sẽ nhận 1 BẢN SAO
    riêng để chạy tiến độ. Sửa bản chuẩn không đụng plan đã cấp (SoT rule 11 — snapshot).

    **Lưu ý cho code đọc bảng này (nhất là phần Engineer/TV2)**: plan của kỹ sư LUÔN có
    `membership_id NOT NULL`. Query nào cần "plan của người dùng" thì lọc theo `membership_id` là
    tự động loại bản chuẩn; nếu quét cả bảng thì thêm `WHERE membership_id IS NOT NULL`.
    """

    __tablename__ = "onboarding_plans"
    __table_args__ = (
        # name="owner" -> naming convention thêm tiền tố thành "ck_onboarding_plans_owner".
        # Biểu thức boolean thuần (không dùng num_nonnulls — hàm riêng của Postgres) để cùng 1 định
        # nghĩa chạy được cả SQLite (tests/conftest.py dựng bảng qua Base.metadata.create_all cho
        # test nghiệp vụ) lẫn Postgres thật, không phải bảo trì 2 phiên bản.
        CheckConstraint(
            "(project_id IS NOT NULL AND membership_id IS NULL) OR "
            "(project_id IS NULL AND membership_id IS NOT NULL)",
            name="owner",
        ),
        Index(
            "uq_onboarding_plans_one_open_per_membership",
            "membership_id",
            unique=True,
            postgresql_where=text("status != 'ONBOARDING_CLOSED'"),
        ),
        # Mỗi project đúng 1 bản chuẩn. Không đụng index trên: plan kỹ sư có project_id NULL nên
        # không nằm trong index này, và bản chuẩn có membership_id NULL — Postgres coi mỗi NULL là
        # khác nhau nên nhiều bản chuẩn không va vào ràng buộc "1 plan mở / kỹ sư".
        Index(
            "uq_onboarding_plans_one_reference_per_project",
            "project_id",
            unique=True,
            postgresql_where=text("membership_id IS NULL"),
        ),
    )

    plan_id: Mapped[int] = mapped_column(primary_key=True)
    # Chỉ set cho BẢN CHUẨN cấp dự án. Plan của kỹ sư suy ra project qua membership.
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.project_id"), nullable=True)
    membership_id: Mapped[int | None] = mapped_column(
        ForeignKey("project_memberships.membership_id"), nullable=True
    )
    template_version_id: Mapped[int] = mapped_column(ForeignKey("template_versions.version_id"), nullable=False)
    revision: Mapped[int] = mapped_column(nullable=False, default=1)
    status: Mapped[PlanStatus] = mapped_column(
        Enum(PlanStatus, name="plan_status"), nullable=False, default=PlanStatus.DRAFT
    )
    approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # Theo dõi mốc First PR (mở, merge, xác nhận) — theo quyết định 2.3 bản spec mới.
    first_pr_url: Mapped[str | None] = mapped_column(nullable=True)
    first_pr_merged_at: Mapped[datetime | None] = mapped_column(nullable=True)
    first_pr_confirmed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id"), nullable=True
    )
