from pydantic import BaseModel


class OnboardingTemplateCreateRequestDTO(BaseModel):
    """Không dùng từ UI PM — project mới tự có template qua project_service.create_project.
    Chỉ dùng để backfill project cũ (tạo trước khi Phase 2 tồn tại) hoặc test qua Swagger."""

    project_id: int
