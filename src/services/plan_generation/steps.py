"""5 bước nghiệp vụ deterministic của pipeline sinh Candidate Plan.

Cố ý KHÔNG có LLM ở đây — SoT §24.5 "không gọi LLM cho validation/state transition deterministic".
Bước duy nhất gọi LLM là `generate_content` (xem content_llm.py). Nhờ tách vậy, 5 bước này test
được bằng pytest thường, không cần mock mạng, không có tính ngẫu nhiên.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.model.document_version import DocumentVersion
from src.model.enums import (
    DocumentCategory,
    DocumentDomain,
    DocumentStatus,
    PolicyCategory,
    TaskCategory,
    TemplateVersionStatus,
    VersionStatus,
)
from src.model.knowledge_document import KnowledgeDocument
from src.model.onboarding_template import OnboardingTemplate
from src.model.project_membership import ProjectMembership
from src.model.task_dependency import TaskDependency
from src.model.template_task import TemplateTask
from src.model.template_version import TemplateVersion

# Map nhóm task -> nhóm tài liệu được phép đọc. Cố định bằng code, KHÔNG để LLM tự đoán: đây là
# quyết định nghiệp vụ (task "Cài đặt môi trường" phải đọc tài liệu SETUP), không phải việc suy luận.
#
# Chỉ có 5 nhóm task vì template của project vốn đã bị lọc bỏ CONVENTION/FIRST_TASK/FIRST_PR từ
# Phase 2 (`template_version_service.create_version` lọc theo DEFERRED_TASK_CATEGORIES). Khi nào mở
# rộng 3 nhóm đó thì thêm dòng vào đây, không phải đổi kiến trúc.
TASK_CATEGORY_DOCUMENT_MAP: dict[TaskCategory, tuple[DocumentCategory, ...]] = {
    TaskCategory.ORIENTATION: (DocumentCategory.OVERVIEW,),
    TaskCategory.ARCHITECTURE: (DocumentCategory.ARCHITECTURE,),
    TaskCategory.ACCESS: (DocumentCategory.ACCESS_SECURITY,),
    TaskCategory.SETUP: (DocumentCategory.SETUP,),
    TaskCategory.CODEBASE: (DocumentCategory.CODEBASE_GUIDE,),
}

# Nhóm task nào được đọc thêm Company Core (tài liệu POLICY dùng chung mọi project).
TASK_CATEGORY_POLICY_MAP: dict[TaskCategory, tuple[PolicyCategory, ...] | None] = {
    # COMPANY là nhóm "Tìm hiểu công ty" — nguồn DUY NHẤT của nó là policy (None = không lọc theo
    # policy_category, đọc hết nội quy/phúc lợi/bảo mật). Cố tình không có mặt trong
    # TASK_CATEGORY_DOCUMENT_MAP vì nhóm này không đọc tài liệu riêng của dự án.
    #
    # Trước đây ORIENTATION cũng đọc toàn bộ policy (None) — tạm gắn khi chưa có category COMPANY
    # riêng. Đã bỏ: giờ COMPANY là nơi DUY NHẤT đọc toàn bộ policy, để ORIENTATION đọc thêm policy
    # nữa sẽ lẫn nguồn (task "Đọc tài liệu Overview" hiện cả nguồn không liên quan tới Overview).
    TaskCategory.COMPANY: None,
    TaskCategory.ACCESS: (PolicyCategory.SECURITY_POLICY,),
}

WORK_MINUTES_PER_DAY = 8 * 60


@dataclass
class DocumentRef:
    """1 tài liệu ACTIVE dùng được làm nguồn — gói sẵn version_id để ghi PlanTaskSource."""

    document_id: int
    version_id: int
    title: str
    knowledge_domain: DocumentDomain
    document_category: DocumentCategory | None
    policy_category: PolicyCategory | None


@dataclass
class TaskPlanInput:
    """1 TemplateTask + đúng bộ tài liệu nó được phép tham chiếu."""

    template_task: TemplateTask
    allowed_documents: list[DocumentRef]


@dataclass
class GenerationContext:
    """`membership is None` = đang sinh BẢN CHUẨN cấp dự án (không gắn kỹ sư nào).
    Đây là tín hiệu duy nhất phân biệt 2 luồng, không cần thêm cờ riêng."""

    membership: ProjectMembership | None
    project_id: int
    template_version: TemplateVersion
    template_tasks: list[TemplateTask]
    dependencies: list[TaskDependency]
    policy_documents: list[DocumentRef] = field(default_factory=list)
    project_documents: list[DocumentRef] = field(default_factory=list)
    task_inputs: list[TaskPlanInput] = field(default_factory=list)


async def _active_documents(
    db: AsyncSession, *, domain: DocumentDomain, project_id: int | None
) -> list[DocumentRef]:
    """Tài liệu dùng được cho plan = document ACTIVE + version ACTIVE (SoT rule 7: "chỉ version
    ACTIVE được dùng cho plan generation và RAG"). Version PROCESSING/FAILED bị loại ở đây."""
    statement = (
        select(KnowledgeDocument, DocumentVersion)
        .join(DocumentVersion, DocumentVersion.document_id == KnowledgeDocument.document_id)
        .where(
            KnowledgeDocument.knowledge_domain == domain,
            KnowledgeDocument.status == DocumentStatus.ACTIVE,
            DocumentVersion.status == VersionStatus.ACTIVE,
        )
        .order_by(KnowledgeDocument.document_id)
    )
    statement = (
        statement.where(KnowledgeDocument.project_id == project_id)
        if domain == DocumentDomain.PROJECT
        else statement.where(KnowledgeDocument.project_id.is_(None))
    )
    rows = (await db.execute(statement)).all()
    return [
        DocumentRef(
            document_id=document.document_id,
            version_id=version.version_id,
            title=document.title,
            knowledge_domain=document.knowledge_domain,
            document_category=document.document_category,
            policy_category=document.policy_category,
        )
        for document, version in rows
    ]


async def load_template_for_project(db: AsyncSession, project_id: int) -> GenerationContext:
    """Bước 1 (bản chuẩn) — tìm TemplateVersion APPROVED của project rồi nạp task + dependency.

    Không cần membership: bản chuẩn là tài sản của dự án, không thuộc kỹ sư nào. `load_template`
    bên dưới chỉ là lớp mỏng gắn thêm membership vào context này.
    """
    template = await db.scalar(
        select(OnboardingTemplate).where(OnboardingTemplate.project_id == project_id)
    )
    if template is None:
        raise HTTPException(
            status_code=422,
            detail="Project chưa có Master Template — cần tạo template trước khi sinh plan",
        )

    version = await db.scalar(
        select(TemplateVersion).where(
            TemplateVersion.template_id == template.template_id,
            TemplateVersion.status == TemplateVersionStatus.APPROVED,
        )
    )
    if version is None:
        # Không tạo plan rỗng âm thầm (SoT rule 16) — báo lỗi để PM đi duyệt template trước.
        raise HTTPException(
            status_code=422,
            detail="Master Template của project chưa có version nào được duyệt (APPROVED) — "
            "vào Master Template duyệt 1 version rồi quay lại tạo plan",
        )

    tasks = list(
        (
            await db.scalars(
                select(TemplateTask)
                .where(TemplateTask.version_id == version.version_id)
                .order_by(TemplateTask.display_order)
            )
        ).all()
    )
    if not tasks:
        raise HTTPException(status_code=422, detail="TemplateVersion đã duyệt nhưng không có task nào")

    task_ids = {task.template_task_id for task in tasks}
    dependencies = list(
        (
            await db.scalars(
                select(TaskDependency).where(TaskDependency.predecessor_task_id.in_(task_ids))
            )
        ).all()
    )

    return GenerationContext(
        membership=None,
        project_id=project_id,
        template_version=version,
        template_tasks=tasks,
        dependencies=[d for d in dependencies if d.successor_task_id in task_ids],
    )


async def load_template(db: AsyncSession, membership_id: int) -> GenerationContext:
    """Bước 1 (plan của kỹ sư) — như trên nhưng gắn thêm membership.

    `project_id` lấy từ membership TRONG DB, không nhận từ client (SoT §19: "kiểm tra membership ở
    backend, không tin projectId từ frontend").
    """
    membership = await db.get(ProjectMembership, membership_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="Membership không tồn tại")

    context = await load_template_for_project(db, membership.project_id)
    context.membership = membership
    return context


async def merge_company_core(db: AsyncSession, context: GenerationContext) -> GenerationContext:
    """Bước 2 — nạp Company Core (POLICY). Số lượng là kết quả query sống, không hardcode."""
    context.policy_documents = await _active_documents(db, domain=DocumentDomain.POLICY, project_id=None)
    return context


async def collect_project_docs(db: AsyncSession, context: GenerationContext) -> GenerationContext:
    """Bước 3 — nạp tài liệu của ĐÚNG project. project_id lấy từ membership trong DB, không nhận từ
    client (SoT §19 "không tin projectId từ frontend")."""
    documents = await _active_documents(
        db, domain=DocumentDomain.PROJECT, project_id=context.project_id
    )
    used_categories = {c for values in TASK_CATEGORY_DOCUMENT_MAP.values() for c in values}
    # Bỏ tài liệu thuộc nhóm đang hoãn (CONVENTION/FIRST_TASK) — chúng vẫn nằm trong DB và vẫn hợp
    # lệ, chỉ là chưa có nhóm task nào tiêu thụ nên không đưa vào ngữ cảnh sinh nội dung.
    context.project_documents = [d for d in documents if d.document_category in used_categories]
    return context


def map_task_sources(context: GenerationContext) -> GenerationContext:
    """Bước 4 — ghép mỗi task với đúng bộ tài liệu được phép đọc."""
    project_by_category: dict[DocumentCategory, list[DocumentRef]] = {}
    for document in context.project_documents:
        if document.document_category is not None:
            project_by_category.setdefault(document.document_category, []).append(document)

    task_inputs: list[TaskPlanInput] = []
    for task in context.template_tasks:
        allowed: list[DocumentRef] = []
        for category in TASK_CATEGORY_DOCUMENT_MAP.get(task.category, ()):
            allowed.extend(project_by_category.get(category, []))

        if task.category in TASK_CATEGORY_POLICY_MAP:
            policy_filter = TASK_CATEGORY_POLICY_MAP[task.category]
            allowed.extend(
                document
                for document in context.policy_documents
                if policy_filter is None or document.policy_category in policy_filter
            )
        task_inputs.append(TaskPlanInput(template_task=task, allowed_documents=allowed))

    context.task_inputs = task_inputs
    return context


def compute_due_dates(context: GenerationContext, start: datetime | None = None) -> dict[int, datetime]:
    """Mốc deadline từng task = cộng dồn estimated_minutes theo display_order, quy đổi 8h/ngày làm
    việc và nhảy qua T7/CN. Deterministic hoàn toàn — không nhờ LLM ước lượng thời gian.

    `start` truyền vào thì dùng nguyên (PM chọn giờ bắt đầu ở modal khi cấp plan cho kỹ sư — xem
    `onboarding_plan_router.generate_candidate_plan`); không truyền thì mặc định giờ gọi hàm.
    """
    current = start or datetime.now(UTC).replace(tzinfo=None)
    result: dict[int, datetime] = {}
    remaining_today = WORK_MINUTES_PER_DAY

    for task in sorted(context.template_tasks, key=lambda t: t.display_order):
        minutes = max(task.estimated_minutes, 0)
        while minutes > remaining_today:
            minutes -= remaining_today
            current += timedelta(days=1)
            while current.weekday() >= 5:  # 5=T7, 6=CN
                current += timedelta(days=1)
            remaining_today = WORK_MINUTES_PER_DAY
        # BUG cũ: thiếu đúng dòng này — `current` đứng yên suốt cả ngày làm việc, nên MỌI task
        # chưa tràn 480 phút/ngày nhận cùng 1 giờ hạn (= giờ sinh plan), và bị "Trễ hẹn" ngay khi
        # vừa tạo vì hạn trùng thời điểm hiện tại. Advance đúng bằng phần phút vừa "tiêu" trong ngày.
        current += timedelta(minutes=minutes)
        remaining_today -= minutes
        result[task.template_task_id] = current
    return result


def validate_generated(context: GenerationContext, contents: dict[int, object]) -> list[str]:
    """Bước 6 (phần kiểm tra) — trả về danh sách cảnh báo; ném lỗi nếu vi phạm bất biến cứng."""
    warnings: list[str] = []

    # Rule 10 SoT: "Agent không được xóa task mandatory".
    mandatory_ids = {t.template_task_id for t in context.template_tasks if t.mandatory}
    missing = mandatory_ids - set(contents.keys())
    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline làm mất {len(missing)} task bắt buộc — huỷ, không lưu plan lỗi",
        )

    orders = [t.display_order for t in context.template_tasks]
    if len(set(orders)) != len(orders):
        raise HTTPException(status_code=422, detail="TemplateVersion có display_order trùng nhau")

    graph: dict[int, list[int]] = {}
    for dependency in context.dependencies:
        graph.setdefault(dependency.predecessor_task_id, []).append(dependency.successor_task_id)
    if _has_cycle(graph):
        raise HTTPException(status_code=422, detail="Dependency graph có chu trình, không sinh plan được")

    for task_input in context.task_inputs:
        if not task_input.allowed_documents:
            warnings.append(
                f"Task '{task_input.template_task.title_pattern}' chưa có tài liệu nguồn nào"
            )
    return warnings


def _has_cycle(graph: dict[int, list[int]]) -> bool:
    """Copy đúng thuật toán DFS 3 màu đã dùng ở template_version_service._has_cycle — giữ nguyên
    hành vi kiểm tra dependency giữa 2 nơi, không import chéo service để tránh phụ thuộc vòng."""
    white, gray, black = 0, 1, 2
    color: dict[int, int] = {}

    def visit(node: int) -> bool:
        color[node] = gray
        for neighbor in graph.get(node, []):
            state = color.get(neighbor, white)
            if state == gray:
                return True
            if state == white and visit(neighbor):
                return True
        color[node] = black
        return False

    return any(color.get(node, white) == white and visit(node) for node in list(graph.keys()))
