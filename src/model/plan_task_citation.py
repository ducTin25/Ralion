from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import Base


class PlanTaskCitation(Base):
    """1 trích dẫn `[n]` trong nội dung task — trỏ tới ĐÚNG 1 đoạn (`DocumentChunk`) của 1 tài liệu.

    Vì sao tách bảng riêng thay vì nới `PlanTaskSource` cho nhiều dòng/tài liệu: `PlanTaskSource`
    đang mang đúng ngữ nghĩa "1 dòng = 1 tài liệu task này cần đọc" và ĐANG ĐƯỢC Member Portal
    (`member_onboarding_service._task_sources()`) đọc trực tiếp để dựng danh sách tài liệu tham khảo.
    Nới constraint ở đó sẽ khiến Member Portal hiện trùng lặp cùng 1 file nhiều lần — hồi quy thật ở
    module của người khác. Tách bảng con giữ nguyên hợp đồng cũ, phần chi tiết theo đoạn nằm ở đây.

    Quan hệ: PlanTask 1-n PlanTaskSource (1 tài liệu) 1-n PlanTaskCitation (nhiều đoạn trong tài liệu).

    `citation_order` là số `[n]` hiển thị trong `PlanTask.instruction`, đánh số TOÀN CỤC trong 1 task
    (không reset theo từng tài liệu). Phải lưu tường minh chứ không suy ra từ thứ tự dòng: Postgres
    không đảm bảo thứ tự trả về khi thiếu ORDER BY, mà `[n]` trong text thì cố định — lệch 1 nhịp là
    bấm trích dẫn ra sai đoạn.
    """

    __tablename__ = "plan_task_citations"
    __table_args__ = (
        # Cùng 1 đoạn không được trích 2 lần trong cùng 1 nguồn — tránh nhân bản khi sinh lại.
        UniqueConstraint("task_source_id", "chunk_id"),
        # `[n]` là định danh duy nhất trong phạm vi 1 task, ép ở tầng DB chứ không chỉ tin tầng app.
        UniqueConstraint("plan_task_id", "citation_order"),
    )

    citation_id: Mapped[int] = mapped_column(primary_key=True)
    # Denormalize từ PlanTaskSource.plan_task_id: cần cột thật ở đây thì UniqueConstraint
    # (plan_task_id, citation_order) mới thực thi được ở tầng DB — constraint không join được.
    plan_task_id: Mapped[int] = mapped_column(ForeignKey("plan_tasks.plan_task_id"), nullable=False)
    task_source_id: Mapped[int] = mapped_column(
        ForeignKey("plan_task_sources.task_source_id"), nullable=False
    )
    chunk_id: Mapped[int] = mapped_column(ForeignKey("document_chunks.chunk_id"), nullable=False)
    citation_order: Mapped[int] = mapped_column(nullable=False)
    # Nhãn hiển thị (tên mục trong file). Tách khỏi nội dung đoạn để FE không phải cắt chuỗi.
    citation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
