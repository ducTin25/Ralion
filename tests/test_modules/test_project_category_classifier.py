import pytest
from sqlalchemy import select

from src.ai.providers.embeddings_fake import FakeEmbedder
from src.model.document_chunk import DocumentChunk
from src.model.document_version import DocumentVersion
from src.model.enums import DocumentCategory, ProjectStatus, SyncStatus
from src.model.project import Project
from src.modules.knowledge.ingestion.project_category_classifier import (
    CLASSIFIER_VERSION,
    ClassificationStatus,
    classify_project_document,
)
from src.modules.knowledge.ingestion.versioning import ProjectIngestRequest, ingest_or_update
from src.services.knowledge_document_service import confirm_project_document_category


@pytest.mark.parametrize(
    ("source_path", "title", "content", "expected"),
    [
        (
            "README.md",
            "Ralion",
            "# Ralion\n\nAn introduction to the onboarding service.",
            DocumentCategory.OVERVIEW,
        ),
        (
            "docs/getting-started.md",
            "Getting Started",
            "# Prerequisites\n\nInstall dependencies for local development.",
            DocumentCategory.SETUP,
        ),
        (
            "docs/architecture/system-design.md",
            "System design",
            "# Architecture\n\nMajor component boundaries are documented here.",
            DocumentCategory.ARCHITECTURE,
        ),
        (
            "docs/security/access.md",
            "Access control",
            "# Authentication\n\nRBAC permissions protect credentials.",
            DocumentCategory.ACCESS_SECURITY,
        ),
        (
            "docs/contributing/style-guide.md",
            "Coding style guide",
            "# Naming\n\nFollow the commit convention.",
            DocumentCategory.CONVENTION,
        ),
        (
            "docs/onboarding/first-contribution.md",
            "First contribution",
            "# Good first issue\n\nChoose a beginner task.",
            DocumentCategory.FIRST_TASK,
        ),
    ],
)
def test_classifier_uses_path_title_heading_and_body_signals(
    source_path: str, title: str, content: str, expected: DocumentCategory
) -> None:
    result = classify_project_document(source_path=source_path, title=title, content=content)

    assert result.category is expected
    assert result.status == ClassificationStatus.CLASSIFIED
    assert result.confidence >= 0.7
    assert result.matched_signals
    assert result.classifier_version == CLASSIFIER_VERSION


def test_classifier_returns_ambiguous_instead_of_defaulting_to_overview() -> None:
    result = classify_project_document(
        source_path="docs/reference.md",
        title="Reference",
        content="# Architecture\n\n# Codebase\n\nRepository structure and system design notes.",
    )

    assert result.category is None
    assert result.status == ClassificationStatus.AMBIGUOUS
    assert "overview" not in result.review_reason


def test_classifier_returns_ambiguous_when_there_is_no_strong_signal() -> None:
    result = classify_project_document(
        source_path="docs/notes.md",
        title="Notes",
        content="A short collection of unrelated observations.",
    )

    assert result.category is None
    assert result.status == ClassificationStatus.AMBIGUOUS
    assert result.confidence == 0.0


@pytest.mark.asyncio
async def test_ambiguous_document_is_staged_without_embedding(db_session) -> None:
    document = await ingest_or_update(
        db_session,
        ProjectIngestRequest(
            project_id=1,
            created_by_user_id=1,
            source_key="github:owner/repo:docs/notes.md",
            source_url="https://github.com/owner/repo/blob/main/docs/notes.md",
            source_repo="owner/repo",
            source_path="docs/notes.md",
            document_category=None,
            raw_content="A short collection of unrelated observations.",
            source_ref="abc123",
            title="Notes",
            category_classification_status=ClassificationStatus.AMBIGUOUS.value,
            category_review_reason="ambiguous by project-category-rules-v1",
            classifier_version=CLASSIFIER_VERSION,
        ),
        embedder=object(),
    )

    assert document.document_category is None
    assert document.category_confirmed is False
    assert document.category_classification_status == ClassificationStatus.AMBIGUOUS.value
    assert document.document_category_classifier_version == CLASSIFIER_VERSION
    assert list((await db_session.scalars(select(DocumentVersion))).all()) == []


