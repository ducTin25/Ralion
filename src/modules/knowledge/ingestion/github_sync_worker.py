"""P0 full-snapshot GitHub synchronisation for scoped Backstage documentation."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.providers.embeddings import Embedder
from src.core.security.secret_scan import scan as secret_scan_and_redact
from src.model.enums import DocumentDomain, DocumentStatus, SyncStatus
from src.model.knowledge_document import KnowledgeDocument
from src.model.project import Project
from src.modules.knowledge.ingestion import github_credential_provider
from src.modules.knowledge.ingestion.github_client import GithubClient
from src.modules.knowledge.ingestion.project_category_classifier import (
    ClassificationStatus,
    classify_project_document,
)
from src.modules.knowledge.ingestion.versioning import ProjectIngestRequest, ingest_or_update

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncEntry:
    path: str
    exclude: tuple[str, ...] = ()


def ensure_repo_target_configured(project: Project) -> None:
    """Repo/branch presence + shape check only — no credential involved. Reused by the
    `/github-sync` endpoint's fail-fast precheck and by `sync_docs` itself.

    `github_repo`/`default_branch` are NULL khi project chưa cấu hình GitHub — hợp lệ, vì PM có
    thể tạo project rồi tự quét thư mục/tải tài liệu tay. Chặn ở đây với thông báo rõ ràng thay
    vì để `.partition()` ném AttributeError khó hiểu ở giữa luồng đồng bộ."""
    if not project.github_repo or not project.default_branch:
        raise ValueError(
            f"Dự án {project.key!r} chưa cấu hình GitHub (github_repo/default_branch) — "
            "không đồng bộ được. Cấu hình repo + nhánh mặc định trước khi chạy GitHub sync."
        )
    # `project_service.create_project` gán "pending/<key>" lúc tạo (đợi PM connect repo thật) —
    # trước đây trường hợp này bị chặn tình cờ bởi owner không khớp GITHUB_TOKEN_OWNER; giờ
    # không còn owner toàn cục nào để so khớp nữa nên phải chặn placeholder tường minh ở đây,
    # cùng quy ước với `isGithubRepoConfigured` bên FE (GithubSyncCard.tsx).
    if project.github_repo.startswith("pending/"):
        raise ValueError(
            f"Dự án {project.key!r} chưa kết nối GitHub repo thật (vẫn là placeholder "
            f"{project.github_repo!r} gán lúc tạo project) — kết nối repo trước khi đồng bộ."
        )
    owner, separator, name = project.github_repo.partition("/")
    if not separator or not owner or not name:
        raise ValueError(f"Invalid GitHub repository coordinate: {project.github_repo!r}")


def _looks_like_github_auth_error(exc: BaseException) -> bool:
    """`GithubClient._fetch` wraps HTTPError into `RuntimeError(f"... failed with HTTP {code}")`,
    losing the structured status code. Matching the message is fragile but avoids reaching into
    GithubClient's shared retry/error path just to classify one exception for credential
    invalidation — a real 401/403 always reaches attempt 0 with this exact wording."""
    message = str(exc)
    return "HTTP 401" in message or "HTTP 403" in message


def load_sync_scope(path: str | Path = "config/knowledge_sources.yaml") -> tuple[SyncEntry, ...]:
    config = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return tuple(
        SyncEntry(item["path"], tuple(item.get("exclude", [])))
        for item in config["sync_scope"]["include"]
    )


async def sync_docs(
    session: AsyncSession,
    project: Project,
    embedder: Embedder,
    *,
    client: GithubClient | None = None,
    force_rechunk: bool = False,
) -> int:
    """Synchronise one project with small per-file transactions, never GitHub writes."""
    ensure_repo_target_configured(project)
    owns_client = client is None
    if owns_client:
        client = await github_credential_provider.build_client_for_project(session, project.project_id)
    project.sync_status = SyncStatus.SYNCING
    await session.commit()
    current_source_path: str | None = None
    try:
        commit_sha = await asyncio.to_thread(
            client.get_branch_head_sha, project.github_repo, project.default_branch
        )
        seen: set[str] = set()
        needs_category_review = False
        synced_documents = 0
        for entry in load_sync_scope():
            files = await asyncio.to_thread(
                client.list_files,
                project.github_repo,
                entry.path,
                entry.exclude,
                ref=commit_sha,
            )
            for file in files:
                current_source_path = file.path
                content = await asyncio.to_thread(
                    client.get_file_content, project.github_repo, file.path, ref=commit_sha
                )
                redaction = secret_scan_and_redact(content)
                title = _title(redaction.redacted_content, file.path)
                classification = classify_project_document(
                    source_path=file.path,
                    title=title,
                    content=redaction.redacted_content,
                )
                if classification.status == ClassificationStatus.AMBIGUOUS:
                    confirmed_category = await session.scalar(
                        select(KnowledgeDocument.document_category).where(
                            KnowledgeDocument.knowledge_domain == DocumentDomain.PROJECT,
                            KnowledgeDocument.source_key == f"github:{project.github_repo}:{file.path}",
                            KnowledgeDocument.category_confirmed.is_(True),
                            KnowledgeDocument.document_category.is_not(None),
                        )
                    )
                    if confirmed_category is not None:
                        classification = classification.__class__(
                            category=confirmed_category,
                            confidence=classification.confidence,
                            matched_signals=classification.matched_signals,
                            status=ClassificationStatus.CLASSIFIED,
                            classifier_version=classification.classifier_version,
                        )
                needs_category_review = needs_category_review or classification.category is None
                source_key = f"github:{project.github_repo}:{file.path}"
                seen.add(source_key)
                content_status = _content_status(redaction.redacted_content)
                await ingest_or_update(
                    session,
                    ProjectIngestRequest(
                        project_id=project.project_id,
                        created_by_user_id=project.created_by_admin_id,
                        source_key=source_key,
                        source_url=f"https://github.com/{project.github_repo}/blob/{project.default_branch}/{file.path}",
                        source_repo=project.github_repo,
                        source_path=file.path,
                        document_category=classification.category,
                        raw_content=redaction.redacted_content,
                        source_ref=commit_sha,
                        title=title,
                        decision_number=_decision_number(file.path),
                        content_status=content_status,
                        category_confirmed=classification.status == ClassificationStatus.CLASSIFIED,
                        category_classification_status=classification.status.value,
                        category_review_reason=(
                            classification.review_reason
                            if classification.status == ClassificationStatus.AMBIGUOUS
                            else None
                        ),
                        classifier_version=classification.classifier_version,
                    ),
                    embedder,
                    force_rechunk=force_rechunk,
                    release_before_external=True,
                )
                synced_documents += 1
                await session.commit()
        await reconcile_deleted(session, project, seen)
        project.sync_status = SyncStatus.PARTIAL if needs_category_review else SyncStatus.SUCCESS
        # The existing PostgreSQL column is TIMESTAMP WITHOUT TIME ZONE.
        # Store the UTC wall-clock value as a naive datetime, matching the
        # convention used by the other application timestamps.
        project.last_synced_at = datetime.now(UTC).replace(tzinfo=None)
        await session.commit()
        return synced_documents
    except Exception as exc:
        logger.exception(
            "github_document_sync_failed project_id=%s repo=%s branch=%s source_path=%s",
            project.project_id,
            project.github_repo,
            project.default_branch,
            current_source_path,
        )
        await session.rollback()
        if owns_client and _looks_like_github_auth_error(exc):
            await github_credential_provider.mark_invalid(session, project.project_id, str(exc))
        project.sync_status = SyncStatus.FAILED
        await session.commit()
        raise


async def reconcile_deleted(session: AsyncSession, project: Project, seen: set[str]) -> None:
    prefix = f"github:{project.github_repo}:"
    active = (await session.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.project_id == project.project_id,
            KnowledgeDocument.knowledge_domain == DocumentDomain.PROJECT,
            KnowledgeDocument.status == DocumentStatus.ACTIVE,
            KnowledgeDocument.source_key.like(f"{prefix}%"),
        )
    )).scalars()
    for document in active:
        if document.source_key not in seen:
            document.status = DocumentStatus.ARCHIVED
    await session.commit()


def _title(content: str, path: str) -> str:
    frontmatter = re.search(r"^---\s*$.*?^title:\s*['\"]?(.+?)['\"]?\s*$.*?^---\s*$", content, re.MULTILINE | re.DOTALL)
    if frontmatter:
        return frontmatter.group(1).strip()
    heading = re.search(r"^#\s+(.+?)\s*$", content, re.MULTILINE)
    return heading.group(1).strip() if heading else Path(path).stem


def _decision_number(path: str) -> str | None:
    """Extract a date-slug identifier without categorising the document type."""
    stem = Path(path).stem
    return stem if re.match(r"^\d{6,8}-[a-z0-9][a-z0-9-]*$", stem, re.IGNORECASE) else None


def _content_status(content: str) -> str | None:
    match = re.search(r"^status:\s*(.+?)\s*$", content, re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip().upper() if match else None
