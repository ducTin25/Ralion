from uuid import uuid4

import pytest
from sqlalchemy import func, select

from src.ai.providers.embeddings_fake import FakeEmbedder
from src.model.document_chunk import DocumentChunk
from src.model.document_version import DocumentVersion
from src.model.enums import DocumentCategory, ProjectStatus, SyncStatus, UserStatus
from src.model.knowledge_document import KnowledgeDocument
from src.model.project import Project
from src.model.user import User
from src.modules.knowledge.ingestion.github_client import GithubFile
from src.modules.knowledge.ingestion.github_sync_worker import sync_docs
from src.services.knowledge_document_service import confirm_project_document_category


class _MixedClassificationGithubClient:
    _content = {
        "README.md": "# Demo repository\n\nAn introduction to the service.",
        "docs/proposals-accepted/ambiguous.md": (
            "# Reference\n\nA short collection of unrelated observations."
        ),
    }

    def get_branch_head_sha(self, repo: str, branch: str) -> str:
        assert repo == "owner/repo"
        assert branch == "main"
        return "abc123"

    def list_files(
        self, repo: str, pattern: str, exclude: tuple[str, ...], *, ref: str
    ) -> list[GithubFile]:
        assert repo == "owner/repo"
        assert ref == "abc123"
        assert exclude == ()
        if pattern == "README.md":
            return [GithubFile("README.md")]
        if pattern == "docs/proposals-accepted/**/*.md":
            return [GithubFile("docs/proposals-accepted/ambiguous.md")]
        return []

    def get_file_content(self, repo: str, path: str, *, ref: str) -> str:
        assert repo == "owner/repo"
        assert ref == "abc123"
        return self._content[path]


@pytest.mark.asyncio
async def test_mixed_github_sync_stages_ambiguous_then_ingests_after_hitl(db_session) -> None:
    user = User(
        email=f"github-sync-{uuid4().hex}@example.test",
        display_name="GitHub Sync PM",
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    await db_session.flush()
    project = Project(
        key=f"SYNC{uuid4().hex[:8].upper()}",
        name="Mixed GitHub Sync",
        created_by_admin_id=user.user_id,
        status=ProjectStatus.ACTIVE,
        github_repo="owner/repo",
        default_branch="main",
    )
    db_session.add(project)
    await db_session.commit()

    # A GithubClient is injected directly (client=client), so sync_docs never has to resolve a
    # credential (see `owns_client` in github_sync_worker.sync_docs) — no
    # project_github_credentials row or GITHUB_TOKEN needed for this test.
    client = _MixedClassificationGithubClient()
    embedder = FakeEmbedder()
    synced_count = await sync_docs(db_session, project, embedder, client=client)

    await db_session.refresh(project)
    assert project.sync_status == SyncStatus.PARTIAL
    assert project.last_synced_at is not None
    documents = list(
        (
            await db_session.scalars(
                select(KnowledgeDocument)
                .where(KnowledgeDocument.project_id == project.project_id)
                .order_by(KnowledgeDocument.source_key)
            )
        ).all()
    )
    assert len(documents) == 2
    assert synced_count == 2
    ambiguous = next(document for document in documents if not document.category_confirmed)
    assert ambiguous.document_category is None
    assert await db_session.scalar(
        select(func.count())
        .select_from(DocumentVersion)
        .where(DocumentVersion.document_id == ambiguous.document_id)
    ) == 0
    assert await db_session.scalar(select(func.count()).select_from(DocumentVersion)) == 1

    await confirm_project_document_category(
        db_session,
        project_id=project.project_id,
        document_id=ambiguous.document_id,
        category=DocumentCategory.ARCHITECTURE,
    )
    await sync_docs(db_session, project, embedder, client=client)

    await db_session.refresh(project)
    await db_session.refresh(ambiguous)
    assert project.sync_status == SyncStatus.SUCCESS
    assert ambiguous.category_confirmed is True
    assert ambiguous.document_category == DocumentCategory.ARCHITECTURE
    assert await db_session.scalar(
        select(func.count())
        .select_from(DocumentVersion)
        .where(DocumentVersion.document_id == ambiguous.document_id)
    ) == 1
    assert await db_session.scalar(
        select(func.count())
        .select_from(DocumentChunk)
        .join(DocumentVersion, DocumentChunk.version_id == DocumentVersion.version_id)
        .where(DocumentVersion.document_id == ambiguous.document_id)
    ) >= 1
