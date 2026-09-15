"""PlanTask — đọc chi tiết task của 1 plan và cho PM sửa tay khi plan còn DRAFT."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dto.request.plan_task_request_dto import UpdatePlanTaskRequestDTO
from src.model.document_chunk import DocumentChunk
from src.model.document_version import DocumentVersion
from src.model.enums import PlanStatus, TaskCategory
from src.model.knowledge_document import KnowledgeDocument
from src.model.onboarding_plan import OnboardingPlan
from src.model.plan_task import PlanTask
from src.model.plan_task_citation import PlanTaskCitation
from src.model.plan_task_source import PlanTaskSource
from src.model.template_task import TemplateTask


@dataclass
class SourceDetail:
    task_source_id: int
    plan_task_id: int
    version_id: int
    document_id: int
    document_title: str
    document_url: str
    citation_note: str | None
    # Vị trí đoạn tài liệu đã dùng — FE cuộn/tô sáng đúng chỗ khi PM bấm trích dẫn, thay vì mở
    # nguyên file rồi tự dò. None với plan cũ (sinh trước khi lưu chunk_id) và với nguồn chỉ mang
    # tính tham chiếu cả file (baseline / không tìm được đoạn khớp).
    chunk_id: int | None
    section_path: str | None
    anchor: str | None


@dataclass
class CitationDetail:
    """1 trích dẫn `[n]` — trỏ tới đúng 1 ĐOẠN, dùng cho việc bấm mở đúng chỗ trong tài liệu.

    Khác `SourceDetail` (mức tài liệu, giữ nguyên cho tương thích): 1 tài liệu có thể có nhiều dòng
    ở đây, mỗi dòng 1 mục trong file.
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
    # Đoạn văn bản THUẦN (đã bỏ cú pháp markdown) để FE dò trong nội dung đã render rồi cuộn tới.
    # Định vị theo nội dung chính xác hơn theo tiêu đề: 1 tiêu đề có thể bị tách thành nhiều đoạn,
    # và 2 mục trong cùng file có thể trùng tên.
    content_snippet: str | None


@dataclass
class PlanTaskDetail:
    task: PlanTask
    category: TaskCategory
    estimated_minutes: int
    sources: list[SourceDetail]
    citations: list[CitationDetail]
    # Không phải cột DB — suy ra từ `due_at`. Task N (N>1): = due_at của task N-1. Task đầu tiên:
    # = due_at của chính nó trừ estimated_minutes (KHÔNG dùng OnboardingPlan.created_at — đó là lúc
    # DB tạo dòng plan, khác hẳn giờ PM chọn ở modal khi sinh; do modal không lưu riêng, suy ngược
    # từ due_at là cách duy nhất không cần thêm cột). Luôn tự nhất quán với due_at hiện tại, kể cả
    # sau khi PM sửa tay 1 task — không có giá trị nào "lệch" so với dữ liệu thật đang hiển thị.
    start_at: datetime | None


SNIPPET_MAX_CHARS = 160


def _plain_text_snippet(content: str) -> str:
    """Lấy 1 đoạn văn bản THUẦN từ nội dung chunk để frontend dò trong DOM đã render.

    Phải bỏ đúng những cú pháp mà `markdownPreview.renderInline()` bên frontend bỏ (đậm, code, link)
    và đúng những tiền tố mà `renderMarkdown()` nuốt (heading, gạch đầu dòng, số thứ tự, trích dẫn,
    checkbox) — không hơn không kém. Bỏ nhiều hơn (ví dụ ký tự `|` của bảng, thứ mà renderer hiện
    không xử lý) sẽ tạo ra chuỗi không tồn tại trong DOM và làm việc dò luôn trượt.

    Chỉ lấy DÒNG đầu tiên có nội dung: mỗi dòng markdown render thành 1 khối riêng, chuỗi trải dài
    qua nhiều khối sẽ không nằm gọn trong một node văn bản nào để so khớp.
    """
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^#{1,6}\s+", "", line)
        line = re.sub(r"^>\s*", "", line)
        line = re.sub(r"^[-*]\s+\[[ xX]\]\s+", "", line)
        line = re.sub(r"^[-*]\s+", "", line)
        line = re.sub(r"^\d+[.)]\s+", "", line)
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
        line = re.sub(r"\*\*([^*]+)\*\*", r"\1", line)
        line = re.sub(r"`([^`]+)`", r"\1", line)
        line = " ".join(line.split())
        if line:
            return line[:SNIPPET_MAX_CHARS]
    return ""


