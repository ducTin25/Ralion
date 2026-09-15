from pydantic import BaseModel, Field, field_validator

from src.model.enums import DocumentCategory


class ScanSelectionItemDTO(BaseModel):
    candidate_id: str
    include: bool
    category: DocumentCategory
    title: str | None = None


class ImportScanSelectionRequestDTO(BaseModel):
    selections: list[ScanSelectionItemDTO]


class ConfirmProjectDocumentCategoryRequestDTO(BaseModel):
    category: DocumentCategory


class ConnectGithubRepoRequestDTO(BaseModel):
    """PM trỏ project tới 1 GitHub repo thật để `github_sync_worker.sync_docs` đồng bộ — thay thế
    giá trị `pending/<key>` gán mặc định lúc tạo project (xem project_service.create_project).

    `github_token` là 1 fine-grained Personal Access Token do chính PM tạo, scope
    `Contents: Read-only` cho đúng repo này — server validate ngay bằng 1 lệnh gọi GitHub thật
    trước khi lưu (xem project_service.connect_github_repo), mã hoá tại
    `project_github_credentials`, không bao giờ trả lại nguyên văn qua bất kỳ response nào."""

    github_repo: str = Field(..., min_length=3, description="Dạng owner/repo")
    default_branch: str = Field(default="main", min_length=1)
    github_token: str = Field(
        ..., min_length=4, repr=False, description="Fine-grained PAT, Contents: Read-only"
    )

    @field_validator("github_repo")
    @classmethod
    def _validate_owner_repo(cls, value: str) -> str:
        owner, separator, name = value.strip().partition("/")
        if not separator or not owner or not name or "/" in name:
            raise ValueError('github_repo phải theo định dạng "owner/repo"')
        return f"{owner}/{name}"
