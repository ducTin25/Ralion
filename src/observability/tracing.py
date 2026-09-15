"""Tracing bằng Langfuse cho pipeline sinh Candidate Plan (SDK v4).

Thiết kế quan trọng: **thiếu Langfuse là chuyện bình thường, không phải lỗi**. Chưa cài thư viện
hoặc chưa cấu hình key thì `observe_step` trở thành decorator rỗng và pipeline chạy y hệt. Lý do:
- CI không có secret, không được để test đỏ chỉ vì thiếu key observability.
- Người mới clone repo phải chạy được ngay, không phải đăng ký Langfuse trước.

Quyền riêng tư — `capture_input=False, capture_output=False` ở MỌI span:
mặc định `@observe` dump toàn bộ tham số vào/ra của hàm lên Langfuse. Các bước pipeline nhận
`AsyncSession` và `GenerationContext` (chứa NGUYÊN VĂN nội dung tài liệu dự án) → bật mặc định là
đẩy nội dung nội bộ ra dịch vụ ngoài, vi phạm SoT §19. Nội dung prompt/kết quả LLM (thứ thật sự cần
xem để debug chất lượng AI) được `CallbackHandler` của LangChain gửi riêng, kèm token/cost chuẩn.

Tên span đặt theo `docs/PM/plan-pm.md` Phase 4: bước gọi LLM dùng `as_type="generation"` để Langfuse
tính token/cost; bước tra dữ liệu thuần dùng `as_type="tool"` + tên `execute_tool <bước>`.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Iterator
from typing import Any, TypeVar

from src.config import get_settings

F = TypeVar("F", bound=Callable[..., Any])

_observe: Callable[..., Any] | None = None
_resolved = False
_client_ready = False


def langfuse_enabled() -> bool:
    settings = get_settings()
    return bool(settings.langfuse_public_key and settings.langfuse_secret_key)


def _ensure_client() -> bool:
    """Khởi tạo client Langfuse 1 lần, truyền key TƯỜNG MINH từ Settings.

    Bắt buộc phải làm bước này: SDK Langfuse tự đọc `os.environ`, trong khi project dùng
    pydantic-settings nạp `.env` vào object `Settings` chứ KHÔNG đổ ngược vào `os.environ`. Không
    khởi tạo tường minh thì SDK báo "initialized without public_key" và im lặng tắt tracing — chạy
    vẫn không lỗi nên rất dễ tưởng là đang trace mà thật ra không có gì được gửi đi.
    """
    global _client_ready
    if _client_ready:
        return True
    if not langfuse_enabled():
        return False
    try:
        from langfuse import Langfuse

        settings = get_settings()
        Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
            environment=settings.app_env,
        )
        _client_ready = True
        return True
    except Exception:  # noqa: BLE001 - observability không bao giờ được làm hỏng nghiệp vụ
        return False


def _resolve_observe() -> Callable[..., Any] | None:
    """Nạp `@observe` của Langfuse 1 lần duy nhất. Không có thư viện/không có key -> None."""
    global _observe, _resolved
    if _resolved:
        return _observe

    _resolved = True
    if not _ensure_client():
        return None
    try:
        from langfuse import observe
    except ImportError:
        return None
    _observe = observe
    return _observe


def observe_step(name: str, *, as_type: str = "tool") -> Callable[[F], F]:
    """Bọc 1 bước pipeline thành 1 span con của trace hiện tại."""

    def decorator(func: F) -> F:
        observe = _resolve_observe()
        if observe is None:
            return func
        try:
            return observe(  # type: ignore[no-any-return]
                name=name,
                as_type=as_type,
                capture_input=False,
                capture_output=False,
            )(func)
        except TypeError:
            # Phiên bản SDK khác chữ ký -> bỏ tracing bước này, KHÔNG để chết pipeline.
            return func

    return decorator


def get_langchain_callbacks() -> list[Any]:
    """Callback gửi prompt/completion/token/cost của lời gọi LLM lên Langfuse.

    Trả list rỗng khi chưa bật Langfuse — `ChatOpenAI.ainvoke(callbacks=[])` là hợp lệ nên chỗ gọi
    không cần rẽ nhánh if/else.
    """
    if not _ensure_client():
        return []
    try:
        from langfuse.langchain import CallbackHandler

        return [CallbackHandler()]
    except ImportError:
        return []


@contextlib.contextmanager
def tag_project_trace(project_id: int) -> Iterator[None]:
    """Gắn tag `project:<id>` cho trace hiện tại + MỌI span con tạo bên trong `with` — đây là cách
    `get_project_ai_cost_usd()` lọc được cost đúng theo dự án (query Langfuse Metrics API theo tag,
    xem hàm đó). Bọc quanh `run_generation()` (`pipeline.py`) — điểm DUY NHẤT gọi AI thật.

    No-op an toàn (không lỗi, không cảnh báo) khi chưa cấu hình Langfuse — cùng triết lý với
    `observe_step`/`get_langchain_callbacks` trong file này."""
    context_manager = None
    if _ensure_client():
        try:
            from langfuse import propagate_attributes

            context_manager = propagate_attributes(tags=[f"project:{project_id}"])
        except Exception:  # noqa: BLE001 - observability không bao giờ được làm hỏng nghiệp vụ
            context_manager = None

    if context_manager is None:
        yield
        return
    # KHÔNG bọc `yield` trong try/except riêng: lỗi ở đây phải là lỗi THẬT của code nghiệp vụ bên
    # trong `with`, không phải lỗi tracing — nuốt nhầm ở đây sẽ che mất lỗi thật của pipeline.
    with context_manager:
        yield


async def get_project_ai_cost_usd(project_id: int) -> float | None:
    """Tổng chi phí AI (USD) của 1 dự án, cộng dồn từ MỌI lần sinh Candidate Plan đã gắn tag
    `project:<id>` (xem `run_generation()` trong `pipeline.py`, nơi bọc
    `langfuse.propagate_attributes(tags=[...])`).

    `async` vì gọi ra REST API Langfuse thật (I/O mạng) — dùng `async_api` (không phải `api` đồng
    bộ) để không chặn event loop lúc `pm_dashboard_service.get_dashboard()` (đã là `async def`) gọi
    hàm này.

    Trả `None` khi: chưa cấu hình Langfuse, lỗi mạng/timeout, hoặc CHƯA có trace nào của dự án này
    được gắn tag (kể cả khi dự án đã từng sinh plan TRƯỚC khi tính năng gắn tag này tồn tại — trace
    cũ không tự có tag, không backfill được). Người gọi (`pm_dashboard_service.py`) phải coi `None`
    là "chưa có dữ liệu", KHÔNG phải lỗi hay chi phí $0 — hiện "—" trên UI, không hiện "$0".

    **KHÔNG dùng measure `totalCost` của Langfuse** — đã kiểm tra bằng dữ liệu thật (dự án GADGETHUB
    sau khi sinh plan thật): Langfuse đếm ĐÚNG token (`inputTokens`/`outputTokens`) nhưng
    `totalCost` luôn ra 0, vì model gọi qua `base_url` riêng của DeepSeek không nằm trong bảng giá
    Langfuse tự có — đúng vấn đề `config.py` đã ghi chú khi thêm `deepseek_input_usd_per_mtok`/
    `deepseek_output_usd_per_mtok`. Ở đây lấy TOKEN thật từ Langfuse rồi tự tính tiền bằng ĐÚNG 2
    hằng số đó — cùng công thức với `LlmUsage.estimated_usd()` trong `content_llm.py`, không phải
    tự nghĩ ra cách tính khác.
    """
    if not _ensure_client():
        return None
    try:
        import json

        from langfuse import get_client

        response = await get_client().async_api.metrics.metrics(
            query=json.dumps(
                {
                    "view": "observations",
                    "metrics": [
                        {"measure": "inputTokens", "aggregation": "sum"},
                        {"measure": "outputTokens", "aggregation": "sum"},
                    ],
                    "filters": [
                        {
                            "column": "tags",
                            "operator": "any of",
                            "value": [f"project:{project_id}"],
                            "type": "arrayOptions",
                        }
                    ],
                    "fromTimestamp": "2020-01-01T00:00:00Z",
                    "toTimestamp": "2030-01-01T00:00:00Z",
                }
            )
        )
        if not response.data:
            return None
        row = response.data[0]
        input_tokens = row.get("sum_inputTokens")
        output_tokens = row.get("sum_outputTokens")
        if input_tokens is None or output_tokens is None:
            return None
        settings = get_settings()
        return round(
            float(input_tokens) / 1_000_000 * settings.deepseek_input_usd_per_mtok
            + float(output_tokens) / 1_000_000 * settings.deepseek_output_usd_per_mtok,
            6,
        )
    except Exception:  # noqa: BLE001 - observability không bao giờ được làm hỏng dashboard chính
        return None


def flush_traces() -> None:
    """Đẩy nốt trace còn trong buffer.

    Bắt buộc gọi ở cuối job chạy nền: Langfuse gửi theo batch nền, mà job kết thúc thì không còn ai
    kích hoạt việc gửi — không flush là trace không bao giờ lên dashboard dù code chạy đúng.
    """
    if not _ensure_client():
        return
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception:  # noqa: BLE001 - observability không bao giờ được làm hỏng nghiệp vụ
        return
