from uuid import uuid4

import pytest
from sqlalchemy import func, select, text

from src.config import get_settings
from src.model.enums import DocumentDomain, DocumentStatus, ProjectStatus, UserStatus
from src.model.knowledge_document import KnowledgeDocument
from src.model.project import Project
from src.model.session import AsyncSessionLocal
from src.model.user import User


@pytest.mark.asyncio
async def test_postgres_allows_staged_document_without_active_version() -> None:
    """Exercise the migrated PostgreSQL schema; SQLite cannot reproduce constraint triggers."""

    database_url = get_settings().database_url
    if "postgresql" not in database_url or "test-db" not in database_url:
        pytest.skip("requires the isolated PostgreSQL migration-test container")

    async with AsyncSessionLocal() as session:
        suffix = uuid4().hex
        user = User(
            email=f"staged-doc-{suffix}@example.test",
            display_name="Staged document migration test",
            status=UserStatus.ACTIVE,
        )
        session.add(user)
        await session.flush()
        project = Project(
            key=f"STAGED{suffix[:8].upper()}",
            name="Staged document lifecycle",
            created_by_admin_id=user.user_id,
            status=ProjectStatus.ACTIVE,
            github_repo="owner/repo",
            default_branch="main",
        )
        session.add(project)
        await session.flush()
        document = KnowledgeDocument(
            project_id=project.project_id,
            created_by_user_id=user.user_id,
            knowledge_domain=DocumentDomain.PROJECT,
            document_category=None,
            category_confirmed=False,
            category_classification_status="AMBIGUOUS",
            category_review_reason="migration regression test",
            source_key=f"github:owner/repo:docs/{suffix}.md",
            source_repo="owner/repo",
            title="Ambiguous document",
            source_url=f"https://github.com/owner/repo/blob/main/docs/{suffix}.md",
            status=DocumentStatus.ACTIVE,
        )
        session.add(document)
        await session.commit()

        assert await session.scalar(
            select(func.count()).select_from(KnowledgeDocument).where(
                KnowledgeDocument.document_id == document.document_id
            )
        ) == 1
        trigger_count = await session.scalar(
            text(
                "SELECT count(*) FROM pg_trigger "
                "WHERE tgname IN ('trg_document_versions_one_active', "
                "'trg_knowledge_documents_one_active') AND NOT tgisinternal"
            )
        )
        assert trigger_count == 0
