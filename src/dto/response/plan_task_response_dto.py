from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from src.model.enums import TaskCategory, TaskStatus
from src.model.plan_task import PlanTask


class PlanTaskSourceResponseDTO(BaseModel):
    """1 nguồn trích dẫn của task — trỏ tới đúng 1 ĐOẠN trong 1 file tài liệu.

    `document_title` + `document_url` join sẵn từ KnowledgeDocument/DocumentVersion để FE mở
    DocumentPreviewModal ngay, không phải gọi thêm API. `section_path`/`anchor` join từ
    DocumentChunk để FE cuộn/tô sáng đúng đoạn thay vì mở nguyên file rồi bắt người đọc tự dò.

    `chunk_id`/`section_path`/`anchor` = None khi nguồn chỉ mang tính tham chiếu cả file: plan sinh
    trước khi lưu `chunk_id`, hoặc nhánh baseline / "có tài liệu nhưng không tìm được đoạn khớp".
    """

    task_source_id: int
    plan_task_id: int
    version_id: int
    document_id: int
    document_title: str
    document_url: str
    citation_note: str | None
    chunk_id: int | None = None
    section_path: str | None = None
    anchor: str | None = None

    @classmethod
    def from_detail(cls, source) -> PlanTaskSourceResponseDTO:
        """Từ `plan_task_service.SourceDetail`. Gom về 1 chỗ vì có 2 router cùng dựng DTO này
        (`onboarding_plan_router` liệt kê task của plan, `plan_task_router` trả 1 task) — trước đây
        chép tay 2 bản giống hệt nên thêm field phải nhớ sửa cả hai."""
        return cls(
            task_source_id=source.task_source_id,
            plan_task_id=source.plan_task_id,
            version_id=source.version_id,
            document_id=source.document_id,
            document_title=source.document_title,
            document_url=source.document_url,
            citation_note=source.citation_note,
            chunk_id=source.chunk_id,
            section_path=source.section_path,
            anchor=source.anchor,
        )


class PlanTaskCitationResponseDTO(BaseModel):
    """1 trích dẫn `[n]` — trỏ tới đúng 1 ĐOẠN trong tài liệu.

    Bổ sung BÊN CẠNH `sources` (mức tài liệu) chứ không thay thế: `sources` vẫn là danh sách tài liệu
    cần đọc như trước, `citations` là chi tiết từng mục để bấm mở đúng chỗ. Số `[n]` trong
    `PlanTask.instruction` khớp với `citation_order` ở đây.
    """

    citation_id: int
    plan_task_id: int
    citation_order: int
    version_id: int
    document_id: int
    document_title: str
    document_url: str
    chunk_id: int
    citation_note: str | None
    section_path: str | None
    content_snippet: str | None

    @classmethod
    def from_detail(cls, citation) -> PlanTaskCitationResponseDTO:
        """Từ `plan_task_service.CitationDetail` — gom về 1 chỗ vì 2 router cùng dựng DTO này."""
        return cls(
            citation_id=citation.citation_id,
            plan_task_id=citation.plan_task_id,
            citation_order=citation.citation_order,
            version_id=citation.version_id,
            document_id=citation.document_id,
            document_title=citation.document_title,
            document_url=citation.document_url,
            chunk_id=citation.chunk_id,
            citation_note=citation.citation_note,
            section_path=citation.section_path,
            content_snippet=citation.content_snippet,
        )


class PlanTaskResponseDTO(BaseModel):
    plan_task_id: int
    plan_id: int
    template_task_id: int
    # Lấy từ TemplateTask.category — PlanTask không lưu category riêng, FE cần để gom nhóm hiển thị.
    category: TaskCategory
    title: str
    instruction: str
    display_order: int
    mandatory: bool
    # Không phải cột DB — suy ra từ due_at của task đứng ngay trước (xem
    # plan_task_service.list_task_details). None chỉ khi plan chưa có due_at nào (baseline cũ).
    start_at: datetime | None
    due_at: datetime | None
    status: TaskStatus
    estimated_minutes: int
    sources: list[PlanTaskSourceResponseDTO]
    # Mặc định rỗng: plan sinh trước khi có bảng citation vẫn trả về hợp lệ, FE tự hiểu là chưa có
    # trích dẫn mức đoạn và chỉ hiện danh sách tài liệu.
    citations: list[PlanTaskCitationResponseDTO] = []

    @classmethod
    def from_entity(
        cls,
        task: PlanTask,
        *,
        category: TaskCategory,
        estimated_minutes: int,
        sources: list[PlanTaskSourceResponseDTO],
        citations: list[PlanTaskCitationResponseDTO] | None = None,
        start_at: datetime | None = None,
    ) -> PlanTaskResponseDTO:
        return cls(
            plan_task_id=task.plan_task_id,
            plan_id=task.plan_id,
            template_task_id=task.template_task_id,
            category=category,
            title=task.title,
            instruction=task.instruction,
            display_order=task.display_order,
            mandatory=task.mandatory,
            start_at=start_at,
            due_at=task.due_at,
            status=task.status,
            estimated_minutes=estimated_minutes,
            sources=sources,
            citations=citations or [],
        )
