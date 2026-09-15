"""Regression coverage for the project-isolation bug in `ingest_or_update`.

Reproduces exactly what the manual E2E session found: two PROJECT-scoped documents built from
the same `source_key` (same GitHub repo/path) used to collide on the single
`(knowledge_domain, source_key)` unique index, so the second project's sync silently found and
mutated the first project's row instead of creating its own — see CHANGE_LOG.md and
`uq_knowledge_documents_project_source_key`.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from src.ai.providers.embeddings_fake import FakeEmbedder
from src.model.enums import DocumentCategory, DocumentDomain, UserStatus
from src.model.knowledge_document import KnowledgeDocument
from src.model.project import Project
from src.model.user import User
from src.modules.knowledge.ingestion.versioning import ProjectIngestRequest, ingest_or_update

REPO = "thanos-io/objstore"
SOURCE_KEY = f"github:{REPO}:README.md"


async def _seed_admin(db_session) -> User:
    admin = User(email="admin@iso.dev", display_name="Admin", status=UserStatus.ACTIVE)
    db_session.add(admin)
    await db_session.flush()
    return admin


async def _seed_project(db_session, admin: User, key: str) -> Project:
    project = Project(
        key=key, name=key, created_by_admin_id=admin.user_id, github_repo=REPO, default_branch="main"
    )
    db_session.add(project)
    await db_session.flush()
    return project


def _request(
    project: Project, admin: User, *, content: str, source_ref: str = "deadbeef"
) -> ProjectIngestRequest:
    return ProjectIngestRequest(
        project_id=project.project_id,
        created_by_user_id=admin.user_id,
        source_key=SOURCE_KEY,
        source_url=f"https://github.com/{REPO}/blob/main/README.md",
        source_repo=REPO,
        source_path="README.md",
        document_category=DocumentCategory.OVERVIEW,
        raw_content=content,
        source_ref=source_ref,
        title="Readme",
        category_confirmed=True,
        category_classification_status="CLASSIFIED",
    )


@pytest.mark.asyncio
async def test_same_repo_path_in_two_projects_creates_two_documents(db_session):
    admin = await _seed_admin(db_session)
    project_a = await _seed_project(db_session, admin, "PROJA")
    project_b = await _seed_project(db_session, admin, "PROJB")
    embedder = FakeEmbedder()

    doc_a = await ingest_or_update(db_session, _request(project_a, admin, content="# Readme\n\nA content."), embedder)
    await db_session.commit()
    doc_b = await ingest_or_update(db_session, _request(project_b, admin, content="# Readme\n\nB content."), embedder)
    await db_session.commit()

    assert doc_a.document_id != doc_b.document_id
    assert doc_a.project_id == project_a.project_id
    assert doc_b.project_id == project_b.project_id

    rows = (
        await db_session.scalars(
            select(KnowledgeDocument).where(
                KnowledgeDocument.knowledge_domain == DocumentDomain.PROJECT,
                KnowledgeDocument.source_key == SOURCE_KEY,
            )
        )
    ).all()
    assert {row.project_id for row in rows} == {project_a.project_id, project_b.project_id}


@pytest.mark.asyncio
async def test_resync_within_one_project_updates_in_place(db_session):
    admin = await _seed_admin(db_session)
    project = await _seed_project(db_session, admin, "PROJC")
    embedder = FakeEmbedder()

    first = await ingest_or_update(db_session, _request(project, admin, content="# Readme\n\nv1."), embedder)
    await db_session.commit()
    first_id = first.document_id

    second = await ingest_or_update(
        db_session,
        _request(project, admin, content="# Readme\n\nv2, changed.", source_ref="cafebabe"),
        embedder,
    )
    await db_session.commit()

    assert second.document_id == first_id
    count = await db_session.scalar(
        select(KnowledgeDocument.document_id).where(
            KnowledgeDocument.knowledge_domain == DocumentDomain.PROJECT,
            KnowledgeDocument.project_id == project.project_id,
            KnowledgeDocument.source_key == SOURCE_KEY,
        )
    )
    assert count == first_id


@pytest.mark.asyncio
async def test_syncing_a_second_project_never_mutates_the_first_projects_document(db_session):
    admin = await _seed_admin(db_session)
    project_a = await _seed_project(db_session, admin, "PROJD")
    project_b = await _seed_project(db_session, admin, "PROJE")
    embedder = FakeEmbedder()

    doc_a = await ingest_or_update(db_session, _request(project_a, admin, content="# Readme\n\nOriginal A."), embedder)
    await db_session.commit()
    original_title = doc_a.title
    original_updated_at = doc_a.updated_at

    await ingest_or_update(db_session, _request(project_b, admin, content="# Readme\n\nProject B content."), embedder)
    await db_session.commit()

    await db_session.refresh(doc_a)
    assert doc_a.project_id == project_a.project_id
    assert doc_a.title == original_title
    assert doc_a.updated_at == original_updated_at