@pytest.mark.asyncio
async def test_confirmed_document_creates_version_and_embeddings(db_session) -> None:
    document = await ingest_or_update(
        db_session,
        ProjectIngestRequest(
            project_id=1,
            created_by_user_id=1,
            source_key="github:owner/repo:docs/setup.md",
            source_url="https://github.com/owner/repo/blob/main/docs/setup.md",
            source_repo="owner/repo",
            source_path="docs/setup.md",
            document_category=DocumentCategory.SETUP,
            raw_content="# Setup\n\nInstall the service locally.",
            source_ref="abc123",
            title="Setup",
            category_confirmed=True,
            category_classification_status=ClassificationStatus.CLASSIFIED.value,
            classifier_version=CLASSIFIER_VERSION,
        ),
        embedder=FakeEmbedder(),
    )

    assert document.category_confirmed is True
    assert document.category_classification_status == ClassificationStatus.CLASSIFIED.value
    assert len(list((await db_session.scalars(select(DocumentVersion))).all())) == 1
    assert len(list((await db_session.scalars(select(DocumentChunk))).all())) == 1


@pytest.mark.asyncio
async def test_hitl_can_confirm_a_staged_document(db_session) -> None:
    staged = await ingest_or_update(
        db_session,
        ProjectIngestRequest(
            project_id=1,
            created_by_user_id=1,
            source_key="github:owner/repo:docs/reference.md",
            source_url="https://github.com/owner/repo/blob/main/docs/reference.md",
            source_repo="owner/repo",
            source_path="docs/reference.md",
            document_category=None,
            raw_content="Reference notes.",
            source_ref="abc123",
            title="Reference",
            category_classification_status=ClassificationStatus.AMBIGUOUS.value,
            classifier_version=CLASSIFIER_VERSION,
        ),
        embedder=object(),
    )
    await db_session.commit()

    confirmed = await confirm_project_document_category(
        db_session,
        project_id=1,
        document_id=staged.document_id,
        category=DocumentCategory.ARCHITECTURE,
    )

    assert confirmed.document_category == DocumentCategory.ARCHITECTURE
    assert confirmed.category_confirmed is True
    assert confirmed.category_classification_status == ClassificationStatus.CLASSIFIED.value


@pytest.mark.asyncio
async def test_final_category_confirmation_marks_partial_sync_success(db_session) -> None:
    project = Project(
        key="HITL",
        name="HITL status",
        created_by_admin_id=1,
        status=ProjectStatus.ACTIVE,
        sync_status=SyncStatus.PARTIAL,
    )
    db_session.add(project)
    await db_session.flush()
    staged = await ingest_or_update(
        db_session,
        ProjectIngestRequest(
            project_id=project.project_id,
            created_by_user_id=1,
            source_key="github:owner/repo:docs/notes.md",
            source_url="https://github.com/owner/repo/blob/main/docs/notes.md",
            source_repo="owner/repo",
            source_path="docs/notes.md",
            document_category=None,
            raw_content="Reference notes.",
            source_ref="abc123",
            title="Notes",
            category_classification_status=ClassificationStatus.AMBIGUOUS.value,
            classifier_version=CLASSIFIER_VERSION,
        ),
        embedder=object(),
    )
    await db_session.commit()

    await confirm_project_document_category(
        db_session,
        project_id=project.project_id,
        document_id=staged.document_id,
        category=DocumentCategory.ARCHITECTURE,
    )

    await db_session.refresh(project)
    assert project.sync_status is SyncStatus.SUCCESS


@pytest.mark.asyncio
async def test_hitl_can_override_an_already_classified_document(db_session) -> None:
    """PM catches a wrong category later (whether set by the classifier, a prior HITL
    confirm, or chosen by themselves during upload/scan-import) and corrects it. This
    must work even though the document is already CLASSIFIED, not just AMBIGUOUS."""
    document = await ingest_or_update(
        db_session,
        ProjectIngestRequest(
            project_id=1,
            created_by_user_id=1,
            source_key="github:owner/repo:docs/setup.md",
            source_url="https://github.com/owner/repo/blob/main/docs/setup.md",
            source_repo="owner/repo",
            source_path="docs/setup.md",
            document_category=DocumentCategory.ARCHITECTURE,
            raw_content="Setup instructions.",
            source_ref="def456",
            title="Setup",
            category_confirmed=True,
            category_classification_status=ClassificationStatus.CLASSIFIED.value,
            classifier_version=CLASSIFIER_VERSION,
        ),
        embedder=FakeEmbedder(),
    )
    await db_session.commit()
    original_version_count = len(list((await db_session.scalars(select(DocumentVersion))).all()))

    overridden = await confirm_project_document_category(
        db_session,
        project_id=1,
        document_id=document.document_id,
        category=DocumentCategory.SETUP,
    )

    assert overridden.document_category == DocumentCategory.SETUP
    assert overridden.category_confirmed is True
    assert overridden.category_classification_status == ClassificationStatus.CLASSIFIED.value
    assert "ARCHITECTURE -> " in overridden.category_review_reason
    # Metadata-only correction: no new version/chunk is created.
    assert (
        len(list((await db_session.scalars(select(DocumentVersion))).all()))
        == original_version_count
    )
