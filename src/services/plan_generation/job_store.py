"""Trạng thái tiến độ của 1 lần sinh Candidate Plan — lưu in-memory, KHÔNG vào DB.

Vì sao in-memory: đây là dữ liệu sống đúng vài chục giây (FE poll để vẽ 6 bước loading rồi bỏ),
không phải dữ liệu nghiệp vụ cần lịch sử. Ghi vào DB sẽ tạo bảng rác chỉ để phục vụ 1 hiệu ứng UI.
Tái dùng đúng pattern `_SCAN_SESSIONS` đã chạy ổn ở Phase 3 (`repo_scanner_service.py`): dict
module-level + TTL prune mỗi lần đọc.

Giới hạn đã biết (ghi rõ, không giấu): chạy nhiều worker/process thì job không share được giữa các
process. Hiện `docker-compose.yml` chạy uvicorn 1 process nên không có vấn đề; khi nào scale nhiều
worker thì thay chỗ này bằng Redis, phần còn lại của pipeline không phải sửa.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum

JOB_TTL_SECONDS = 30 * 60


class StepStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


class JobStatus(StrEnum):
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


# 6 bước đúng theo mockup owner-plan-generating (docs/PM/plan-pm.md Phase 4).
STEP_SEQUENCE: tuple[tuple[str, str], ...] = (
    ("load_template", "Tải Master Template đã duyệt"),
    ("merge_company_core", "Gộp tài liệu Company Core"),
    ("collect_project_docs", "Lọc tài liệu dự án theo nhóm"),
    ("map_task_sources", "Chọn nguồn cho từng nhóm task"),
    ("generate_content", "Điền nội dung & hướng dẫn từng task"),
    ("validate_and_persist", "Kiểm tra dependency và lưu plan"),
)


@dataclass
class StepState:
    key: str
    label: str
    status: StepStatus = StepStatus.PENDING
    duration_ms: int | None = None
    detail: str | None = None
    progress_done: int | None = None
    progress_total: int | None = None
    document_count: int | None = None
    _started_at: float | None = None


@dataclass
class GenerationJob:
    job_id: str
    correlation_id: str
    # Đúng 1 trong 2 có giá trị: membership_id = cấp plan cho kỹ sư, project_id = sinh bản chuẩn.
    membership_id: int | None
    project_id: int | None
    created_at: float
    steps: list[StepState]
    status: JobStatus = JobStatus.RUNNING
    plan_id: int | None = None
    error: str | None = None
    total_duration_ms: int | None = None
    warnings: list[str] = field(default_factory=list)

    def step(self, key: str) -> StepState:
        for state in self.steps:
            if state.key == key:
                return state
        raise KeyError(f"Bước '{key}' không có trong pipeline")

    def start_step(self, key: str) -> None:
        state = self.step(key)
        state.status = StepStatus.RUNNING
        state._started_at = time.perf_counter()

    def finish_step(self, key: str, detail: str | None = None) -> int:
        state = self.step(key)
        elapsed = self._elapsed_ms(state)
        state.status = StepStatus.DONE
        state.duration_ms = elapsed
        state.detail = detail
        return elapsed

    def update_step_detail(self, key: str, detail: str) -> None:
        """Đổi RIÊNG dòng mô tả của 1 bước đang chạy, không đụng `status`/`duration_ms`.

        Dùng để báo tiến độ BÊN TRONG 1 bước (vd "3/7 task đã sinh xong") — bước `generate_content`
        chạy vài chục giây, không có dòng này thì FE chỉ thấy spinner đứng im. Cố ý không đụng tới
        `_started_at` để `finish_step` vẫn đo đúng tổng thời gian của cả bước.
        """
        state = self.step(key)
        state.detail = detail
        # The content generator reports "done/total task ..." after every completed task.
        # Keep this compatibility path so existing callers also populate structured progress.
        first_token = detail.split(" ", 1)[0]
        if "/" in first_token:
            done_text, total_text = first_token.split("/", 1)
            if done_text.isdigit() and total_text.isdigit():
                state.progress_done = int(done_text)
                state.progress_total = int(total_text)

    def update_step_progress(
        self, key: str, *, done: int, total: int, document_count: int, detail: str
    ) -> None:
        state = self.step(key)
        state.progress_done = max(0, done)
        state.progress_total = max(0, total)
        state.document_count = max(0, document_count)
        state.detail = detail

    def fail_step(self, key: str, message: str) -> None:
        state = self.step(key)
        state.duration_ms = self._elapsed_ms(state)
        state.status = StepStatus.FAILED
        state.detail = message

    @staticmethod
    def _elapsed_ms(state: StepState) -> int:
        if state._started_at is None:
            return 0
        return int((time.perf_counter() - state._started_at) * 1000)


_JOBS: dict[str, GenerationJob] = {}


def _prune_expired_jobs() -> None:
    now = time.time()
    for job_id in [jid for jid, job in _JOBS.items() if now - job.created_at > JOB_TTL_SECONDS]:
        del _JOBS[job_id]


def create_job(*, membership_id: int | None = None, project_id: int | None = None) -> GenerationJob:
    """Truyền `membership_id` khi cấp plan cho kỹ sư, `project_id` khi sinh bản chuẩn của dự án."""
    if (membership_id is None) == (project_id is None):
        raise ValueError("Phải truyền đúng 1 trong 2: membership_id hoặc project_id")

    _prune_expired_jobs()
    job = GenerationJob(
        job_id=uuid.uuid4().hex,
        correlation_id=uuid.uuid4().hex,
        membership_id=membership_id,
        project_id=project_id,
        created_at=time.time(),
        steps=[StepState(key=key, label=label) for key, label in STEP_SEQUENCE],
    )
    _JOBS[job.job_id] = job
    return job


def get_job(job_id: str) -> GenerationJob | None:
    _prune_expired_jobs()
    return _JOBS.get(job_id)
