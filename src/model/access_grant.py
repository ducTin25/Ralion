"""Quyền truy cập đã cấp cho một người trong một dự án — vế còn thiếu của vòng đời JML.

Vấn đề tính năng này giải quyết: spec Phase 1 có bước "Quyền truy cập (repo, Jira,
secrets, môi trường)" nhưng không entity nào biểu diễn nó. Hệ quả thực tế:

- Kỹ sư mới thấy task "Xin quyền truy cập repo" mà không biết xin ai, xin thế nào.
- Admin không biết ai đang chờ quyền gì.
- Khi kỹ sư rời dự án, **không có danh sách nào để thu hồi** — đây là *access creep*:
  quyền chỉ được cấp thêm, không bao giờ được gỡ, vì không ai ghi lại đã cấp gì.

Ba quyết định thiết kế:

1. **Khoá theo `membership_id`, không phải `user_id`.** Quyền luôn gắn với một dự án
   cụ thể. Cùng một người ở hai dự án cần hai bộ quyền riêng, và rời một dự án không
   được kéo theo mất quyền ở dự án kia.

2. **Không xoá bản ghi, chỉ chuyển REVOKED.** Cột `revoked_at` giữ lại bằng chứng đã
   thu hồi — đó chính là thứ mà kiểm toán hỏi, và là lý do tồn tại của cả bảng này.

3. **Không liên kết ngược tới `PlanTask`.** TV1 sở hữu `PlanTask`; bảng này chỉ trả lời
   "admin đã cấp quyền gì, khi nào, còn hiệu lực không". Ai muốn nối hai thứ lại thì
   đọc từ đây, không sửa vào đây.
"""

from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base
from src.model.enums import AccessGrantStatus, AccessResourceType


class AccessGrant(Base):
    __tablename__ = "access_grants"
    __table_args__ = (
        # Một membership không được có hai dòng cùng loại tài nguyên đang SỐNG song song,
        # nếu không hàng đợi hiện trùng và đếm sai. Nhưng bản ghi REVOKED thì được phép
        # trùng — thu hồi rồi cấp lại là chuyện bình thường, và lịch sử phải giữ đủ.
        #
        # Vì vậy phải là partial index, không phải UniqueConstraint thường. Và phải khai
        # CẢ HAI `postgresql_where` lẫn `sqlite_where`: thiếu vế SQLite thì test sẽ tạo
        # unique index đầy đủ, khiến việc cấp lại quyền đã thu hồi không thể kiểm thử
        # được — đúng cái bẫy đã gặp với `uq_document_versions_one_active_per_document`.
        Index(
            "uq_access_grant_live_resource",
            "membership_id",
            "resource_type",
            unique=True,
            postgresql_where=text("status <> 'REVOKED'"),
            sqlite_where=text("status <> 'REVOKED'"),
        ),
        Index("ix_access_grant_membership", "membership_id"),
        Index("ix_access_grant_status", "status"),
    )

    grant_id: Mapped[int] = mapped_column(primary_key=True)
    membership_id: Mapped[int] = mapped_column(
        ForeignKey("project_memberships.membership_id"), nullable=False
    )
    resource_type: Mapped[AccessResourceType] = mapped_column(
        Enum(AccessResourceType, name="access_resource_type"), nullable=False
    )
    # Ghi chú tự do: tên repo cụ thể, đường dẫn project Jira... Để trống được vì lúc tự
    # sinh hệ thống chưa biết tên tài nguyên thật.
    resource_note: Mapped[str | None] = mapped_column(nullable=True)
    status: Mapped[AccessGrantStatus] = mapped_column(
        Enum(AccessGrantStatus, name="access_grant_status"),
        nullable=False,
        default=AccessGrantStatus.REQUESTED,
    )
    requested_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    granted_by_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id"), nullable=True
    )
    granted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
