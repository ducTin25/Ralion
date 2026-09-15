"""Test kiến trúc 3 pha của bước sinh nội dung (`content_llm.generate_ai_content`).

Khác `test_plan_generation.py` (tắt hẳn AI để test phần nghiệp vụ): file này BẬT nhánh AI nhưng
thay LLM và tầng đọc DB bằng bản giả, nên vẫn deterministic và không cần mạng/API key. Mục tiêu là
canh đúng những thứ chỉ sai khi chạy song song — thứ mà test nghiệp vụ không nhìn thấy:

- 1 đoạn dùng chung giữa nhiều task chỉ được tóm tắt ĐÚNG 1 lần (pha B dedup theo `chunk_id`).
- Card dùng chung KHÔNG kéo theo số `[n]` của task đã tính nó (mỗi task tự đánh số cục bộ).
- Các task chạy song song thật, nhưng không vượt trần `MAX_CONCURRENT_LLM_CALLS`.
- Lỗi/hỏng ở 1 task không lan sang task khác.
- Sửa 1 lần (repair-once) cứu được output sai khung, và vẫn ghi log để đo eval.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from src.model.enums import DocumentDomain, PolicyCategory
from src.services.plan_generation import content_llm, prompts
from src.services.plan_generation.steps import DocumentRef, TaskPlanInput
from src.services.plan_generation.tools import ChunkHit

# --- Bản giả tối thiểu -----------------------------------------------------------------------


@dataclass
class FakeTask:
    """Chỉ đủ trường mà `content_llm` thật sự đọc — không dựng cả ORM TemplateTask cho 1 test đơn vị."""

    template_task_id: int
    title_pattern: str = "Task"
    objective: str = "Muc tieu"
    instruction_template: str = "Khung co san"
    estimated_minutes: int = 60


def _document(document_id: int, *, policy: PolicyCategory | None = None) -> DocumentRef:
    return DocumentRef(
        document_id=document_id,
        version_id=1000 + document_id,
        title=f"Tai lieu {document_id}",
        knowledge_domain=DocumentDomain.POLICY if policy else DocumentDomain.PROJECT,
        document_category=None,
        policy_category=policy,
    )


def _chunks(document: DocumentRef, count: int) -> list[ChunkHit]:
    return [
        ChunkHit(
            chunk_id=document.document_id * 100 + index,
            version_id=document.version_id,
            document_id=document.document_id,
            heading=f"Muc {index}",
            content=f"Noi dung doan {index} cua tai lieu {document.document_id}",
            score=0.0,
        )
        for index in range(count)
    ]


VALID_STEPS = "## Mục tiêu\nx\n\n## Các bước thực hiện\n1. Lam gi do [1]\n\n## Kết quả cần đạt\n- [ ] xong"


class FakeLLM:
    """Ghi lại mọi lời gọi + đo mức song song thật sự đạt được.

    `steps_reply` nhận (số thứ tự lời gọi của task đó, tiêu đề task) để test mô phỏng được ca "lần
    đầu sai, lần sửa thì đúng".
    """

    def __init__(self, *, steps_reply=None, card_reply=None, delay: float = 0.01):
        self.steps_reply = steps_reply or (lambda attempt, task_title: VALID_STEPS)
        self.card_reply = card_reply
        self.delay = delay
        self.card_calls: list[list[int]] = []  # mỗi phần tử = danh sách chunk_id của 1 lô
        self.steps_calls: list[str] = []
        self.attempts_by_task: dict[str, int] = {}
        self.concurrent = 0
        self.max_concurrent = 0

    async def ainvoke(self, messages, config=None):
        self.concurrent += 1
        self.max_concurrent = max(self.max_concurrent, self.concurrent)
        try:
            # Ngủ 1 nhịp để 2 lời gọi song song thật sự chồng lấn nhau — không có nó thì coroutine
            # chạy tuần tự hết trước khi coroutine sau kịp bắt đầu, và phép đo song song vô nghĩa.
            await asyncio.sleep(self.delay)
            system, user = messages[0][1], messages[1][1]
            if system == prompts.EVIDENCE_CARD_SYSTEM_PROMPT:
                chunk_ids = [
                    int(line.split("chunk_id: ")[1].split(" ")[0].split("\n")[0])
                    for line in user.split("\n")
                    if line.startswith("chunk_id: ")
                ]
                self.card_calls.append(chunk_ids)
                if self.card_reply is not None:
                    return SimpleNamespace(content=self.card_reply(chunk_ids))
                payload = [
                    {"chunk_id": cid, "summary": f"Tom tat {cid}", "quote": ""} for cid in chunk_ids
                ]
                return SimpleNamespace(content=json.dumps(payload, ensure_ascii=False))

            title = user.split("TÊN TASK: ")[1].split("\n")[0]
            attempt = self.attempts_by_task.get(title, 0)
            self.attempts_by_task[title] = attempt + 1
            self.steps_calls.append(title)
            return SimpleNamespace(content=self.steps_reply(attempt, title))
        finally:
            self.concurrent -= 1


@pytest.fixture
def wire(monkeypatch):
    """Thay `fetch_all_document_chunks` (chạm DB) và nhà máy LLM bằng bản giả.

    Nhờ vậy test chạy đúng code thật của 3 pha mà không cần DB — và đếm được chính xác số lần đọc
    tài liệu, thứ mà test qua API không nhìn thấy.
    """

    def _wire(llm: FakeLLM, chunk_map: dict[int, list[ChunkHit]]):
        reads: list[int] = []

        async def fake_fetch(db, *, version_id: int):
            reads.append(version_id)
            return chunk_map.get(version_id, [])

        monkeypatch.setattr(content_llm, "fetch_all_document_chunks", fake_fetch)
        monkeypatch.setattr(
            "src.services.llm.get_plan_content_llm", lambda: llm, raising=False
        )
        return reads

    return _wire


def _context(task_inputs):
    # `generate_ai_content` chỉ đọc `context.task_inputs`; dựng cả GenerationContext thật sẽ kéo
    # theo TemplateVersion/ORM không liên quan gì tới thứ đang test.
    return SimpleNamespace(task_inputs=task_inputs)


# --- Pha A: đọc DB 1 lần ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shared_document_is_read_from_db_once(wire):
    """2 task cùng đọc 1 tài liệu chỉ tốn 1 truy vấn — an toàn vì chunk của 1 version là bất biến."""
    shared = _document(1)
    chunk_map = {shared.version_id: _chunks(shared, 2)}
    llm = FakeLLM()
    reads = wire(llm, chunk_map)

    await content_llm.generate_ai_content(
        None,
        _context(
            [
                TaskPlanInput(template_task=FakeTask(1, "Task A"), allowed_documents=[shared]),
                TaskPlanInput(template_task=FakeTask(2, "Task B"), allowed_documents=[shared]),
            ]
        ),
        "PRJ",
    )

    assert reads == [shared.version_id], f"Phải đọc đúng 1 lần, thực tế {len(reads)} lần"


# --- Pha B: mỗi đoạn tóm tắt đúng 1 lần -------------------------------------------------------


@pytest.mark.asyncio
async def test_shared_chunk_is_summarized_once_across_tasks(wire):
    """Bản cũ tóm tắt lại từ đầu cho TỪNG task; giờ gom theo `chunk_id` duy nhất nên chỉ 1 lần.

    Đây chính là phần giảm CHI PHÍ thật (ít lời gọi LLM hơn), khác với phần song song chỉ giảm thời
    gian chờ mà không giảm số lời gọi."""
    shared = _document(1)
    chunk_map = {shared.version_id: _chunks(shared, 3)}
    llm = FakeLLM()
    wire(llm, chunk_map)

    await content_llm.generate_ai_content(
        None,
        _context(
            [
                TaskPlanInput(template_task=FakeTask(i, f"Task {i}"), allowed_documents=[shared])
                for i in range(1, 4)
            ]
        ),
        "PRJ",
    )

    summarized = [cid for call in llm.card_calls for cid in call]
    assert len(summarized) == len(set(summarized)) == 3, (
        f"3 đoạn dùng chung cho 3 task phải chỉ tóm tắt 3 lần, thực tế {summarized}"
    )
    assert len(llm.steps_calls) == 3, "Nhưng mỗi task vẫn phải có nội dung riêng"


# --- Pha C: số trích dẫn là CỤC BỘ theo task --------------------------------------------------


@pytest.mark.asyncio
async def test_shared_card_gets_different_citation_order_per_task(wire):
    """Card dùng chung nhưng số `[n]` phải khác nhau giữa 2 task có danh sách tài liệu khác nhau.

    Đây là hồi quy cho đúng lỗi mà cache khoá theo số thứ tự sẽ gây ra: cùng 1 đoạn SECURITY_POLICY
    mang số [3] ở task đọc nhiều tài liệu, nhưng phải là [1] ở task chỉ đọc mỗi tài liệu đó.
    """
    first = _document(1)
    shared = _document(2)
    chunk_map = {first.version_id: _chunks(first, 2), shared.version_id: _chunks(shared, 1)}
    llm = FakeLLM()
    wire(llm, chunk_map)

    contents = await content_llm.generate_ai_content(
        None,
        _context(
            [
                TaskPlanInput(
                    template_task=FakeTask(1, "Task nhieu nguon"),
                    allowed_documents=[first, shared],
                ),
                TaskPlanInput(
                    template_task=FakeTask(2, "Task mot nguon"), allowed_documents=[shared]
                ),
            ]
        ),
        "PRJ",
    )

    shared_chunk_id = chunk_map[shared.version_id][0].chunk_id
    order_in_task1 = next(
        c.citation_order for c in contents[1].citations if c.chunk_id == shared_chunk_id
    )
    order_in_task2 = next(
        c.citation_order for c in contents[2].citations if c.chunk_id == shared_chunk_id
    )

    assert order_in_task1 == 3, "Task đọc 2 tài liệu: đoạn dùng chung đứng thứ 3"
    assert order_in_task2 == 1, "Task chỉ đọc tài liệu đó: cùng đoạn ấy phải là [1]"


@pytest.mark.asyncio
async def test_every_task_citations_are_contiguous_from_one(wire):
    """Dù chạy song song và hoàn thành không theo thứ tự, mỗi task vẫn có dãy [1..n] liền mạch."""
    documents = [_document(i) for i in range(1, 4)]
    chunk_map = {d.version_id: _chunks(d, 2) for d in documents}
    llm = FakeLLM()
    wire(llm, chunk_map)

    contents = await content_llm.generate_ai_content(
        None,
        _context(
            [
                TaskPlanInput(
                    template_task=FakeTask(i, f"Task {i}"), allowed_documents=documents[: i or 1]
                )
                for i in range(1, 4)
            ]
        ),
        "PRJ",
    )

    for task_id, content in contents.items():
        orders = [c.citation_order for c in content.citations]
        assert orders == list(range(1, len(orders) + 1)), f"Task {task_id} có dãy số hỏng: {orders}"


# --- Song song có trần -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tasks_really_run_in_parallel_but_respect_the_cap(wire):
    """Phải có chồng lấn thật (nếu không thì tối ưu vô nghĩa) nhưng không vượt trần rate limit."""
    documents = [_document(i) for i in range(1, 9)]
    chunk_map = {d.version_id: _chunks(d, 1) for d in documents}
    llm = FakeLLM(delay=0.02)
    wire(llm, chunk_map)

    await content_llm.generate_ai_content(
        None,
        _context(
            [
                TaskPlanInput(template_task=FakeTask(i, f"Task {i}"), allowed_documents=[documents[i - 1]])
                for i in range(1, 9)
            ]
        ),
        "PRJ",
    )

    assert llm.max_concurrent > 1, "Không có lời gọi nào chồng lấn — vẫn đang chạy tuần tự"
    assert llm.max_concurrent <= content_llm.MAX_CONCURRENT_LLM_CALLS, (
        f"Vượt trần {content_llm.MAX_CONCURRENT_LLM_CALLS}: {llm.max_concurrent} lời gọi cùng lúc"
    )


@pytest.mark.asyncio
async def test_progress_callback_reports_each_finished_task(wire):
    """Job/FE phải thấy tiến độ bên trong bước 5 thay vì spinner đứng im tới lúc xong."""
    documents = [_document(i) for i in range(1, 4)]
    chunk_map = {d.version_id: _chunks(d, 1) for d in documents}
    llm = FakeLLM()
    wire(llm, chunk_map)
    seen: list[tuple[int, int]] = []

    await content_llm.generate_ai_content(
        None,
        _context(
            [
                TaskPlanInput(template_task=FakeTask(i, f"Task {i}"), allowed_documents=[documents[i - 1]])
                for i in range(1, 4)
            ]
        ),
        "PRJ",
        progress=lambda done, total: seen.append((done, total)),
    )

    assert seen == [(1, 3), (2, 3), (3, 3)]


# --- Cách ly lỗi -------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_one_failing_task_does_not_affect_siblings(wire):
    """1 task ném lỗi thì chỉ task đó rơi về baseline; task khác vẫn có nội dung AI."""
    documents = [_document(i) for i in range(1, 4)]
    chunk_map = {d.version_id: _chunks(d, 1) for d in documents}

    def explode(attempt, task_title):
        if task_title == "Task 2":
            raise RuntimeError("LLM sap")
        return VALID_STEPS

    llm = FakeLLM(steps_reply=explode)
    wire(llm, chunk_map)

    contents = await content_llm.generate_ai_content(
        None,
        _context(
            [
                TaskPlanInput(template_task=FakeTask(i, f"Task {i}"), allowed_documents=[documents[i - 1]])
                for i in range(1, 4)
            ]
        ),
        "PRJ",
    )

    assert contents[2].generated_by_ai is False, "Task lỗi phải hạ cấp về baseline"
    assert contents[1].generated_by_ai is True and contents[3].generated_by_ai is True, (
        "Task khác không được bị ảnh hưởng"
    )
    assert len(contents) == 3, "Không được mất task nào khỏi plan"


@pytest.mark.asyncio
async def test_batch_failure_keeps_every_chunk_listed(wire):
    """Lô tóm tắt hỏng thì các đoạn của nó vẫn xuất hiện đủ kèm ghi chú — bao phủ do CODE giữ."""
    document = _document(1)
    chunk_map = {document.version_id: _chunks(document, 3)}

    def broken_cards(chunk_ids):
        raise RuntimeError("timeout")

    llm = FakeLLM(card_reply=broken_cards)
    wire(llm, chunk_map)

    contents = await content_llm.generate_ai_content(
        None,
        _context([TaskPlanInput(template_task=FakeTask(1, "Task A"), allowed_documents=[document])]),
        "PRJ",
    )

    assert len(contents[1].citations) == 3, "Vẫn đủ 3 trích dẫn dù không tóm tắt được"
    assert contents[1].instruction.count(prompts.UNSUMMARIZED_CHUNK_NOTE) == 3


# --- Sửa 1 lần ---------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_repair_once_recovers_bad_output_and_logs_it(wire, caplog):
    """Lần đầu sai khung → sửa 1 lần → nhận. Và PHẢI có log, nếu không tỉ lệ hỏng thật bị che mất
    khi đo eval (đúng lý do bản gốc cố ý không sửa hộ).

    Bản giả ở đây CỐ Ý chỉ trả kết quả đúng khi nhìn thấy lời nhắc sửa trong hội thoại, chứ không
    dựa vào "lần gọi thứ 2". Nếu chỉ đếm lần gọi, test vẫn xanh kể cả khi nhánh sửa bị gỡ bỏ (đã
    kiểm bằng mutation: gỡ nhánh sửa mà test không đỏ) — tức là test không canh đúng thứ cần canh.
    """
    document = _document(1)
    chunk_map = {document.version_id: _chunks(document, 1)}

    class RepairAwareLLM(FakeLLM):
        async def ainvoke(self, messages, config=None):
            self.saw_repair = any(
                "Bản trả lời vừa rồi KHÔNG dùng được" in message[1] for message in messages
            )
            return await super().ainvoke(messages, config)

    llm = RepairAwareLLM(
        steps_reply=lambda attempt, title: VALID_STEPS if llm.saw_repair else "Sai khung hoan toan"
    )
    llm.saw_repair = False
    wire(llm, chunk_map)

    with caplog.at_level(logging.INFO, logger="src.services.plan_generation.content_llm"):
        contents = await content_llm.generate_ai_content(
            None,
            _context(
                [TaskPlanInput(template_task=FakeTask(1, "Task A"), allowed_documents=[document])]
            ),
            "PRJ",
        )

    assert contents[1].generated_by_ai is True
    assert "## Mục tiêu" in contents[1].instruction
    assert llm.attempts_by_task["Task A"] == 2, "Đúng 1 lần sửa, không nhiều hơn"
    assert any("sửa 1 lần thành công" in r.message for r in caplog.records), "Thiếu log lần sửa"


@pytest.mark.asyncio
async def test_repair_gives_up_after_one_attempt(wire):
    """Sai 2 lần thì thôi — hạ cấp về nội dung khung, KHÔNG thử vòng 3 (chi phí không có trần)."""
    document = _document(1)
    chunk_map = {document.version_id: _chunks(document, 1)}
    llm = FakeLLM(steps_reply=lambda attempt, title: "Van sai khung")
    wire(llm, chunk_map)

    contents = await content_llm.generate_ai_content(
        None,
        _context([TaskPlanInput(template_task=FakeTask(1, "Task A"), allowed_documents=[document])]),
        "PRJ",
    )

    assert llm.attempts_by_task["Task A"] == 2, "Tối đa 2 lời gọi (1 lần đầu + 1 lần sửa)"
    # Vẫn giữ phần "Tài liệu nguồn cần đọc" ráp bằng code — không vứt cả task về trắng.
    assert prompts.SOURCES_SECTION_HEADING in contents[1].instruction


@pytest.mark.asyncio
async def test_repair_prompt_tells_the_model_what_was_wrong(wire):
    """Lời nhắc sửa phải nói đúng lỗi cụ thể; "viết lại đi" chung chung thì lần 2 thường sai y hệt."""
    document = _document(1)
    chunk_map = {document.version_id: _chunks(document, 1)}
    seen: list = []

    class Recorder(FakeLLM):
        async def ainvoke(self, messages, config=None):
            seen.append(messages)
            return await super().ainvoke(messages, config)

    llm = Recorder(steps_reply=lambda attempt, title: "## Mục tiêu\nBuoc [9]" if attempt == 0 else VALID_STEPS)
    wire(llm, chunk_map)

    await content_llm.generate_ai_content(
        None,
        _context([TaskPlanInput(template_task=FakeTask(1, "Task A"), allowed_documents=[document])]),
        "PRJ",
    )

    repair_messages = seen[-1]
    assert len(repair_messages) == 4, "Phải gửi lại kèm output cũ + lời nhắc sửa"
    assert "ngoài phạm vi" in repair_messages[-1][1], "Lời nhắc phải nêu đúng lỗi trích dẫn"


# --- Task không có bằng chứng ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_without_documents_never_calls_the_llm(wire):
    """Task không có tài liệu thì không tốn 1 đồng token nào — chốt ngay ở pha A."""
    llm = FakeLLM()
    wire(llm, {})

    contents = await content_llm.generate_ai_content(
        None,
        _context([TaskPlanInput(template_task=FakeTask(1, "Task A"), allowed_documents=[])]),
        "PRJ",
    )

    assert llm.card_calls == [] and llm.steps_calls == []
    assert contents[1].generated_by_ai is False


@pytest.mark.asyncio
async def test_document_without_chunks_is_reported_not_fabricated(wire):
    """Có tài liệu nhưng chưa tách đoạn: nói thẳng để PM đi kiểm tra khâu nạp, không bịa hướng dẫn."""
    document = _document(1)
    llm = FakeLLM()
    wire(llm, {document.version_id: []})

    contents = await content_llm.generate_ai_content(
        None,
        _context([TaskPlanInput(template_task=FakeTask(1, "Task A"), allowed_documents=[document])]),
        "PRJ",
    )

    assert llm.steps_calls == [], "Không có đoạn nào thì không được gọi LLM viết nội dung"
    assert prompts.NO_HIT_NOTICE in contents[1].instruction


# --- Báo tiến độ trong job ---------------------------------------------------------------------


def test_update_step_detail_does_not_disturb_step_timing():
    """Cập nhật tiến độ giữa chừng KHÔNG được đụng `status`/`duration_ms`.

    Nếu nó lỡ chạm vào, bước đang RUNNING sẽ bị coi là xong hoặc mất số đo thời gian — mà chính số
    đo đó là thứ dùng để so trước/sau khi tối ưu.
    """
    from src.services.plan_generation.job_store import GenerationJob, JobStatus, StepStatus, create_job

    job = create_job(project_id=1)
    job.start_step("generate_content")

    job.update_step_detail("generate_content", "2/5 task đã sinh xong")

    state = job.step("generate_content")
    assert state.detail == "2/5 task đã sinh xong"
    assert state.status is StepStatus.RUNNING, "Vẫn phải đang chạy"
    assert state.duration_ms is None, "Chưa xong thì chưa được có số đo"
    assert job.status is JobStatus.RUNNING
    assert isinstance(job, GenerationJob)

    duration = job.finish_step("generate_content", "5/5 task do AI viết")
    assert duration >= 0 and job.step("generate_content").detail == "5/5 task do AI viết"
