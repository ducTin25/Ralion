from pydantic import BaseModel

from src.dto.response.pm_blocker_response_dto import PmBlockerResponseDTO


class PmDashboardEngineerOverdueDTO(BaseModel):
    membership_id: int
    engineer_name: str
    overdue_count: int


class PmDashboardResponseDTO(BaseModel):
    """SoT §21 (TV1): "Progress dashboard và close onboarding" — tổng hợp những gì PM đang phải
    tự cộng dồn bằng mắt qua nhiều trang (Thành viên, Blocker Engineer, Tài liệu dự án, Master
    Template) thành 1 màn hình duy nhất. Không thêm khái niệm mới nào — mọi số liệu ở đây đều suy
    ra được từ dữ liệu các trang kia đã có, không phải phát minh chỉ số mới cho riêng dashboard.
    """

    project_id: int
    project_key: str
    project_name: str

    engineer_count: int
    with_plan_count: int
    active_count: int
    done_count: int

    open_blocker_count: int
    overdue_task_count: int

    document_group_count: int
    document_group_total: int

    template_approved: bool
    template_task_count: int

    oldest_open_blockers: list[PmBlockerResponseDTO]
    engineers_with_most_overdue: list[PmDashboardEngineerOverdueDTO]

    # `None` = chưa có dữ liệu (Langfuse chưa cấu hình, lỗi mạng, hoặc dự án CHƯA từng sinh plan
    # SAU KHI tính năng gắn tag cost tồn tại — trace cũ không tự có tag, không backfill được).
    # KHÁC hẳn `0.0` (đã tính được, đúng là chưa tốn tiền) — FE phải hiện "—" cho `None`, không phải
    # "$0" (xem `src/observability/tracing.py:get_project_ai_cost_usd`).
    total_ai_cost_usd: float | None
