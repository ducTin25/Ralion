"""Router KnowledgeDocument — đọc chính sách công ty (POLICY, dùng cho Company Core) + Phase 3:
CRUD tài liệu dự án thật (PROJECT domain), upload đơn lẻ, quét folder (UC-04) và import từ Coverage
Report. Không có endpoint nào extract/chunk/embedding — thuộc phạm vi TV3 (SoT §17)."""

import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.providers.embeddings import Embedder
from src.api.dependencies import get_current_user, get_embedder, require_project_member
from src.dto.request.knowledge_document_request_dto import (
    ConfirmProjectDocumentCategoryRequestDTO,
    ConnectGithubRepoRequestDTO,
    ImportScanSelectionRequestDTO,
)
from src.dto.response.discovery_schedule_response_dto import IngestionJobResponseDTO
from src.dto.response.knowledge_document_response_dto import (
    KnowledgeDocumentResponseDTO,
    ProjectDocumentContentResponseDTO,
    ProjectDocumentResponseDTO,
)
from src.dto.response.project_response_dto import ProjectResponseDTO
from src.dto.response.repo_scan_response_dto import CoverageReportResponseDTO
from src.model.enums import (
    IngestionJobTriggerType,
    IngestionJobType,
    ProjectRole,
    SyncStatus,
)
from src.model.ingestion_job import IngestionJob
from src.model.project_membership import ProjectMembership
from src.model.session import AsyncSessionLocal, get_db
from src.model.user import User
from src.modules.knowledge.ingestion import github_credential_provider, github_sync_worker
from src.services import (
    knowledge_document_service,
    operation_job_service,
    project_service,
    repo_scanner_service,
)
from src.shared.ai.external_failures import ExternalServiceFailure

router = APIRouter(prefix="/knowledge-documents", tags=["knowledge-documents"])
logger = logging.getLogger(__name__)

_GITHUB_SYNC_FAILURE_MESSAGE = (
    "Không thể đồng bộ tài liệu từ GitHub. Vui lòng thử lại hoặc liên hệ quản trị viên."
)
_EMBEDDING_UNAVAILABLE_MESSAGE = (
    "Dịch vụ embedding tạm thời không sẵn sàng (có thể đang khởi động lại). "
    "Vui lòng thử lại sau ít phút."
)

async def _latest_github_sync_job(db: AsyncSession, project_id: int) -> IngestionJob | None:
    return await db.scalar(
        select(IngestionJob)
        .where(
            IngestionJob.project_id == project_id,
            IngestionJob.job_type == IngestionJobType.GITHUB_SYNC,
        )
        .order_by(IngestionJob.created_at.desc(), IngestionJob.ingestion_job_id.desc())
        .limit(1)
    )


async def _run_github_sync(job_id: int, project_id: int, embedder: Embedder) -> None:
    """Run after the 202 response with a session that outlives the request."""
    async with AsyncSessionLocal() as session:
        job = await session.get(IngestionJob, job_id)
        if job is None:
            logger.warning("github_sync_job_missing", extra={"ingestion_job_id": job_id})
            return
        project = await project_service.get_project(session, project_id)
        if project is None:
            logger.warning("github_sync_project_missing", extra={"project_id": project_id})
            await operation_job_service.fail(session, job, ValueError("Project not found"))
            return
        try:
            synced_documents = await github_sync_worker.sync_docs(session, project, embedder)
            job.processed_evidence_count = synced_documents
            await operation_job_service.succeed(session, job)
        except Exception as exc:  # sync_docs persists FAILED; retain traceback for operators.
            await operation_job_service.fail(session, job, exc)
            logger.exception("github_sync_failed", extra={"project_id": project_id})


async def _run_scan_import(
    job_id: int,
    project_id: int,
    scan_session_id: str,
    selections: list[tuple[str, str, str | None]],
    created_by_user_id: int,
    embedder: Embedder,
) -> None:
    async with AsyncSessionLocal() as session:
        job = await session.get(IngestionJob, job_id)
        if job is None:
            logger.warning("document_import_job_missing", extra={"ingestion_job_id": job_id})
            return
        try:
            imported = await knowledge_document_service.import_scan_selection(
                session,
                project_id=project_id,
                scan_session_id=scan_session_id,
                selections=selections,
                created_by_user_id=created_by_user_id,
                embedder=embedder,
            )
            job.processed_evidence_count = len(imported)
            await operation_job_service.succeed(session, job)
        except Exception as exc:
            await operation_job_service.fail(session, job, exc)
            logger.exception("document_import_failed", extra={"project_id": project_id})


