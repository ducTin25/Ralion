"""Bước 5 — sinh nội dung hướng dẫn cho từng PlanTask.

Đây là bước DUY NHẤT trong pipeline gọi LLM. Có 3 nguồn nội dung, pipeline chọn theo thứ tự ưu tiên
`load_reference_content` → `generate_ai_content` → `generate_baseline_content`:

- `load_reference_content` — **sao chép từ Plan chuẩn đã có** của cùng (project, template_version).
  Chạy trước tiên và KHÔNG gọi LLM: kỹ sư cùng dự án phải nhận nội dung giống nhau (SoT §12), nên
  sinh lại bằng AI cho từng người vừa tốn tiền vừa cho ra nội dung lệch nhau.
- `generate_ai_content` — bản AI, chỉ chạy cho kỹ sư ĐẦU TIÊN của dự án.
- `generate_baseline_content` — **baseline B0** (không AI), mốc so sánh mà `docs/PM/plan-pm.md` §4.1
  định nghĩa, dùng để chứng minh AI có thật sự tạo giá trị hay không.

## Bao phủ tài liệu là bất biến của CODE, không phải lời hứa của LLM

Trước đây pipeline tra BM25 1 câu rồi lấy top-K đoạn: tài liệu nào ít từ khoá trùng câu truy vấn sẽ
rớt khỏi kết quả và biến mất khỏi lộ trình (PM test thật: nhóm 18 tài liệu chính sách chỉ ra 4 nguồn).
Nay đổi hẳn cách làm:

1. `_collect_outlines` đọc TOÀN BỘ đoạn của TỪNG tài liệu trong `allowed_documents` (không xếp hạng,
   không cắt).
2. `_batch_documents` chia thành lô nhỏ theo ngân sách đoạn — đây là chỗ DUY NHẤT khống chế kích
   thước prompt, thay cho việc cắt bớt tài liệu.
3. Mỗi lô là 1 lời gọi LLM riêng (chạy song song, chặn bằng semaphore), LLM chỉ trả JSON từng đoạn
   (`summary` + `quote`) chứ không tự viết khung markdown.
4. `_build_sources_section` RÁP BẰNG CODE: lặp qua từng tài liệu → từng đoạn, đoạn nào LLM không tóm
   tắt được thì tự ghi `UNSUMMARIZED_CHUNK_NOTE` và vẫn giữ trích dẫn trỏ đúng đoạn đó.

## `generate_ai_content` chạy theo 3 PHA (xem docs/PM/Phase-4/plan-optimize-plan-generation-perf.md)

- **Pha A (`_phase_a_collect`)** — tuần tự, CHỈ đọc DB. Đọc outline cho mọi task, nhớ theo
  `version_id` để 2 task cùng đọc 1 tài liệu không truy vấn 2 lần. Kết thúc pha này là hết đụng DB.
- **Pha B (`_phase_b_evidence_cards`)** — song song, CHỈ gọi LLM. Gom `chunk_id` DUY NHẤT của toàn
  bộ lượt sinh rồi mới chia lô: 1 đoạn được tóm tắt đúng 1 lần dù bao nhiêu task cùng đọc nó (bản cũ
  tóm tắt lại từ đầu cho từng task). Dedup TRƯỚC khi gọi, không phải chống gọi trùng lúc chạy.
- **Pha C (`_phase_c_task_content`)** — song song, CHỈ gọi LLM. Mỗi task tự đánh lại số `[n]` cục bộ
  của riêng mình từ Evidence Card tra theo `chunk_id`. Vì số `[n]` KHÔNG nằm trong card, 1 card dùng
  chung cho nhiều task không thể làm lệch số trích dẫn.

Tách pha A ra trước là điều kiện để pha B/C chạy song song an toàn: `AsyncSession` không dùng đồng
thời được, nên mọi truy vấn phải xong trước khi mở song song.

Nhờ (4), mọi tài liệu và mọi đoạn chắc chắn xuất hiện — không phụ thuộc LLM có nhớ liệt kê đủ không.
Cũng nhờ vậy nhánh baseline (không AI) dùng CHUNG hàm ráp này, chỉ khác là không có câu tóm tắt.

Bật/tắt AI: `Settings.plan_generation_use_ai`. Thiếu API key → tự rơi về baseline, không crash.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.model.enums import DocumentDomain, PolicyCategory
from src.observability import get_langchain_callbacks
from src.services.plan_generation import prompts
from src.services.plan_generation.steps import DocumentRef, GenerationContext, TaskPlanInput
from src.services.plan_generation.text_verification import verified_substring
from src.services.plan_generation.tools import ChunkHit, fetch_all_document_chunks

logger = logging.getLogger(__name__)

MAX_CHUNK_CHARS = 1200
# Trần cho 1 Evidence Card. `summary` giữ đúng mức cũ (1 dòng ~30 từ) vì nó render thành 1 gạch đầu
# dòng cho MỖI đoạn trong "Tài liệu nguồn cần đọc" — nới lên vài trăm từ thì mục nguồn của nhóm
# COMPANY (hàng trăm đoạn) sẽ dài không đọc nổi. `quote` mới là thứ cần đủ dài để trích dẫn có nghĩa.
MAX_SUMMARY_WORDS = 30
MAX_QUOTE_CHARS = 240
# Ngân sách đoạn cho 1 lời gọi LLM. Đây là chỗ DUY NHẤT khống chế kích thước prompt — tài liệu không
# bao giờ bị cắt bớt, chỉ bị chia thành nhiều lô.
MAX_CHUNKS_PER_BATCH = 10
# Số lời gọi LLM chạy song song tối đa. Nhóm COMPANY có thể sinh ra hàng chục lô; thả `asyncio.gather`
# tự do sẽ bắn hết cùng lúc và ăn rate limit của nhà cung cấp.
MAX_CONCURRENT_LLM_CALLS = 4

# Nhãn nhóm chính sách — khớp đúng `POLICY_CATEGORY_META` bên frontend để PM đọc thấy cùng một tên ở
# Master Template lẫn trong nội dung task.
POLICY_CATEGORY_LABELS: dict[PolicyCategory, str] = {
    PolicyCategory.COMPANY_POLICY: "Chính sách chung công ty",
    PolicyCategory.HR_POLICY: "Chính sách nhân sự",
    PolicyCategory.SECURITY_POLICY: "Chính sách bảo mật",
    PolicyCategory.BENEFIT: "Phúc lợi",
    PolicyCategory.WORKING_RULE: "Quy tắc làm việc",
    PolicyCategory.GENERAL: "Chính sách khác",
}
# Thứ tự hiển thị nhóm chính sách, cố định để 2 lần sinh plan ra cùng thứ tự (dễ so sánh khi eval).
POLICY_CATEGORY_ORDER: tuple[PolicyCategory, ...] = (
    PolicyCategory.COMPANY_POLICY,
    PolicyCategory.HR_POLICY,
    PolicyCategory.SECURITY_POLICY,
    PolicyCategory.BENEFIT,
    PolicyCategory.WORKING_RULE,
    PolicyCategory.GENERAL,
)


@dataclass(frozen=True)
class SourceRef:
    """1 nguồn sẽ ghi thành `PlanTaskSource` — mức TÀI LIỆU (1 dòng = 1 tài liệu cần đọc).

    Giữ nguyên ngữ nghĩa cũ vì Member Portal (`member_onboarding_service._task_sources()`) đang đọc
    thẳng bảng này; chi tiết theo từng đoạn nằm ở `CitationRef` bên dưới.

    `chunk_id` giữ lại cho tương thích ngược với plan sinh trước khi có bảng citation.
    """

    version_id: int
    citation_note: str | None
    chunk_id: int | None = None


@dataclass(frozen=True)
class CitationRef:
    """1 trích dẫn `[n]` — mức ĐOẠN, sẽ ghi thành `PlanTaskCitation`.

    `citation_order` chính là số `[n]` hiển thị trong nội dung, đánh số toàn cục trong 1 task.
    """

    version_id: int
    chunk_id: int
    citation_order: int
    citation_note: str | None


@dataclass
class TaskContent:
    title: str
    instruction: str
    sources: list[SourceRef] = field(default_factory=list)
    citations: list[CitationRef] = field(default_factory=list)
    generated_by_ai: bool = False
    # True = nội dung sao chép từ Plan chuẩn, không sinh mới. Tách riêng khỏi `generated_by_ai` để
    # job/log nói đúng sự thật: nội dung này GỐC do AI viết, nhưng lần tạo plan NÀY không gọi AI.
    cloned: bool = False


@dataclass
class DocumentOutline:
    """1 tài liệu + TOÀN BỘ đoạn của nó (không xếp hạng, không cắt)."""

    document: DocumentRef
    chunks: list[ChunkHit]


@dataclass
class LlmUsage:
    """Gom số lời gọi + token của 1 lượt sinh plan để tự tính chi phí.

    Vì sao phải tự đếm thay vì đọc trên Langfuse: model đi qua `base_url` riêng của DeepSeek, không
    nằm trong bảng giá dựng sẵn của Langfuse nên cột cost ở dashboard hiện 0 dù token vẫn đúng. Số
    ở đây ghi thẳng vào log có cấu trúc, đủ để so trước/sau khi tối ưu mà không phụ thuộc dashboard.

    Cộng dồn không cần khoá: mọi lần cộng đều nằm trong code đồng bộ giữa 2 lần `await`, mà event
    loop chỉ chuyển coroutine tại `await` — không có 2 coroutine nào cộng xen kẽ nhau được.
    """

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def record(self, response) -> None:
        self.calls += 1
        metadata = getattr(response, "response_metadata", {}) or {}
        counts = metadata.get("token_usage") or getattr(response, "usage_metadata", {}) or {}
        if not isinstance(counts, dict):
            return
        self.input_tokens += int(counts.get("prompt_tokens") or counts.get("input_tokens") or 0)
        self.output_tokens += int(counts.get("completion_tokens") or counts.get("output_tokens") or 0)

    def estimated_usd(self) -> float:
        settings = get_settings()
        return round(
            self.input_tokens / 1_000_000 * settings.deepseek_input_usd_per_mtok
            + self.output_tokens / 1_000_000 * settings.deepseek_output_usd_per_mtok,
            6,
        )


@dataclass(frozen=True)
class EvidenceCard:
    """Kết quả xử lý 1 ĐOẠN tài liệu, dùng chung cho mọi task cùng đọc đoạn đó.

    Cố ý KHÔNG chứa `citation_order`: số `[n]` là thứ tự cục bộ trong 1 task, task khác đọc cùng đoạn
    sẽ ra số khác. Nhét số vào card rồi tái sử dụng card giữa các task chính là cách làm hỏng trích
    dẫn — số `[n]` luôn được từng task tự đánh lại ở `_build_sources_section`.

    `exact_quote is None` = LLM không trả quote, hoặc quote trả về KHÔNG khớp nguyên văn tài liệu và
    đã bị máy chủ loại. Vẫn giữ `summary` để đoạn đó không biến mất khỏi mục nguồn.
    """

    chunk_id: int
    summary: str | None
    exact_quote: str | None


@dataclass
class ChunkBatch:
    """1 lô đoạn gửi cho đúng 1 lời gọi LLM.

    `offset` = số đoạn của tất cả lô đứng trước — chỉ còn là thông tin vị trí để đọc log/test cho dễ.
    Từ khi chuyển sang Evidence Card, kết quả được tra theo `chunk_id` nên KHÔNG còn phép quy đổi
    `[k]` cục bộ → `[n]` toàn cục bằng offset nữa (chính phép cộng đó là chỗ dễ gán nhầm số trích dẫn
    khi 1 lô được dùng lại cho task có danh sách tài liệu khác).
    """

    chunks: list[ChunkHit]
    offset: int


async def load_reference_content(db: AsyncSession, reference_plan_id: int) -> dict[int, TaskContent]:
    """Đọc nội dung Plan chuẩn, trả về đúng dạng `dict[template_task_id, TaskContent]` giống 2 hàm
    sinh nội dung kia — nhờ vậy `persist_generated_plan()` không cần biết nội dung đến từ đâu.

    Khoá theo `template_task_id` (không phải `plan_task_id`) vì đó là thứ chung giữa 2 plan: plan mới
    có `plan_task_id` riêng, nhưng cùng tham chiếu về đúng TemplateTask của cùng TemplateVersion.
    """
    from src.model.plan_task import PlanTask
    from src.model.plan_task_citation import PlanTaskCitation
    from src.model.plan_task_source import PlanTaskSource

    tasks = list(
        (
            await db.scalars(
                select(PlanTask).where(PlanTask.plan_id == reference_plan_id).order_by(PlanTask.display_order)
            )
        ).all()
    )
    if not tasks:
        return {}

    task_ids = [t.plan_task_id for t in tasks]
    sources = list(
        (await db.scalars(select(PlanTaskSource).where(PlanTaskSource.plan_task_id.in_(task_ids)))).all()
    )
    sources_by_task: dict[int, list[SourceRef]] = {}
    for source in sources:
        sources_by_task.setdefault(source.plan_task_id, []).append(
            SourceRef(
                version_id=source.version_id,
                citation_note=source.citation_note,
                chunk_id=source.chunk_id,
            )
        )

    # Trích dẫn phải sao chép kèm, nếu không plan của kỹ sư sẽ có `[n]` trong nội dung mà không có
    # bản ghi nào để bấm mở — nội dung và trích dẫn luôn đi cùng nhau.
    citation_rows = list(
        (
            await db.scalars(
                select(PlanTaskCitation)
                .where(PlanTaskCitation.plan_task_id.in_(task_ids))
                .order_by(PlanTaskCitation.citation_order)
            )
        ).all()
    )
    version_by_source_id = {source.task_source_id: source.version_id for source in sources}
    citations_by_task: dict[int, list[CitationRef]] = {}
    for citation in citation_rows:
        citations_by_task.setdefault(citation.plan_task_id, []).append(
            CitationRef(
                version_id=version_by_source_id[citation.task_source_id],
                chunk_id=citation.chunk_id,
                citation_order=citation.citation_order,
                citation_note=citation.citation_note,
            )
        )

    return {
        task.template_task_id: TaskContent(
            title=task.title,
            instruction=task.instruction,
            sources=sources_by_task.get(task.plan_task_id, []),
            citations=citations_by_task.get(task.plan_task_id, []),
            generated_by_ai=False,
            cloned=True,
        )
        for task in tasks
    }


def _citations_within_range(instruction: str, source_count: int) -> bool:
    """Mọi `[n]` trong nội dung phải trỏ tới nguồn CÓ THẬT đã đưa vào prompt.

    LLM đôi khi bịa số thứ tự (vd `[7]` khi chỉ có 3 nguồn) — trích dẫn kiểu đó vô nghĩa với người
    đọc và không mở được đoạn nào. Bắt ở đây để rơi về nội dung không-AI thay vì phát hành 1 plan
    trích dẫn sai.
    """
    return all(1 <= int(number) <= source_count for number in re.findall(r"\[(\d+)\]", instruction))


def _no_evidence_instruction(task, notice: str) -> str:
    """Nội dung cho task KHÔNG có bằng chứng từ tài liệu.

    Cố ý KHÔNG đổ `instruction_template` ra như hướng dẫn thật: đó là khung mẫu PM soạn trong Master
    Template, không phải nội dung rút từ tài liệu dự án. Trình bày nó dưới tiêu đề "Các bước thực
    hiện" khiến PM tưởng task đã có hướng dẫn được tài liệu xác nhận (đúng lỗi đã phát hiện khi test
    thật: task hiện "TÀI LIỆU NGUỒN (0)" mà vẫn có đủ Mục tiêu/Các bước).
    """
    return (
        f"## Trạng thái\n{notice}\n\n"
        f"## Mục tiêu (tham khảo — chưa được tài liệu xác nhận)\n{task.objective.strip()}\n"
    )


def _document_sources(task_input: TaskPlanInput) -> list[SourceRef]:
    """Mức tài liệu: MỌI tài liệu được phép đọc đều thành 1 nguồn, không cắt bớt theo trần nào.

    Trần cũ (`MAX_SOURCES_PER_TASK`) là nguyên nhân trực tiếp khiến nhóm 18 tài liệu chính sách chỉ
    hiện 4 nguồn — bỏ hẳn, giới hạn chi phí chuyển sang tầng chia lô.
    """
    return [
        SourceRef(version_id=document.version_id, citation_note=document.title)
        for document in task_input.allowed_documents
    ]


async def _collect_outlines(db: AsyncSession, task_input: TaskPlanInput) -> list[DocumentOutline]:
    """Đọc toàn bộ đoạn của TỪNG tài liệu được phép đọc, giữ nguyên thứ tự tài liệu ở bước 4."""
    outlines: list[DocumentOutline] = []
    for document in task_input.allowed_documents:
        chunks = await fetch_all_document_chunks(db, version_id=document.version_id)
        outlines.append(DocumentOutline(document=document, chunks=chunks))
    return outlines


def _ordered_outlines(outlines: list[DocumentOutline]) -> list[DocumentOutline]:
    """Sắp tài liệu POLICY theo đúng thứ tự 5 nhóm chính sách; tài liệu dự án giữ nguyên thứ tự.

    Sắp ở đây (chứ không lúc hiển thị) để thứ tự tài liệu, thứ tự lô, và thứ tự đánh số `[n]` luôn
    khớp nhau — điều kiện để quy đổi `[k]` cục bộ sang `[n]` toàn cục bằng phép cộng offset.
    """
    if not any(d.document.knowledge_domain == DocumentDomain.POLICY for d in outlines):
        return outlines

    def sort_key(outline: DocumentOutline) -> tuple[int, int]:
        policy_category = outline.document.policy_category
        group = (
            POLICY_CATEGORY_ORDER.index(policy_category)
            if policy_category in POLICY_CATEGORY_ORDER
            else len(POLICY_CATEGORY_ORDER)
        )
        return (group, outline.document.document_id)

    return sorted(outlines, key=sort_key)


def _batch_documents(
    outlines: list[DocumentOutline], *, max_chunks_per_batch: int = MAX_CHUNKS_PER_BATCH
) -> list[ChunkBatch]:
    """Chia toàn bộ đoạn thành các lô ≤ `max_chunks_per_batch` đoạn.

    2 ràng buộc, đều xuất phát từ yêu cầu nghiệp vụ chứ không phải tối ưu kỹ thuật:
    - KHÔNG trộn 2 nhóm chính sách trong cùng 1 lô: mỗi nhóm được tóm tắt trong ngữ cảnh riêng, nhóm
      nhỏ (vd BENEFIT chỉ 1 tài liệu) không bị lời văn của nhóm lớn lấn át.
    - Tài liệu dài hơn ngân sách KHÔNG bị cắt: tự tách thành nhiều lô liên tiếp, phần đuôi vẫn được
      tóm tắt đầy đủ.
    """
    batches: list[ChunkBatch] = []
    current: list[ChunkHit] = []
    current_group: PolicyCategory | None = None
    offset = 0

    def flush() -> None:
        nonlocal current, offset
        if current:
            batches.append(ChunkBatch(chunks=current, offset=offset))
            offset += len(current)
            current = []

    for outline in outlines:
        group = outline.document.policy_category
        if current and group != current_group:
            flush()
        current_group = group
        for chunk in outline.chunks:
            if len(current) >= max_chunks_per_batch:
                flush()
            current.append(chunk)
    flush()
    return batches


def _build_chunks_block(batch: ChunkBatch) -> str:
    """Đưa thẳng `chunk_id` thật cho LLM đối chiếu — giống hợp đồng bên chat
    (`AnswerGenerator._prompt`), nhờ vậy kết quả tra được theo `chunk_id` mà không phụ thuộc thứ tự
    trả về của LLM. Bản cũ đánh số cục bộ 1..N rồi cộng offset để ra số toàn cục; cách đó chỉ đúng
    khi lô được dùng cho đúng 1 task."""
    blocks = []
    for chunk in batch.chunks:
        heading = f" — {chunk.heading}" if chunk.heading else ""
        blocks.append(f"chunk_id: {chunk.chunk_id}{heading}\n{chunk.content[:MAX_CHUNK_CHARS]}")
    return "\n\n".join(blocks)


def _extract_json_array(text: str) -> list:
    """Bóc mảng JSON khỏi câu trả lời, chịu được vài kiểu bọc thừa hay gặp.

    LLM đôi khi bọc ```json dù đã dặn không, hoặc thêm 1 câu dẫn trước mảng. Cắt từ '[' đầu tới ']'
    cuối là đủ để qua 2 ca đó mà không cần thư viện ngoài. Hỏng vẫn trả [] chứ không ném — lô đó coi
    như không có card, các đoạn của nó vẫn xuất hiện kèm ghi chú "chưa tóm tắt được".
    """
    cleaned = text.strip()
    left = cleaned.find("[")
    right = cleaned.rfind("]")
    if left == -1 or right <= left:
        return []
    try:
        parsed = json.loads(cleaned[left : right + 1])
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _cap_summary(text: str) -> str:
    words = text.split()
    return " ".join(words[:MAX_SUMMARY_WORDS])


def _cap_quote(quote: str) -> str:
    """Cắt theo RANH GIỚI TỪ, không cắt giữa chữ.

    Cắt cụt giữa từ vẫn là substring hợp lệ của tài liệu (nên không sai về mặt xác minh), nhưng đưa
    một câu đứt ngang vào prompt thì LLM dễ chép lại nguyên cái đứt đó vào nội dung cho người đọc.
    """
    if len(quote) <= MAX_QUOTE_CHARS:
        return quote
    cut = quote[:MAX_QUOTE_CHARS]
    space = cut.rfind(" ")
    return cut[:space] if space > 0 else cut


def _parse_evidence_cards(response_text: str, batch: ChunkBatch) -> dict[int, EvidenceCard]:
    """Đổi JSON của LLM thành card đã XÁC MINH, khoá theo `chunk_id`.

    2 lớp lọc, cả 2 đều do máy chủ nắm chứ không tin LLM:
    - `chunk_id` phải thuộc đúng lô này. LLM bịa/chép nhầm id thì bỏ, không gán nhầm sang đoạn khác.
    - `quote` phải khớp NGUYÊN VĂN nội dung đoạn (`verified_substring`). Không khớp thì bỏ RIÊNG
      quote và vẫn giữ `summary` — hỏng trích dẫn không đáng để mất luôn phần tóm tắt.
    """
    chunk_by_id = {chunk.chunk_id: chunk for chunk in batch.chunks}
    cards: dict[int, EvidenceCard] = {}
    for item in _extract_json_array(response_text):
        if not isinstance(item, dict):
            continue
        raw_id = item.get("chunk_id")
        try:
            chunk_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        chunk = chunk_by_id.get(chunk_id)
        if chunk is None or chunk_id in cards:
            continue

        summary = item.get("summary")
        summary_text = _cap_summary(str(summary).strip()) if isinstance(summary, str) else ""

        quote = item.get("quote")
        verified = (
            verified_substring(quote, chunk.content) if isinstance(quote, str) and quote.strip() else None
        )
        cards[chunk_id] = EvidenceCard(
            chunk_id=chunk_id,
            summary=summary_text or None,
            exact_quote=_cap_quote(verified) if verified else None,
        )
    return cards


async def _build_batch_cards(llm, batch: ChunkBatch, usage: LlmUsage | None = None) -> dict[int, EvidenceCard]:
    """Xử lý 1 lô. Lỗi (timeout/parse) KHÔNG làm hỏng cả task — lô đó coi như không có card, các đoạn
    của nó vẫn xuất hiện đầy đủ kèm ghi chú "chưa tóm tắt được"."""
    try:
        response = await llm.ainvoke(
            [
                ("system", prompts.EVIDENCE_CARD_SYSTEM_PROMPT),
                ("user", prompts.build_evidence_card_prompt(chunks_block=_build_chunks_block(batch))),
            ],
            config={"callbacks": get_langchain_callbacks()},
        )
    except Exception as exc:  # noqa: BLE001 - hạ cấp có kiểm soát, đã log lại
        logger.warning(
            "plan_generation: xử lý lô %s đoạn lỗi (%s) — các đoạn vẫn được liệt kê, không tóm tắt",
            len(batch.chunks),
            type(exc).__name__,
        )
        return {}

    if usage is not None:
        usage.record(response)
    cards = _parse_evidence_cards(str(response.content), batch)
    missing = len(batch.chunks) - len(cards)
    unverified = sum(1 for card in cards.values() if card.exact_quote is None)
    if missing or unverified:
        # Không im lặng: đây là tín hiệu prompt/model đang bỏ sót hoặc bịa trích dẫn, cần thấy được
        # khi đo eval chứ không để nhánh hạ cấp che mất.
        logger.info(
            "plan_generation: lô %s đoạn — thiếu %s card, %s card có quote không khớp tài liệu",
            len(batch.chunks),
            missing,
            unverified,
        )
    return cards


def _build_sources_section(
    outlines: list[DocumentOutline], cards: dict[int, EvidenceCard]
) -> tuple[str, list[CitationRef]]:
    """Ráp mục "Tài liệu nguồn cần đọc" + danh sách trích dẫn — HOÀN TOÀN BẰNG CODE.

    Đây là chỗ bảo đảm bao phủ: vòng lặp chạy qua từng tài liệu rồi từng đoạn, nên không tài liệu/đoạn
    nào biến mất được, bất kể LLM trả về gì (hay không trả gì — nhánh baseline truyền `cards` rỗng).

    Cũng là chỗ DUY NHẤT đánh số `[n]`: `order` đếm lại từ 1 theo đúng danh sách tài liệu của TASK
    NÀY. Card tra theo `chunk_id` nên dùng chung được giữa các task mà số trích dẫn vẫn riêng.

    Tài liệu POLICY được gom thêm 1 cấp tiêu đề theo nhóm chính sách, đúng như PM thấy ở Master
    Template. Dùng tối đa `###` vì bộ render markdown của app chỉ hỗ trợ tới h3.
    """
    lines: list[str] = [prompts.SOURCES_SECTION_HEADING, ""]
    citations: list[CitationRef] = []
    order = 0
    current_group: PolicyCategory | None = None
    is_policy_view = any(d.document.knowledge_domain == DocumentDomain.POLICY for d in outlines)

    for outline in outlines:
        document = outline.document
        if is_policy_view and document.policy_category != current_group:
            current_group = document.policy_category
            label = POLICY_CATEGORY_LABELS.get(current_group, "Chính sách khác")
            lines.append(f"### {label}")
            lines.append("")

        lines.append(f"**{document.title}**" if is_policy_view else f"### {document.title}")

        if not outline.chunks:
            # Tài liệu chưa được tách đoạn (ingest lỗi/chưa chạy): nói thẳng, không lờ đi cho đẹp.
            lines.append("- (tài liệu chưa có nội dung trích xuất — mở trực tiếp để đọc)")
        for chunk in outline.chunks:
            order += 1
            card = cards.get(chunk.chunk_id)
            heading = chunk.heading or document.title
            summary = card.summary if card else None
            text = summary or f"{heading} {prompts.UNSUMMARIZED_CHUNK_NOTE}"
            lines.append(f"- {text} [{order}]")
            citations.append(
                CitationRef(
                    version_id=document.version_id,
                    chunk_id=chunk.chunk_id,
                    citation_order=order,
                    citation_note=heading,
                )
            )

        lines.append(prompts.READ_FULL_DOCUMENT_NOTICE)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n", citations


def _build_evidence_block(outlines: list[DocumentOutline], cards: dict[int, EvidenceCard]) -> str:
    """Khối NGUỒN cho lời gọi viết "Các bước thực hiện".

    Khác bản cũ (`_build_citation_index_block`) ở 2 điểm, đều là điều kiện để có trích dẫn thật:
    - Có `trích:` — câu nguyên văn ĐÃ được máy chủ xác minh. Bản cũ cố ý chỉ đưa tên tài liệu + tên
      mục cho prompt nhẹ, nhưng vì thế LLM không có chữ nào của tài liệu để bám vào, nên "trích dẫn"
      chỉ là con số gắn vào câu do nó tự viết.
    - Gom theo nhóm chính sách bằng dòng `### <tên nhóm>`, khớp đúng nhóm ở mục nguồn, để nội dung
      nhóm COMPANY (đọc hết mọi POLICY) không còn là một mạch dài không phân đoạn.

    Số `[n]` ở đây đếm cùng cách với `_build_sources_section` — 2 hàm phải cho ra cùng dãy số, nếu
    lệch thì trích dẫn trong nội dung trỏ sai mục nguồn.
    """
    lines: list[str] = []
    order = 0
    current_group: PolicyCategory | None = None
    is_policy_view = any(d.document.knowledge_domain == DocumentDomain.POLICY for d in outlines)
    group_count = len({d.document.policy_category for d in outlines}) if is_policy_view else 1

    for outline in outlines:
        document = outline.document
        if is_policy_view and group_count > 1 and document.policy_category != current_group:
            current_group = document.policy_category
            lines.append(f"### {POLICY_CATEGORY_LABELS.get(current_group, 'Chính sách khác')}")

        for chunk in outline.chunks:
            order += 1
            card = cards.get(chunk.chunk_id)
            heading = f" › {chunk.heading}" if chunk.heading else ""
            lines.append(f"[{order}] {document.title}{heading}")
            if card and card.summary:
                lines.append(f"    tóm tắt: {card.summary}")
            if card and card.exact_quote:
                lines.append(f'    trích: "{card.exact_quote}"')
    return "\n".join(lines)


def _baseline_body(task) -> str:
    body = task.instruction_template.strip() or task.objective.strip()
    return f"## Mục tiêu\n{task.objective.strip()}\n\n## Các bước thực hiện\n{body}\n"


def generate_baseline_content(context: GenerationContext) -> dict[int, TaskContent]:
    """Baseline B0 — không gọi LLM, không truy xuất, hoàn toàn deterministic.

    Không có tóm tắt AI nhưng VẪN liệt kê đủ tài liệu (mức tài liệu) — dùng chung
    `_document_sources()` với nhánh AI nên số nguồn của 2 nhánh luôn khớp nhau, tiện so sánh khi eval.
    """
    contents: dict[int, TaskContent] = {}
    for task_input in context.task_inputs:
        task = task_input.template_task
        instruction = (
            _baseline_body(task)
            if task_input.allowed_documents
            else _no_evidence_instruction(task, prompts.NO_SOURCE_NOTICE)
        )
        contents[task.template_task_id] = TaskContent(
            title=task.title_pattern,
            instruction=instruction,
            sources=_document_sources(task_input),
            generated_by_ai=False,
        )
    return contents


async def _phase_a_collect(
    db: AsyncSession,
    context: GenerationContext,
    baseline: dict[int, TaskContent],
) -> tuple[list[tuple[TaskPlanInput, list[DocumentOutline]]], dict[int, TaskContent], list[ChunkBatch]]:
    """PHA A — tuần tự, CHỈ đọc DB. Không có 1 lời gọi LLM nào trong pha này.

    Trả về 3 thứ: danh sách task cần gọi LLM (kèm outline đã đọc), phần nội dung đã chốt được ngay
    (task không có tài liệu / có tài liệu nhưng chưa tách đoạn), và các lô đoạn DUY NHẤT cho pha B.

    2 việc quan trọng ở đây:
    - Nhớ theo `version_id`: nhiều task đọc chung 1 tài liệu (vd 2 task cùng nhóm SETUP) chỉ truy vấn
      1 lần. An toàn tuyệt đối vì chunk của 1 version là bất biến — nạp lại tài liệu sinh ra
      `version_id` mới chứ không sửa chunk cũ (xem modules/knowledge/ingestion/versioning.py).
    - Gom `chunk_id` duy nhất TOÀN LƯỢT rồi mới chia lô, nên 1 đoạn chỉ được tóm tắt đúng 1 lần dù
      bao nhiêu task cùng đọc nó.
    """
    prepared: list[tuple[TaskPlanInput, list[DocumentOutline]]] = []
    contents: dict[int, TaskContent] = {}
    chunks_by_version: dict[int, list[ChunkHit]] = {}
    unique_outlines: list[DocumentOutline] = []
    seen_versions: set[int] = set()

    for task_input in context.task_inputs:
        task = task_input.template_task
        if not task_input.allowed_documents:
            contents[task.template_task_id] = baseline[task.template_task_id]
            continue

        outlines: list[DocumentOutline] = []
        for document in task_input.allowed_documents:
            chunks = chunks_by_version.get(document.version_id)
            if chunks is None:
                chunks = await fetch_all_document_chunks(db, version_id=document.version_id)
                chunks_by_version[document.version_id] = chunks
            outlines.append(DocumentOutline(document=document, chunks=chunks))
            if document.version_id not in seen_versions:
                seen_versions.add(document.version_id)
                unique_outlines.append(DocumentOutline(document=document, chunks=chunks))

        outlines = _ordered_outlines(outlines)
        if not any(outline.chunks for outline in outlines):
            # Có tài liệu nhưng chưa tài liệu nào được tách đoạn — khác hẳn ca "chưa có tài liệu",
            # PM cần biết để đi kiểm tra khâu nạp tài liệu chứ không phải upload thêm.
            contents[task.template_task_id] = TaskContent(
                title=task.title_pattern,
                instruction=_no_evidence_instruction(task, prompts.NO_HIT_NOTICE),
                sources=_document_sources(task_input),
                generated_by_ai=False,
            )
            continue
        prepared.append((task_input, outlines))

    batches = _batch_documents(_ordered_outlines(unique_outlines)) if prepared else []
    return prepared, contents, batches


async def _phase_b_evidence_cards(
    llm, batches: list[ChunkBatch], semaphore: asyncio.Semaphore, usage: LlmUsage
) -> dict[int, EvidenceCard]:
    """PHA B — song song có trần, CHỈ gọi LLM. Không đụng DB nên chạy đồng thời là an toàn."""

    async def run(batch: ChunkBatch) -> dict[int, EvidenceCard]:
        async with semaphore:
            return await _build_batch_cards(llm, batch, usage)

    cards: dict[int, EvidenceCard] = {}
    for result in await asyncio.gather(*(run(batch) for batch in batches)):
        cards.update(result)
    return cards


async def _phase_c_task_content(
    llm,
    task_input: TaskPlanInput,
    outlines: list[DocumentOutline],
    cards: dict[int, EvidenceCard],
    project_key: str,
    semaphore: asyncio.Semaphore,
    baseline: dict[int, TaskContent],
    usage: LlmUsage,
) -> tuple[int, TaskContent]:
    """PHA C — sinh nội dung cho ĐÚNG 1 task. Luôn trả về nội dung dùng được, không ném ra ngoài:
    lỗi ở 1 task không được làm hỏng cả plan (giữ nguyên bất biến của bản cũ, chỉ đổi chỗ đứng)."""
    task = task_input.template_task
    try:
        sources_section, citations = _build_sources_section(outlines, cards)
        async with semaphore:
            steps = await _generate_steps_section(
                llm, task, project_key, outlines, cards, len(citations), usage
            )
        if steps is None:
            # Không nhận nội dung sai khung/trích dẫn bịa, nhưng phần "Tài liệu nguồn cần đọc" đã
            # ráp bằng code thì vẫn dùng được — giữ lại thay vì vứt cả task về baseline trắng.
            steps = _baseline_body(task)

        return task.template_task_id, TaskContent(
            title=task.title_pattern,
            instruction=f"{steps.rstrip()}\n\n{sources_section}",
            sources=_document_sources(task_input),
            citations=citations,
            generated_by_ai=True,
        )
    except Exception as exc:  # noqa: BLE001 - hạ cấp có kiểm soát, đã log lại
        logger.warning(
            "plan_generation: sinh nội dung AI lỗi cho task %s (%s) — dùng baseline",
            task.template_task_id,
            type(exc).__name__,
        )
        return task.template_task_id, baseline[task.template_task_id]


async def generate_ai_content(
    db: AsyncSession,
    context: GenerationContext,
    project_key: str,
    *,
    progress: Callable[[int, int], None] | None = None,
) -> dict[int, TaskContent]:
    """Bản AI — 3 pha: đọc DB 1 lần → Evidence Card theo đoạn duy nhất → sinh nội dung từng task.

    Lỗi ở 1 task KHÔNG làm hỏng cả plan: task đó rơi về baseline. Thà có nội dung khung còn hơn mất
    trắng cả lượt sinh vì 1 câu trả lời lỗi.

    `progress(done, total)` (tuỳ chọn) được gọi mỗi khi 1 task ở pha C xong, để job/FE thấy tiến độ
    bên trong bước 5 thay vì đứng im cho tới lúc cả bước kết thúc.
    """
    from src.services.llm import get_plan_content_llm

    baseline = generate_baseline_content(context)
    llm = get_plan_content_llm()
    # 1 semaphore DUY NHẤT cho cả pha B lẫn pha C. Bản cũ chỉ chặn nhánh tóm tắt, còn lời gọi viết
    # nội dung thì thả tự do — không sao khi các task chạy nối đuôi, nhưng giờ chúng chạy song song
    # nên không chặn là bắn N lời gọi cùng lúc vào rate limit.
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM_CALLS)
    usage = LlmUsage()

    prepared, contents, batches = await _phase_a_collect(db, context, baseline)
    if not prepared:
        return contents

    cards = await _phase_b_evidence_cards(llm, batches, semaphore, usage)

    total = len(prepared)
    done = 0
    pending = [
        _phase_c_task_content(
            llm, task_input, outlines, cards, project_key, semaphore, baseline, usage
        )
        for task_input, outlines in prepared
    ]
    # `as_completed` thay vì `gather` để báo tiến độ ngay khi từng task xong. Thứ tự hoàn thành không
    # quan trọng vì kết quả gom theo `template_task_id`, không theo vị trí.
    for coroutine in asyncio.as_completed(pending):
        task_id, content = await coroutine
        contents[task_id] = content
        done += 1
        if progress is not None:
            progress(done, total)

    logger.info(
        "plan_generation: %s lời gọi LLM, %s chunk duy nhất, %s Evidence Card "
        "(%s có trích dẫn đã xác minh), %s input + %s output token, ~%.6f USD",
        usage.calls,
        sum(len(batch.chunks) for batch in batches),
        len(cards),
        sum(1 for card in cards.values() if card.exact_quote),
        usage.input_tokens,
        usage.output_tokens,
        usage.estimated_usd(),
    )
    return contents


def _validate_instruction(instruction: str, citation_count: int) -> str | None:
    """Trả về mô tả lỗi nếu output không dùng được, `None` nếu đạt.

    Trả chuỗi mô tả (thay vì bool) để nhánh sửa 1 lần nói đúng cho LLM biết nó sai chỗ nào — bảo
    "viết lại đi" chung chung thì lần 2 thường sai y hệt lần 1.
    """
    if "## Mục tiêu" not in instruction:
        return "thiếu mục '## Mục tiêu' — sai khung markdown bắt buộc"
    if not _citations_within_range(instruction, citation_count):
        return f"có trích dẫn [n] nằm ngoài phạm vi 1..{citation_count} nguồn thật"
    return None


async def _generate_steps_section(
    llm,
    task,
    project_key: str,
    outlines: list[DocumentOutline],
    cards: dict[int, EvidenceCard],
    citation_count: int,
    usage: LlmUsage | None = None,
) -> str | None:
    """Lời gọi LLM thứ 2: viết Mục tiêu / Các bước thực hiện / Kết quả cần đạt.

    Sai khung hoặc trích dẫn ngoài phạm vi thì SỬA ĐÚNG 1 LẦN (gửi lại kèm mô tả lỗi cụ thể), rồi
    kiểm lại; vẫn sai thì trả `None` để người gọi hạ cấp về nội dung khung.

    Vì sao có nhánh sửa, dù bản đầu cố ý không "sửa hộ" để khỏi che lỗi lúc đo eval: mọi lần sửa đều
    được ghi log kèm lý do, nên tỉ lệ hỏng thật vẫn đọc được từ log — thứ bị bỏ đi chỉ là việc bắt
    người dùng nhận nội dung khung vì một lỗi định dạng mà 1 lời nhắc là sửa được.
    """
    messages = [
        ("system", prompts.SYSTEM_PROMPT),
        (
            "user",
            prompts.build_user_prompt(
                project_key=project_key,
                task_title=task.title_pattern,
                task_objective=task.objective,
                instruction_template=task.instruction_template,
                estimated_minutes=task.estimated_minutes,
                sources_block=_build_evidence_block(outlines, cards),
            ),
        ),
    ]

    for attempt in range(2):
        response = await llm.ainvoke(
            messages,
            # Callback này (chứ không phải @observe) mới là chỗ gửi prompt/completion +
            # input_tokens/output_tokens/cost lên Langfuse — xem observability/tracing.py.
            config={"callbacks": get_langchain_callbacks()},
        )
        if usage is not None:
            usage.record(response)
        instruction = str(response.content).strip()
        problem = _validate_instruction(instruction, citation_count)
        if problem is None:
            if attempt:
                logger.info(
                    "plan_generation: task %s sửa 1 lần thành công", task.template_task_id
                )
            return instruction

        if attempt == 0:
            logger.warning(
                "plan_generation: task %s output không đạt (%s) — thử sửa 1 lần",
                task.template_task_id,
                problem,
            )
            messages = messages + [
                ("assistant", instruction),
                ("user", prompts.build_repair_prompt(problem=problem, citation_count=citation_count)),
            ]

    logger.warning(
        "plan_generation: task %s vẫn sai sau khi sửa (%s) — dùng nội dung khung",
        task.template_task_id,
        problem,
    )
    return None


def should_use_ai() -> bool:
    settings = get_settings()
    return bool(settings.plan_generation_use_ai and settings.deepseek_api_key)
