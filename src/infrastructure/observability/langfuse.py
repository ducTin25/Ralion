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

from collections.abc import Callable
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


def get_langfuse_client() -> Any | None:
    """Return the already configured shared client, or ``None`` when unavailable."""
    if not _ensure_client():
        return None
    try:
        from langfuse import get_client

        return get_client()
    except Exception:  # noqa: BLE001 - observability is always fail-open
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
