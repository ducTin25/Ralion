from datetime import datetime

from pydantic import BaseModel, Field


class GenerateCandidatePlanRequestDTO(BaseModel):
    """Chỉ nhận membership_id — project_id/template_version_id do backend tự tra từ membership,
    KHÔNG nhận từ client (SoT §19: "kiểm tra membership ở backend, không tin projectId từ frontend")."""

    membership_id: int = Field(gt=0)
    # PM chọn ở modal "giờ bắt đầu" trước khi bấm sinh — cho hàm compute_due_dates() tính hạn từng
    # task nối tiếp nhau kể từ mốc này. Không truyền thì rơi về giờ gọi API (hành vi cũ).
    start_at: datetime | None = None


class GenerateReferencePlanRequestDTO(BaseModel):
    """Sinh/tạo lại lộ trình chuẩn của dự án — cấp project, không gắn kỹ sư nào."""

    project_id: int = Field(gt=0)
