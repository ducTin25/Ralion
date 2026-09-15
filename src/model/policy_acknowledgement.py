from datetime import datetime

from sqlalchemy import ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base


class PolicyAcknowledgement(Base):
    """Bằng chứng một người đã xác nhận đọc MỘT PHIÊN BẢN cụ thể của chính sách.

    Khoá ngoại trỏ tới `version_id` chứ không phải `document_id`, và đó là quyết định
    thiết kế cốt lõi của toàn bộ tính năng:

    Nếu gắn vào `document_id`, khi HR tải lên phiên bản mới thì bản ghi xác nhận cũ vẫn
    còn — hệ thống sẽ báo "đã đọc" cho một nội dung người ta chưa từng nhìn thấy. Đó là
    loại sai nguy hiểm nhất trong tuân thủ: có bằng chứng, nhưng bằng chứng sai.

    Gắn vào `version_id` thì phiên bản mới tự động có 0 lượt xác nhận. Không cần viết
    logic reset, không có trạng thái nào phải dọn.

    Bản ghi là BẤT BIẾN — không có đường xoá. Bản chất của vết ký nhận là không sửa được;
    thêm "bỏ xác nhận" là phá giá trị của toàn bộ tính năng.
    """

    __tablename__ = "policy_acknowledgements"
    __table_args__ = (
        UniqueConstraint("version_id", "user_id", name="uq_policy_ack_version_user"),
        Index("ix_policy_ack_version", "version_id"),
        Index("ix_policy_ack_user", "user_id"),
    )

    ack_id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(
        ForeignKey("document_versions.version_id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    acknowledged_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