@router.get("/policy", response_model=list[KnowledgeDocumentResponseDTO])
async def list_policy_documents(
    db: AsyncSession = Depends(get_db),
) -> list[KnowledgeDocumentResponseDTO]:
    """Chính sách công ty chung (domain POLICY) — dùng chung mọi project, chỉ đọc."""
    documents = await knowledge_document_service.list_active_policy_documents(db)
    return [KnowledgeDocumentResponseDTO.from_entity(d) for d in documents]


@router.get("/pm/projects/{project_id}", response_model=list[ProjectDocumentResponseDTO])
async def list_project_documents(
    project_id: int,
    _membership: Annotated[ProjectMembership | None, Depends(require_project_member(ProjectRole.PM))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ProjectDocumentResponseDTO]:
    project = await project_service.get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    pairs = await knowledge_document_service.list_project_documents(db, project_id)
    return [ProjectDocumentResponseDTO.from_entity(doc, version) for doc, version in pairs]


@router.get(
    "/pm/projects/{project_id}/{document_id}/content",
    response_model=ProjectDocumentContentResponseDTO,
)
async def read_project_document_content(
    project_id: int,
    document_id: int,
    _membership: Annotated[ProjectMembership | None, Depends(require_project_member(ProjectRole.PM))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectDocumentContentResponseDTO:
    """Đọc tài liệu ngay trong app. Trả markdown đã chuẩn hoá từ nội dung ĐÃ INGEST (xem
    `knowledge_document_service.get_project_document_content` để biết vì sao không đọc file gốc)."""
    try:
        document, version, content = await knowledge_document_service.get_project_document_content(
            db, project_id=project_id, document_id=document_id
        )
    except ValueError as exc:
        status = 404 if str(exc) == "Project document not found" else 422
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    return ProjectDocumentContentResponseDTO.from_entity(document, version, content)


@router.delete("/pm/projects/{project_id}/{document_id}", status_code=204)
async def delete_project_document(
    project_id: int,
    document_id: int,
    _membership: Annotated[ProjectMembership | None, Depends(require_project_member(ProjectRole.PM))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    try:
        await knowledge_document_service.archive_project_document(
            db, project_id=project_id, document_id=document_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)


@router.patch("/pm/projects/{project_id}/{document_id}/category", response_model=ProjectDocumentResponseDTO)
async def confirm_project_document_category(
    project_id: int,
    document_id: int,
    dto: ConfirmProjectDocumentCategoryRequestDTO,
    _membership: Annotated[ProjectMembership | None, Depends(require_project_member(ProjectRole.PM))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectDocumentResponseDTO:
    try:
        document = await knowledge_document_service.confirm_project_document_category(
            db, project_id=project_id, document_id=document_id, category=dto.category
        )
    except ValueError as exc:
        raise HTTPException(status_code=404 if str(exc) == "Project document not found" else 422, detail=str(exc)) from exc
    return ProjectDocumentResponseDTO.from_entity(document, None)


@router.post("/pm/projects/{project_id}/upload", response_model=ProjectDocumentResponseDTO, status_code=201)
async def upload_project_document(
    project_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    _membership: Annotated[ProjectMembership | None, Depends(require_project_member(ProjectRole.PM))],
    db: Annotated[AsyncSession, Depends(get_db)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    category: str = Form(...),
    title: str = Form(...),
    file: UploadFile = File(...),
) -> ProjectDocumentResponseDTO:
    project = await project_service.get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    content = await file.read()
    try:
        document, version = await knowledge_document_service.import_single_file(
            db,
            project_id=project_id,
            category=category,
            title=title,
            content=content,
            created_by_user_id=current_user.user_id,
            embedder=embedder,
            # Tên file thật quyết định cách đọc nội dung (text vs nhị phân); `title` là chữ PM gõ
            # tay nên có thể không có đuôi file.
            filename=file.filename,
        )
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ExternalServiceFailure as exc:
        await db.rollback()
        logger.warning(
            "knowledge_document_upload_embedding_failed",
            extra={
                "project_id": project_id,
                "service": exc.service,
                "failure_code": exc.code.value,
                "retryable": exc.retryable,
                "attempts": exc.attempts,
            },
        )
        headers = (
            {"Retry-After": str(int(exc.retry_after_seconds))}
            if exc.retry_after_seconds is not None
            else None
        )
        raise HTTPException(
            status_code=503, detail=_EMBEDDING_UNAVAILABLE_MESSAGE, headers=headers
        ) from exc
    return ProjectDocumentResponseDTO.from_entity(document, version)


@router.post("/pm/projects/{project_id}/scan", response_model=CoverageReportResponseDTO)
async def scan_project_repository(
    project_id: int,
    _membership: Annotated[ProjectMembership | None, Depends(require_project_member(ProjectRole.PM))],
    db: Annotated[AsyncSession, Depends(get_db)],
    files: list[UploadFile] = File(...),
) -> CoverageReportResponseDTO:
    """PM chọn thẳng folder dự án (input webkitdirectory) — mỗi file gửi lên kèm đường dẫn tương
    đối qua tên file (browser đã tự đặt bằng webkitRelativePath). Không ghi DB ở bước này."""
    project = await project_service.get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    candidate_files: list[tuple[str, bytes]] = []
    for upload in files:
        relative_path = upload.filename or ""
        if not repo_scanner_service.is_candidate_file(relative_path):
            continue
        content = await upload.read()
        candidate_files.append((relative_path, content))

    existing_checksums = await knowledge_document_service.list_existing_checksums_for_project(db, project_id)
    try:
        scan_session_id, report, _ = await repo_scanner_service.build_coverage_report(
            candidate_files, existing_checksums
        )
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc

    repo_scanner_service.set_scan_session_project(scan_session_id, project_id)
    return CoverageReportResponseDTO.from_entity(scan_session_id, report)


@router.post(
    "/pm/projects/{project_id}/scan/{scan_session_id}/import",
    response_model=IngestionJobResponseDTO,
    status_code=202,
)
async def import_scan_selection(
    project_id: int,
    scan_session_id: str,
    dto: ImportScanSelectionRequestDTO,
    current_user: Annotated[User, Depends(get_current_user)],
    background_tasks: BackgroundTasks,
    _membership: Annotated[ProjectMembership | None, Depends(require_project_member(ProjectRole.PM))],
    db: Annotated[AsyncSession, Depends(get_db)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
) -> IngestionJobResponseDTO:
    project = await project_service.get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    selections = [(item.candidate_id, item.category.value, item.title) for item in dto.selections if item.include]
    if not selections:
        raise HTTPException(status_code=422, detail="Chưa chọn file nào để import")

    try:
        job = await operation_job_service.reserve(
            db,
            project_id,
            job_type=IngestionJobType.DOCUMENT_IMPORT,
            trigger_type=IngestionJobTriggerType.MANUAL,
            triggered_by_user_id=current_user.user_id,
        )
    except operation_job_service.AlreadyRunningError as exc:
        raise HTTPException(status_code=409, detail="A document import is already running") from exc
    background_tasks.add_task(
        _run_scan_import,
        job.ingestion_job_id,
        project_id,
        scan_session_id,
        selections,
        current_user.user_id,
        embedder,
    )
    return IngestionJobResponseDTO.from_entity(job)


@router.get(
    "/pm/projects/{project_id}/scan-import/{job_id}", response_model=IngestionJobResponseDTO
)
async def get_scan_import_status(
    project_id: int,
    job_id: int,
    _membership: Annotated[ProjectMembership | None, Depends(require_project_member(ProjectRole.PM))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> IngestionJobResponseDTO:
    job = await db.get(IngestionJob, job_id)
    if (
        job is None
        or job.project_id != project_id
        or job.job_type != IngestionJobType.DOCUMENT_IMPORT
    ):
        raise HTTPException(status_code=404, detail="Document import job not found")
    return IngestionJobResponseDTO.from_entity(job)


@router.patch("/pm/projects/{project_id}/github-repo", response_model=ProjectResponseDTO)
async def connect_github_repo(
    project_id: int,
    dto: ConnectGithubRepoRequestDTO,
    _membership: Annotated[ProjectMembership | None, Depends(require_project_member(ProjectRole.PM))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectResponseDTO:
    """Trỏ project sang 1 repo GitHub thật kèm 1 PAT do PM cung cấp, thay `pending/<key>` gán lúc
    tạo project — bước bắt buộc trước khi gọi được /github-sync bên dưới. Token được validate
    bằng 1 lệnh gọi GitHub thật trước khi lưu (xem project_service.connect_github_repo)."""
    try:
        project = await project_service.connect_github_repo(
            db, project_id, dto.github_repo, dto.default_branch, dto.github_token
        )
    except project_service.GithubCredentialValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    credential_status = await github_credential_provider.get_status(db, project_id)
    job = await _latest_github_sync_job(db, project_id)
    return ProjectResponseDTO.from_entity(
        project, credential_status=credential_status, github_sync_job=job
    )


@router.get("/pm/projects/{project_id}/github-sync", response_model=ProjectResponseDTO)
async def get_github_sync_status(
    project_id: int,
    _membership: Annotated[ProjectMembership | None, Depends(require_project_member(ProjectRole.PM))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectResponseDTO:
    """Small polling endpoint for the asynchronous GitHub sync lifecycle — also the only signal
    the FE has that a credential went INVALID mid-sync (see github_sync_worker.mark_invalid)."""
    project = await project_service.get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    credential_status = await github_credential_provider.get_status(db, project_id)
    job = await _latest_github_sync_job(db, project_id)
    return ProjectResponseDTO.from_entity(
        project, credential_status=credential_status, github_sync_job=job
    )


@router.post("/pm/projects/{project_id}/github-sync", response_model=ProjectResponseDTO, status_code=202)
async def sync_project_from_github(
    project_id: int,
    background_tasks: BackgroundTasks,
    _membership: Annotated[ProjectMembership | None, Depends(require_project_member(ProjectRole.PM))],
    db: Annotated[AsyncSession, Depends(get_db)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
) -> ProjectResponseDTO:
    """Đồng bộ tài liệu dự án trực tiếp từ GitHub qua `github_sync_worker.sync_docs` (đã có sẵn,
    trước đây chưa gọi được từ đâu cả). Endpoint chỉ xác thực cấu hình, giữ chỗ trạng thái
    `SYNCING` rồi trả `202`; phần tải, ingest và embedding chạy trong background task với một
    database session riêng. Frontend theo dõi tiến độ qua `GET .../github-sync`.

    Guard chặn 2 lượt chạy chồng nhau bằng job reservation có unique index theo
    `project + operation`; trạng thái job này cũng là nguồn authoritative cho frontend."""
    project = await project_service.get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    # Validate deterministic configuration before acknowledging the job. Network and per-file
    # failures are recorded as FAILED by the background worker instead of becoming a proxy 500.
    try:
        github_sync_worker.ensure_repo_target_configured(project)
        await github_credential_provider.get_token(db, project_id)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "github_sync_request_failed project_id=%s repo=%s branch=%s",
            project_id,
            project.github_repo,
            project.default_branch,
        )
        raise HTTPException(status_code=502, detail=_GITHUB_SYNC_FAILURE_MESSAGE) from exc

    project.sync_status = SyncStatus.SYNCING
    try:
        job = await operation_job_service.reserve(
            db,
            project_id,
            job_type=IngestionJobType.GITHUB_SYNC,
            trigger_type=IngestionJobTriggerType.MANUAL,
            triggered_by_user_id=_membership.user_id if _membership is not None else None,
        )
    except operation_job_service.AlreadyRunningError as exc:
        raise HTTPException(
            status_code=409, detail="Đang có một lượt đồng bộ GitHub chạy nền cho project này"
        ) from exc
    except Exception as exc:
        await db.rollback()
        logger.exception("github_sync_reservation_failed", extra={"project_id": project_id})
        raise HTTPException(status_code=502, detail=_GITHUB_SYNC_FAILURE_MESSAGE) from exc
    await db.refresh(project)
    background_tasks.add_task(
        _run_github_sync, job.ingestion_job_id, project.project_id, embedder
    )
    credential_status = await github_credential_provider.get_status(db, project_id)
    return ProjectResponseDTO.from_entity(
        project, credential_status=credential_status, github_sync_job=job
    )
