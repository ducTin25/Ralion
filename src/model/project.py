from datetime import datetime, time

from sqlalchemy import CheckConstraint, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base
from src.model.enums import DiscoveryMode, ProjectStatus, SyncStatus


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        # name="github_target_paired" -> naming convention thêm tiền tố thành
        # "ck_projects_github_target_paired".
        CheckConstraint(
            "(github_repo IS NULL AND default_branch IS NULL) OR "
            "(github_repo IS NOT NULL AND default_branch IS NOT NULL)",
            name="github_target_paired",
        ),
        # F6 Scheduled Incremental Convention Discovery — each mode requires exactly its own
        # fields, mirroring github_target_paired's existing "pairing" idiom above. Can't
        # discover conventions without a connected repo, so any scheduled mode requires one.
        CheckConstraint(
            "discovery_mode = 'MANUAL_ONLY' OR github_repo IS NOT NULL",
            name="discovery_requires_github_repo",
        ),
        CheckConstraint(
            "discovery_mode != 'EVERY_N_HOURS' OR discovery_interval_hours IS NOT NULL",
            name="discovery_every_n_hours_requires_interval",
        ),
        CheckConstraint("discovery_interval_hours IS NULL OR discovery_interval_hours >= 1", name="discovery_interval_hours_min_1"),
        CheckConstraint(
            "discovery_mode NOT IN ('DAILY_AT', 'WEEKLY_AT') OR "
            "(discovery_time_of_day IS NOT NULL AND discovery_timezone IS NOT NULL)",
            name="discovery_daily_weekly_requires_time_and_tz",
        ),
        CheckConstraint(
            "discovery_mode != 'WEEKLY_AT' OR discovery_day_of_week IS NOT NULL",
            name="discovery_weekly_requires_day_of_week",
        ),
        CheckConstraint(
            "discovery_day_of_week IS NULL OR (discovery_day_of_week >= 0 AND discovery_day_of_week <= 6)",
            name="discovery_day_of_week_range",
        ),
    )

    project_id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(unique=True, nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    # Vòng lặp FK Project <-> ProjectMembership: dùng use_alter để Alembic phát ra
    # ALTER TABLE hoãn lại sau khi cả 2 bảng đã tồn tại, thay vì raw SQL tay.
    primary_pm_membership_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "project_memberships.membership_id",
            use_alter=True,
            name="fk_projects_primary_pm_membership_id",
        ),
        nullable=True,
    )
    created_by_admin_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="project_status"), nullable=False, default=ProjectStatus.ACTIVE
    )
    sync_status: Mapped[SyncStatus] = mapped_column(
        Enum(SyncStatus, name="sync_status"), nullable=False, default=SyncStatus.NOT_STARTED
    )
    # Toạ độ GitHub để đồng bộ tài liệu tự động. NULL = project chưa cấu hình GitHub, vẫn hợp lệ:
    # PM tạo project rồi tự quét thư mục/tải tài liệu tay (luồng chính hiện tại) không cần repo nào.
    # CHECK `ck_projects_github_target_paired` ép 2 cột cùng NULL hoặc cùng có giá trị — nửa vời
    # (có repo mà thiếu branch) sẽ làm `github_sync_worker.sync_docs` không biết lấy nhánh nào.
    github_repo: Mapped[str | None] = mapped_column(String, nullable=True)
    default_branch: Mapped[str | None] = mapped_column(String, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    # ---- F6 Scheduled Incremental Convention Discovery ----
    discovery_mode: Mapped[DiscoveryMode] = mapped_column(
        Enum(DiscoveryMode, name="discovery_mode"), nullable=False, default=DiscoveryMode.MANUAL_ONLY
    )
    discovery_interval_hours: Mapped[int | None] = mapped_column(nullable=True)
    discovery_time_of_day: Mapped[time | None] = mapped_column(nullable=True)
    # 0=Monday..6=Sunday, matching Python's own datetime.weekday().
    discovery_day_of_week: Mapped[int | None] = mapped_column(nullable=True)
    discovery_timezone: Mapped[str | None] = mapped_column(String, nullable=True)
    # Precomputed by the scheduler/service on every schedule save and after every scheduled
    # fire — naive UTC, matching this codebase's persist convention everywhere else. NULL for
    # MANUAL_ONLY (no automated run).
    discovery_next_run_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # Last point in time the PR/comment corpus was successfully covered up to (naive UTC).
    # NULL = never ingested (cold start). Advanced only after a run's ingestion step commits.
    discovery_pr_corpus_watermark_at: Mapped[datetime | None] = mapped_column(nullable=True)
