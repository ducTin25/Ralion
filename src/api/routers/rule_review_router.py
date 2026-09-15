from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.providers.embeddings import Embedder
from src.api.dependencies import (
    get_current_user,
    get_embedder,
    require_pm_or_admin,
    require_project_member,
)
from src.dto.response.rule_review_dto import (
    MemberConventionListDTO,
    RuleFamilyActionResultDTO,
    RuleFamilyListDTO,
)
from src.model.enums import ProjectRole
from src.model.project import Project
from src.model.project_membership import ProjectMembership
from src.model.session import get_db
from src.model.user import User
from src.services import rule_review_service
from src.services.rule_review_service import (
    RuleFamilyAlreadyReviewedError,
    RuleFamilyNotApprovedError,
    RuleFamilyNotFoundError,
)

router = APIRouter(tags=["f6-rule-mining"])


async def _project_repo_or_404(db: AsyncSession, project_id: int) -> str:
    """The PM review queue is scoped by the project's connected GitHub repo (F6 families carry
    no `project_id`, only a transitive repo via evidence — see `_resolve_family_repos`). A
    project with no repo connected yet (or still the `pending/<key>` placeholder, see
    `github_sync_worker.ensure_repo_target_configured`) simply has nothing that can match, which
    is the same case as any project with zero mined conventions — no special-case needed."""
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project.github_repo or ""


@router.get("/pm/projects/{project_id}/rule-candidates/pending", response_model=RuleFamilyListDTO)
async def list_pending_rule_candidates(
    project_id: int,
    _membership: Annotated[ProjectMembership | None, Depends(require_project_member(ProjectRole.PM))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> RuleFamilyListDTO:
    repo = await _project_repo_or_404(db, project_id)
    return await rule_review_service.list_pending(db, page=page, page_size=page_size, repo=repo)


@router.get("/pm/projects/{project_id}/rule-candidates/approved", response_model=RuleFamilyListDTO)
async def list_approved_rule_candidates(
    project_id: int,
    _membership: Annotated[ProjectMembership | None, Depends(require_project_member(ProjectRole.PM))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> RuleFamilyListDTO:
    """The PM Review Queue's own "Đã duyệt" tab — project-scoped. Distinct from `GET
    /conventions` below, which stays company-wide for the chat Member Conventions panel."""
    repo = await _project_repo_or_404(db, project_id)
    return await rule_review_service.list_approved(db, page=page, page_size=page_size, repo=repo)


@router.post(
    "/pm/projects/{project_id}/rule-candidates/{rule_family_id}/approve",
    response_model=RuleFamilyActionResultDTO,
)
async def approve_rule_candidate(
    project_id: int,
    rule_family_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    _membership: Annotated[ProjectMembership | None, Depends(require_project_member(ProjectRole.PM))],
    db: Annotated[AsyncSession, Depends(get_db)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
) -> RuleFamilyActionResultDTO:
    """Approving also indexes the rule into the shared retrieval engine so F5 can answer
    from it (Phase 10 §4, event-driven — no cron sweep). A failed index does not fail the
    approval; the response carries `retrieval_indexed=false` and /reindex is the retry."""
    repo = await _project_repo_or_404(db, project_id)
    try:
        return await rule_review_service.approve(
            db, rule_family_id, current_user, repo=repo, embedder=embedder
        )
    except RuleFamilyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule candidate not found") from exc
    except RuleFamilyAlreadyReviewedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Rule candidate already reviewed"
        ) from exc


@router.post(
    "/pm/projects/{project_id}/rule-candidates/{rule_family_id}/reject",
    response_model=RuleFamilyActionResultDTO,
)
async def reject_rule_candidate(
    project_id: int,
    rule_family_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    _membership: Annotated[ProjectMembership | None, Depends(require_project_member(ProjectRole.PM))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RuleFamilyActionResultDTO:
    repo = await _project_repo_or_404(db, project_id)
    try:
        return await rule_review_service.reject(db, rule_family_id, current_user, repo=repo)
    except RuleFamilyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule candidate not found") from exc
    except RuleFamilyAlreadyReviewedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Rule candidate already reviewed"
        ) from exc


@router.get("/conventions", response_model=RuleFamilyListDTO)
async def list_conventions(
    _: Annotated[User, Depends(require_pm_or_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> RuleFamilyListDTO:
    """Company-wide approved conventions — kept unscoped on purpose. This is the one endpoint
    the chat Member Conventions panel (`frontend/src/features/chat/components/
    ConventionsPanel.tsx`) reads, which has no project in scope (chat sessions can be
    company-scoped). It only ever serves HITL-approved content; the PM's own project-scoped
    "Đã duyệt" tab uses `GET /pm/projects/{project_id}/rule-candidates/approved` above."""
    return await rule_review_service.list_approved(db, page=page, page_size=page_size)


@router.get("/projects/{project_id}/conventions", response_model=MemberConventionListDTO)
async def list_member_conventions(
    project_id: int,
    _: Annotated[ProjectMembership | None, Depends(require_project_member(ProjectRole.ENGINEER))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 50,
) -> MemberConventionListDTO:
    """Member handbook read: authorized project scope, approved rules, no AI/retrieval work."""
    return await rule_review_service.list_member_conventions(
        db, project_id=project_id, page=page, page_size=page_size
    )


@router.post(
    "/pm/projects/{project_id}/rule-candidates/{rule_family_id}/reindex",
    response_model=RuleFamilyActionResultDTO,
)
async def reindex_rule_candidate(
    project_id: int,
    rule_family_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    _membership: Annotated[ProjectMembership | None, Depends(require_project_member(ProjectRole.PM))],
    db: Annotated[AsyncSession, Depends(get_db)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
) -> RuleFamilyActionResultDTO:
    """Manual retry when the approve-time index failed (Phase 10 §4).

    Exists so an approved rule can never be stuck outside the retrieval engine with no way
    back in. Idempotent — safe to call on an already-indexed family.
    """
    repo = await _project_repo_or_404(db, project_id)
    try:
        return await rule_review_service.reindex(
            db, rule_family_id, repo=repo, actor_user_id=current_user.user_id, embedder=embedder
        )
    except RuleFamilyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule candidate not found") from exc
    except RuleFamilyNotApprovedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Only an approved rule can be indexed"
        ) from exc
