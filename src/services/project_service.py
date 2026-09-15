from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dto.request.project_request_dto import ProjectCreateRequestDTO, ProjectUpdateRequestDTO
from src.model.enums import ProjectStatus
from src.model.project import Project
from src.modules.knowledge.ingestion import github_credential_provider
from src.modules.knowledge.ingestion.github_client import GithubClient
from src.services import onboarding_template_service


class GithubCredentialValidationError(ValueError):
    """The PAT supplied at connect-time could not prove read access to the exact repo/branch
    being connected. Raised instead of persisting anything, so a failed connect attempt never
    leaves `Project.github_repo` pointing at a repo the stored credential can't actually read."""


async def create_project(db: AsyncSession, dto: ProjectCreateRequestDTO) -> Project:
    # SoT §11.16: mỗi project phải tự có 1 Project Template ngay khi tạo (fork từ Global Master
    # Template) — nếu chưa có GLOBAL template đã duyệt, không cho tạo project, báo lỗi rõ ràng
    # thay vì tạo project với template rỗng.
    global_template = await onboarding_template_service.get_approved_global_template(db)
    if global_template is None:
        raise HTTPException(
            status_code=422,
            detail="Chưa có Global Master Template đã duyệt — không thể tạo project mới.",
        )

    project = Project(
        key=dto.key.upper(),
        name=dto.name,
        github_repo=f"pending/{dto.key.lower()}",
        default_branch="main",
        created_by_admin_id=dto.created_by_admin_id,
    )
    db.add(project)
    await db.flush()

    await onboarding_template_service.materialize_project_template(db, project, global_template)

    await db.commit()
    await db.refresh(project)
    return project


async def get_project(db: AsyncSession, project_id: int) -> Project | None:
    return await db.get(Project, project_id)


async def list_projects(db: AsyncSession, limit: int = 50, offset: int = 0) -> list[Project]:
    result = await db.execute(select(Project).order_by(Project.project_id).limit(limit).offset(offset))
    return list(result.scalars().all())


async def update_project(db: AsyncSession, project_id: int, dto: ProjectUpdateRequestDTO) -> Project | None:
    project = await db.get(Project, project_id)
    if project is None:
        return None
    if dto.name is not None:
        project.name = dto.name
    if dto.status is not None:
        project.status = dto.status
    await db.commit()
    await db.refresh(project)
    return project


async def connect_github_repo(
    db: AsyncSession, project_id: int, github_repo: str, default_branch: str, github_token: str
) -> Project | None:
    """PM trỏ project sang 1 repo GitHub thật (thay `pending/<key>` gán lúc tạo) kèm 1 Personal
    Access Token do chính PM cung cấp — token này auth cho đúng repo đó, không còn phụ thuộc 1
    GITHUB_TOKEN/GITHUB_TOKEN_OWNER toàn cục (chỉ hoạt động khi mọi project cùng 1 owner).

    Validate ngay tại đây bằng 1 lệnh gọi GitHub thật (`get_branch_head_sha`) thay vì hoãn sang
    lần sync đầu tiên như trước — token/repo/branch sai bị từ chối trước khi ghi bất kỳ gì vào
    DB, nên `Project.github_repo` không bao giờ trỏ vào 1 repo mà credential đã lưu không đọc
    được. Chỉ khi validate thành công mới ghi repo/branch lên `Project` và lưu token đã mã hoá
    (`github_credential_provider.store_validated_token`) trong cùng transaction ngầm hiểu — cả
    hai cùng commit, hoặc cùng không."""
    project = await db.get(Project, project_id)
    if project is None:
        return None
    try:
        GithubClient(github_token).get_branch_head_sha(github_repo, default_branch)
    except Exception as exc:
        raise GithubCredentialValidationError(
            f"Không thể xác minh quyền đọc {github_repo}@{default_branch} bằng token đã cung cấp: {exc}"
        ) from exc
    project.github_repo = github_repo
    project.default_branch = default_branch
    await db.commit()
    await db.refresh(project)
    await github_credential_provider.store_validated_token(db, project_id, github_token)
    return project


async def archive_project(db: AsyncSession, project_id: int) -> Project | None:
    """Xoá mềm: chuyển status = ARCHIVED thay vì xoá row (không hard-delete)."""
    project = await db.get(Project, project_id)
    if project is None:
        return None
    project.status = ProjectStatus.ARCHIVED
    await db.commit()
    await db.refresh(project)
    return project