async def list_task_citations(db: AsyncSession, plan_id: int) -> dict[int, list[CitationDetail]]:
    """Trích dẫn mức đoạn của mọi task trong 1 plan, gom theo `plan_task_id`.

    LUÔN `ORDER BY citation_order`: số `[n]` in trong nội dung là cố định, còn thứ tự Postgres trả về
    thì không đảm bảo nếu thiếu ORDER BY — lệch 1 nhịp là bấm trích dẫn ra sai đoạn.
    """
    rows = (
        await db.execute(
            select(
                PlanTaskCitation,
                PlanTaskSource.version_id,
                KnowledgeDocument.document_id,
                KnowledgeDocument.title,
                KnowledgeDocument.source_url,
                DocumentChunk.section_path,
                DocumentChunk.content,
            )
            .join(PlanTaskSource, PlanTaskSource.task_source_id == PlanTaskCitation.task_source_id)
            .join(DocumentVersion, DocumentVersion.version_id == PlanTaskSource.version_id)
            .join(KnowledgeDocument, KnowledgeDocument.document_id == DocumentVersion.document_id)
            .join(DocumentChunk, DocumentChunk.chunk_id == PlanTaskCitation.chunk_id)
            .join(PlanTask, PlanTask.plan_task_id == PlanTaskCitation.plan_task_id)
            .where(PlanTask.plan_id == plan_id)
            .order_by(PlanTaskCitation.citation_order)
        )
    ).all()

    citations_by_task: dict[int, list[CitationDetail]] = {}
    for citation, version_id, document_id, title, source_url, section_path, chunk_content in rows:
        citations_by_task.setdefault(citation.plan_task_id, []).append(
            CitationDetail(
                citation_id=citation.citation_id,
                plan_task_id=citation.plan_task_id,
                citation_order=citation.citation_order,
                version_id=version_id,
                document_id=document_id,
                document_title=title,
                document_url=source_url,
                chunk_id=citation.chunk_id,
                citation_note=citation.citation_note,
                section_path=section_path,
                content_snippet=_plain_text_snippet(chunk_content) or None,
            )
        )
    return citations_by_task


async def list_task_details(db: AsyncSession, plan_id: int) -> list[PlanTaskDetail]:
    """Task + category + nguồn, join sẵn 1 lượt.

    `category`/`estimated_minutes` phải join qua TemplateTask vì PlanTask không lưu 2 field này —
    đúng thiết kế gốc (SoT §24.4 "không trộn TemplateTask với PlanTask"), nhưng FE cần chúng để gom
    nhóm hiển thị nên gộp vào response thay vì bắt FE gọi thêm API template.
    """
    rows = (
        await db.execute(
            select(PlanTask, TemplateTask.category, TemplateTask.estimated_minutes)
            .join(TemplateTask, TemplateTask.template_task_id == PlanTask.template_task_id)
            .where(PlanTask.plan_id == plan_id)
            .order_by(PlanTask.display_order)
        )
    ).all()

    source_rows = (
        await db.execute(
            select(
                PlanTaskSource,
                KnowledgeDocument.document_id,
                KnowledgeDocument.title,
                KnowledgeDocument.source_url,
                DocumentChunk.section_path,
                DocumentChunk.anchor,
            )
            .join(DocumentVersion, DocumentVersion.version_id == PlanTaskSource.version_id)
            .join(KnowledgeDocument, KnowledgeDocument.document_id == DocumentVersion.document_id)
            .join(PlanTask, PlanTask.plan_task_id == PlanTaskSource.plan_task_id)
            # outerjoin: nguồn không trích đoạn cụ thể (baseline / plan cũ) vẫn phải xuất hiện.
            .outerjoin(DocumentChunk, DocumentChunk.chunk_id == PlanTaskSource.chunk_id)
            .where(PlanTask.plan_id == plan_id)
        )
    ).all()

    sources_by_task: dict[int, list[SourceDetail]] = {}
    for source, document_id, title, source_url, section_path, anchor in source_rows:
        sources_by_task.setdefault(source.plan_task_id, []).append(
            SourceDetail(
                task_source_id=source.task_source_id,
                plan_task_id=source.plan_task_id,
                version_id=source.version_id,
                document_id=document_id,
                document_title=title,
                document_url=source_url,
                citation_note=source.citation_note,
                chunk_id=source.chunk_id,
                section_path=section_path,
                anchor=anchor,
            )
        )

    citations_by_task = await list_task_citations(db, plan_id)

    details: list[PlanTaskDetail] = []
    # `rows` đã sort theo display_order (câu SELECT ở trên) — chạy 1 lượt, nhớ due_at của task
    # trước để làm start_at cho task sau, khớp đúng cách compute_due_dates() sinh ra chúng.
    previous_due_at = None
    for task, category, estimated_minutes in rows:
        if previous_due_at is not None:
            start_at = previous_due_at
        elif task.due_at is not None:
            # Task đầu tiên: chưa có task nào đứng trước để lấy due_at, suy ngược từ due_at của
            # chính nó — xem giải thích đầy đủ ở docstring field `start_at` trên `PlanTaskDetail`.
            start_at = task.due_at - timedelta(minutes=estimated_minutes)
        else:
            start_at = None
        details.append(
            PlanTaskDetail(
                task=task,
                category=category,
                estimated_minutes=estimated_minutes,
                sources=sources_by_task.get(task.plan_task_id, []),
                citations=citations_by_task.get(task.plan_task_id, []),
                start_at=start_at,
            )
        )
        previous_due_at = task.due_at
    return details


async def update_task(db: AsyncSession, plan_task_id: int, dto: UpdatePlanTaskRequestDTO) -> PlanTask:
    """PM sửa tay nội dung task. Chỉ cho sửa khi plan còn DRAFT — plan đã duyệt là snapshot Engineer
    đang chạy theo, sửa ngầm sẽ làm họ đọc một đằng làm một nẻo (SoT rule 11)."""
    task = await db.get(PlanTask, plan_task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task không tồn tại")

    plan = await db.get(OnboardingPlan, task.plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan của task không tồn tại")
    if plan.status != PlanStatus.DRAFT:
        raise HTTPException(
            status_code=409,
            detail=f"Plan đã ở trạng thái {plan.status.value} — chỉ sửa được task khi plan còn Nháp",
        )

    if dto.title is not None:
        task.title = dto.title
    if dto.instruction is not None:
        task.instruction = dto.instruction
    if dto.due_at is not None:
        task.due_at = dto.due_at

    await db.commit()
    await db.refresh(task)
    return task
