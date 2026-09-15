from datetime import date, datetime

from sqlalchemy import Enum, ForeignKey, func, text
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base
from src.model.enums import ResponseLength, ResponseTone, UserRole, UserStatus


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(nullable=True)
    display_name: Mapped[str] = mapped_column(nullable=False)
    # system_role: quyền cấp công ty (ADMIN/HR), NULL với nhân viên thường.
    # Quyền theo dự án (PM/ENGINEER) đọc từ ProjectMembership.project_role, không phải ở đây.
    system_role: Mapped[UserRole | None] = mapped_column(Enum(UserRole, name="user_role"), nullable=True)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"), nullable=False, default=UserStatus.ACTIVE
    )
    # F5 chat personalization (presentation-layer only). Default = current F5 behaviour
    # unchanged — see PERSONALIZE_CHATBOT_SPEC.md §1.2/§3.3.
    response_length: Mapped[ResponseLength] = mapped_column(
        Enum(ResponseLength, name="response_length"),
        nullable=False,
        default=ResponseLength.STANDARD,
    )
    response_tone: Mapped[ResponseTone] = mapped_column(
        Enum(ResponseTone, name="response_tone"), nullable=False, default=ResponseTone.NEUTRAL
    )
    created_by_admin_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    # Ngày nhân sự chính thức bắt đầu làm việc. Nullable có chủ ý: tài khoản tạo trước
    # khi có cột này không có dữ liệu, và suy ra từ created_at sẽ tạo một ngày sai
    # trông như thật — tệ hơn để trống.
    start_date: Mapped[date | None] = mapped_column(nullable=True)
    # Mật khẩu hiện tại do admin đặt (lúc tạo tài khoản hoặc lúc reset), người dùng
    # chưa tự chọn. Chặn mọi endpoint nghiệp vụ cho tới khi họ đổi.
    must_change_password: Mapped[bool] = mapped_column(
        nullable=False, server_default=text("false"), default=False
    )
    # Mọi token phiên phát hành TRƯỚC mốc này đều bị từ chối. Đây là cách thu hồi phiên
    # tức thì mà không cần bảng session phía server: token tự chứa `issued_at`, chỉ cần
    # so sánh một số nguyên với một cột đã nạp sẵn cùng User.
    #
    # Đóng dấu ở ba thời điểm: khoá tài khoản, người dùng tự đổi mật khẩu, admin reset
    # mật khẩu. Cả ba đều là lúc phải giả định phiên đang mở không còn đáng tin.
    session_invalid_before: Mapped[datetime | None] = mapped_column(nullable=True)
