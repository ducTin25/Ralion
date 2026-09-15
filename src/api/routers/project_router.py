from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.dto.request.project_request_dto import ProjectCreateRequestDTO, ProjectUpdateRequestDTO
from src.dto.response.project_response_dto import ProjectResponseDTO
from src.model.session import get_db
from src.modules.knowledge.ingestion import github_credential_provider
from src.services import project_service

# Prefix "/pm" trên từng path operation (không đặt ở APIRouter) để đánh dấu rõ đây là
# API thuộc module PM (Thành viên 1) — tránh trùng route với module Admin (Thành viên 4)
# nếu sau này cả 2 cùng thao tác trên entity Project.
router = APIRouter(prefix="/projects", tags=["pm-projects"])

# Ràng buộc trên bảng `projects` mà tầng API cần phân biệt khi ghi thất bại.
_PROJECT_CONSTRAINTS = ("uq_projects_key", "fk_projects_created_by_admin_id_users")


def _violated_constraint(exc: IntegrityError) -> str | None:
    """Tên ràng buộc thật đã bị vi phạm, hoặc None nếu không xác định được.

    asyncpg (Postgres) đưa sẵn `constraint_name`. SQLite — dùng ở test nghiệp vụ — không có
    thuộc tính đó, nên đọc tiếp từ thông điệp lỗi thay vì trả về None và mất luôn khả năng
    phân biệt ở tầng test.
    """
    orig = getattr(exc, "orig", None)
    name = getattr(orig, "constraint_name", None)
    if name:
        return str(name)
    message = str(orig or exc)
    return next((c for c in _PROJECT_CONSTRAINTS if c in message), None)


@router.post("/pm", response_model=ProjectResponseDTO, status_code=201)
async def create_project(dto: ProjectCreateRequestDTO, db: AsyncSession = Depends(get_db)) -> ProjectResponseDTO:
    try:
        project = await project_service.create_project(db, dto)
    except IntegrityError as exc:
        await db.rollback()
        # Trước đây MỌI IntegrityError đều bị báo là "Project key already exists". Vi phạm FK
        # `created_by_admin_id` (admin không tồn tại) cũng nhận đúng thông báo đó, khiến người
        # debug đi tìm key trùng trong khi nguyên nhân thật nằm chỗ khác. Phân biệt theo tên
        # ràng buộc thật mà DB trả về, không đoán từ loại exception.
        constraint = _violated_constraint(exc)
        if constraint == "uq_projects_key":
            raise HTTPException(status_code=409, detail="Project key already exists") from exc
        if constraint == "fk_projects_created_by_admin_id_users":
            raise HTTPException(
                status_code=422, detail="created_by_admin_id does not reference an existing user"
            ) from exc
        raise HTTPException(
            status_code=409,
            detail=f"Project violates a database constraint: {constraint or 'unknown'}",
        ) from exc
    # A project that has just been created can never have a credential row yet (it's keyed by
    # the project_id just minted here) — pass None directly instead of a guaranteed-empty query.
    return ProjectResponseDTO.from_entity(project, credential_status=None)


@router.get("/pm", response_model=list[ProjectResponseDTO])
async def list_projects(
    limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_db)
) -> list[ProjectResponseDTO]:
    projects = await project_service.list_projects(db, limit=limit, offset=offset)
    return [
        ProjectResponseDTO.from_entity(
            p, credential_status=await github_credential_provider.get_status(db, p.project_id)
        )
        for p in projects
    ]


@router.get("/pm/{project_id}", response_model=ProjectResponseDTO)
async def get_project(project_id: int, db: AsyncSession = Depends(get_db)) -> ProjectResponseDTO:
    project = await project_service.get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    credential_status = await github_credential_provider.get_status(db, project_id)
    return ProjectResponseDTO.from_entity(project, credential_status=credential_status)


@router.patch("/pm/{project_id}", response_model=ProjectResponseDTO)
async def update_project(
    project_id: int, dto: ProjectUpdateRequestDTO, db: AsyncSession = Depends(get_db)
) -> ProjectResponseDTO:
    project = await project_service.update_project(db, project_id, dto)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    credential_status = await github_credential_provider.get_status(db, project_id)
    return ProjectResponseDTO.from_entity(project, credential_status=credential_status)


@router.delete("/pm/{project_id}", response_model=ProjectResponseDTO)
async def archive_project(project_id: int, db: AsyncSession = Depends(get_db)) -> ProjectResponseDTO:
    """Xoá mềm — chuyển status sang ARCHIVED, không xoá row thật."""
    project = await project_service.archive_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    credential_status = await github_credential_provider.get_status(db, project_id)
    return ProjectResponseDTO.from_entity(project, credential_status=credential_status)
