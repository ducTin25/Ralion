"""Version-flip persistence for PROJECT knowledge documents."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.providers.embeddings import Embedder
from src.ai.retrieval_engine.lexical import lexical_identifiers
from src.core.security.secret_scan import record_secret_findings, scan
from src.model.document_chunk import DocumentChunk
from src.model.document_version import DocumentVersion
from src.model.enums import DocumentCategory, DocumentDomain, DocumentStatus, VersionStatus
from src.model.knowledge_document import KnowledgeDocument
from src.modules.knowledge.ingestion.chunkers import chunk_markdown_document


@dataclass(frozen=True)
class ProjectIngestRequest:
    project_id: int
    created_by_user_id: int
    source_key: str
    source_url: str
    source_repo: str
    source_path: str
    document_category: DocumentCategory | None
    raw_content: str
    source_ref: str
    title: str
    language: str = "en"
    decision_number: str | None = None
    content_status: str | None = None
    category_confirmed: bool = False
    category_classification_status: str | None = None
    category_review_reason: str | None = None
    classifier_version: str | None = None


async def _materialize_document(
    session: AsyncSession,
    document: KnowledgeDocument | None,
    request: ProjectIngestRequest,
) -> KnowledgeDocument:
    """Create/update metadata only after any required external embedding work has finished."""
    if document is None:
        document = KnowledgeDocument(
            project_id=request.project_id,
            created_by_user_id=request.created_by_user_id,
            knowledge_domain=DocumentDomain.PROJECT,
            source_key=request.source_key,
        )
        session.add(document)
    document.document_category = request.document_category
    document.category_confirmed = request.category_confirmed
    document.category_classification_status = request.category_classification_status
    document.category_review_reason = request.category_review_reason
    document.document_category_classifier_version = request.classifier_version
    document.source_repo = request.source_repo
    document.language = request.language
    document.decision_number = request.decision_number
    document.title = request.title
    document.source_url = request.source_url
    document.status = DocumentStatus.ACTIVE
    await session.flush()
    return document


async def ingest_or_update(
    session: AsyncSession,
    request: ProjectIngestRequest,
    embedder: Embedder,
    *,
    force_rechunk: bool = False,
    release_before_external: bool = False,
) -> KnowledgeDocument:
    """Persist one GitHub file, retaining history and reusing embedding cache."""
    if not request.source_ref:
        raise ValueError("PROJECT ingestion requires a pinned source_ref")
    # The scan belongs to the core, not to its callers: GitHub sync, PM upload and
    # repo-scan import all reach persistence through here, so this is the only place
    # that can guarantee no unscanned text is ever chunked, embedded or stored.
    # Redaction is idempotent, so a caller that already scanned (github_sync_worker
    # needs the redacted text for title and classification) costs a second pass and
    # nothing else.
    redaction = scan(request.raw_content)
    content = redaction.redacted_content
    if not content.strip():
        raise ValueError("Project source content must not be empty after redaction")
    record_secret_findings(
        redaction, boundary="ingest.project", document_reference=request.source_key
    )


    # Scoped by project_id, not just (domain, source_key): two projects can point at the same
    # GitHub repo/path, and source_key alone (github:{repo}:{path}) does not distinguish them —
    # see uq_knowledge_documents_project_source_key. Looking this up without project_id would
    # find and silently mutate a different project's document instead of creating this one's.
    document = await session.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.knowledge_domain == DocumentDomain.PROJECT,
            KnowledgeDocument.project_id == request.project_id,
            KnowledgeDocument.source_key == request.source_key,
        )
    )
    if request.document_category is None:
        # Preserve the document as a reviewable staging record, but never make
        # an unclassified source retrievable or embed it under a guessed type.
        # A staged row intentionally has zero DocumentVersions.  PostgreSQL's
        # partial unique index still guarantees at most one ACTIVE version once
        # a later, PM-confirmed sync reaches the normal ingestion path.
        return await _materialize_document(session, document, request)

    checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
    active = (
        await session.scalar(
            select(DocumentVersion).where(
                DocumentVersion.document_id == document.document_id,
                DocumentVersion.status == VersionStatus.ACTIVE,
            )
        )
        if document is not None
        else None
    )
    if active is not None and active.checksum == checksum and (
        not force_rechunk or ":structural-r" in active.version_no
    ):
        # Unchanged source text at a newer repository snapshot remains the same
        # logical version; update its verified permalink commit only.
        active.source_ref = request.source_ref
        active.storage_uri = request.source_url
        active.content_status = request.content_status
        return await _materialize_document(session, document, request)

    chunks = chunk_markdown_document(
        content, title=request.title, document_category=request.document_category
    )
    if not chunks:
        raise ValueError(f"Chunker produced no chunks for {request.source_key}")
    embedding_texts = [_embedding_text(request, chunk.content, chunk.section_path) for chunk in chunks]
    vectors: list[list[float] | None] = []
    missing_indexes: list[int] = []
    for index, text in enumerate(embedding_texts):
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        cached = await session.scalar(
            select(DocumentChunk.embedding).where(
                DocumentChunk.content_hash == digest,
                DocumentChunk.embedding_model_version == embedder.model_version,
                DocumentChunk.embedding.is_not(None),
            ).limit(1)
        )
        vectors.append(cached)
        if cached is None:
            missing_indexes.append(index)
    # Cache reads are complete and no writes have been made. Release the connection before
    # waiting on the embedding provider, then re-read mutable document/version state below.
    if release_before_external:
        await session.commit()
    for start in range(0, len(missing_indexes), 32):
        batch_indexes = missing_indexes[start : start + 32]
        produced = await embedder.embed([embedding_texts[index] for index in batch_indexes])
        if len(produced) != len(batch_indexes):
            raise ValueError("Embedder returned a vector count different from requested chunks")
        for index, vector in zip(batch_indexes, produced, strict=True):
            vectors[index] = vector

    document = await session.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.knowledge_domain == DocumentDomain.PROJECT,
            KnowledgeDocument.project_id == request.project_id,
            KnowledgeDocument.source_key == request.source_key,
        )
    )
    active = (
        await session.scalar(
            select(DocumentVersion).where(
                DocumentVersion.document_id == document.document_id,
                DocumentVersion.status == VersionStatus.ACTIVE,
            )
        )
        if document is not None
        else None
    )
    if active is not None and active.checksum == checksum and (
        not force_rechunk or ":structural-r" in active.version_no
    ):
        active.source_ref = request.source_ref
        active.storage_uri = request.source_url
        active.content_status = request.content_status
        return await _materialize_document(session, document, request)
    document = await _materialize_document(session, document, request)

    revision_no = int(
        await session.scalar(
            select(func.coalesce(func.max(DocumentVersion.revision_no), 0)).where(
                DocumentVersion.document_id == document.document_id
            )
        )
    ) + 1
    if active is not None:
        active.status = VersionStatus.ARCHIVED
        await session.flush()
    version = DocumentVersion(
        document_id=document.document_id,
        version_no=(
            f"{request.source_ref}:structural-r{revision_no}" if force_rechunk else request.source_ref
        ),
        embedding_model_version=embedder.model_version,
        revision_no=revision_no,
        storage_uri=request.source_url,
        checksum=checksum,
        source_ref=request.source_ref,
        content_status=request.content_status,
        status=VersionStatus.ACTIVE,
    )
    session.add(version)
    await session.flush()
    for index, (chunk, embedding_text, vector) in enumerate(zip(chunks, embedding_texts, vectors, strict=True)):
        if vector is None:
            raise AssertionError("Embedding cache resolution left a missing vector")
        session.add(
            DocumentChunk(
                version_id=version.version_id,
                heading=chunk.section_path,
                content=chunk.content,
                embedding_text=embedding_text,
                lexical_identifiers=lexical_identifiers(embedding_text),
                lexical_technical=embedding_text,
                section_path=chunk.section_path,
                anchor=chunk.anchor,
                content_hash=hashlib.sha256(embedding_text.encode("utf-8")).hexdigest(),
                embedding_model_version=embedder.model_version,
                chunk_index=index,
                token_count=chunk.token_count,
                embedding=vector,
            )
        )
    return document


async def reembed_active_chunks(session: AsyncSession, embedder: Embedder, *, batch_size: int = 32) -> int:
    """One-time repair for ACTIVE chunks outside the configured embedding model."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    rows = (
        await session.execute(
            select(DocumentChunk, DocumentVersion)
            .join(DocumentVersion, DocumentVersion.version_id == DocumentChunk.version_id)
            .where(
                DocumentVersion.status == VersionStatus.ACTIVE,
                (DocumentChunk.embedding_model_version != embedder.model_version)
                | (DocumentVersion.embedding_model_version != embedder.model_version),
            )
            .order_by(DocumentChunk.chunk_id)
        )
    ).all()
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        vectors = await embedder.embed([chunk.embedding_text for chunk, _version in batch])
        if len(vectors) != len(batch):
            raise ValueError("Embedder returned a vector count different from requested chunks")
        for (chunk, version), vector in zip(batch, vectors, strict=True):
            chunk.embedding = vector
            chunk.embedding_model_version = embedder.model_version
            version.embedding_model_version = embedder.model_version
    return len(rows)


def _embedding_text(request: ProjectIngestRequest, content: str, section_path: str) -> str:
    """Build neutral retrieval context without a document-type dispatch."""
    breadcrumb = f"{request.title} > {section_path}" if section_path else request.title
    metadata = [breadcrumb]
    if request.decision_number:
        metadata.append(f"Decision {request.decision_number}")
    if request.content_status:
        metadata.append(f"Status {request.content_status}")
    return f"{' | '.join(metadata)}\n\n{content}"
