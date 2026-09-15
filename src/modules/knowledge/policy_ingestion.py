"""Synchronous UI ingestion for company policy documents."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.providers.embeddings import Embedder
from src.ai.retrieval_engine.chunking_config import embedding_params, load_chunking_config
from src.ai.retrieval_engine.lexical import lexical_identifiers
from src.ai.retrieval_engine.policy_chunker import chunk_policy_markdown, embedding_text_for_policy_chunk
from src.core.security.secret_scan import record_secret_findings, scan
from src.model.document_chunk import DocumentChunk
from src.model.document_version import DocumentVersion
from src.model.enums import DocumentDomain, DocumentStatus, PolicyCategory, VersionStatus
from src.model.knowledge_document import KnowledgeDocument
from src.modules.knowledge.policy_metadata import normalize_policy_source_key, parse_policy_version_metadata


@dataclass(frozen=True)
class PolicyIngestRequest:
    title: str
    content: str
    document_code: str
    policy_category: PolicyCategory
    created_by_user_id: int
    source_url: str
    purpose_sentence: str = ""


def parse_policy_header(markdown: str) -> dict[str, str]:
    """Extract the simple metadata bullets used by the seed policy corpus."""
    result: dict[str, str] = {}
    for line in markdown.splitlines():
        match = re.match(r"^[-*]\s+\*\*(.+?):\*\*\s*(.+?)\s*$", line)
        if match:
            result[match.group(1).strip().casefold()] = match.group(2).strip()
    return result


async def ingest_policy_document(
    session: AsyncSession,
    request: PolicyIngestRequest,
    embedder: Embedder,
    *,
    config: dict | None = None,
) -> KnowledgeDocument:
    """Create or version a policy document and atomically activate its new chunks.

    Embeddings are computed before mutating the database. The database transaction then
    creates the new version, stores chunks, archives the previous active version, and
    activates the new version. Historical versions remain available for citations.
    """
    if not request.content.strip():
        raise ValueError("Policy content must not be empty")
    if not request.document_code.strip():
        raise ValueError("document_code must not be empty")

    # F-20: the §6.3 control belongs to the ingest core, before chunk/embed/persist,
    # exactly as the PROJECT core does it. An HR-uploaded document is no less likely
    # to carry a shared credential than a repository file.
    redaction = scan(request.content)
    content = redaction.redacted_content
    if not content.strip():
        raise ValueError("Policy content must not be empty")
    record_secret_findings(
        redaction, boundary="ingest.policy", document_reference=request.document_code
    )

    config = config or load_chunking_config()
    header = parse_policy_header(content)
    source_key = normalize_policy_source_key(request.document_code)
    source_version, effective_date = parse_policy_version_metadata(content)
    # Checksum covers the text that is actually stored and embedded, so an identical
    # re-upload still resolves to the same version. Redaction is deterministic, which
    # is what makes that equivalence hold.
    checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtext(f"POLICY:{source_key}"))))
    document = await session.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.knowledge_domain == DocumentDomain.POLICY,
            KnowledgeDocument.source_key == source_key,
        )
    )
    if document is None:
        document = KnowledgeDocument(
            created_by_user_id=request.created_by_user_id,
            knowledge_domain=DocumentDomain.POLICY,
            policy_category=request.policy_category,
            source_key=source_key,
            title=request.title,
            source_url=request.source_url,
            status=DocumentStatus.ACTIVE,
        )
        session.add(document)
        await session.flush()
    else:
        if document.policy_category != request.policy_category:
            document.policy_category = request.policy_category
        document.title = request.title
        document.source_url = request.source_url

    existing_source_version = await session.scalar(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document.document_id,
            DocumentVersion.version_no == source_version,
            DocumentVersion.embedding_model_version == embedder.model_version,
        )
    )
    if existing_source_version is not None and existing_source_version.checksum != checksum:
        raise ValueError(f"Source version {source_version!r} already exists with a different checksum")
    if existing_source_version is not None:
        return document

    current = await session.scalar(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document.document_id,
            DocumentVersion.status == VersionStatus.ACTIVE,
        )
    )

    revision_no = int(
        await session.scalar(
            select(func.coalesce(func.max(DocumentVersion.revision_no), 0)).where(
                DocumentVersion.document_id == document.document_id
            )
        )
    ) + 1
    chunks = chunk_policy_markdown(
        content,
        document_code=request.document_code,
        purpose_sentence=request.purpose_sentence or header.get("mục đích", ""),
        config=config,
    )
    embedding_prefix = embedding_params(config)
    if not embedding_prefix.get("normalize_embeddings", True):
        raise ValueError("BGE-M3 embeddings must be normalized for cosine retrieval")
    embedding_texts = [
        embedding_text_for_policy_chunk(
            chunk, document_code=request.document_code, purpose_sentence=request.purpose_sentence
        )
        for chunk in chunks
    ]
    vectors = await embedder.embed(embedding_texts)
    if len(vectors) != len(chunks):
        raise ValueError("Embedder returned a vector count different from chunk count")

    # Archive only after all compute has succeeded. The surrounding transaction
    # rolls this change back if inserting the new version or its chunks fails.
    if current is not None:
        current.status = VersionStatus.ARCHIVED
        await session.flush()

    version = DocumentVersion(
        document_id=document.document_id,
        version_no=source_version,
        embedding_model_version=embedder.model_version,
        revision_no=revision_no,
        storage_uri=request.source_url,
        checksum=checksum,
        effective_date=effective_date,
        status=VersionStatus.ACTIVE,
    )
    session.add(version)
    await session.flush()
    for index, (chunk, embedding_text, vector) in enumerate(zip(chunks, embedding_texts, vectors, strict=True)):
        session.add(
            DocumentChunk(
                version_id=version.version_id,
                heading=chunk.heading_path,
                content=chunk.content,
                embedding_text=embedding_text,
                lexical_identifiers=lexical_identifiers(embedding_text),
                lexical_technical=embedding_text,
                section_path=chunk.heading_path,
                content_hash=hashlib.sha256(embedding_text.encode("utf-8")).hexdigest(),
                embedding_model_version=embedder.model_version,
                chunk_index=index,
                token_count=chunk.token_count,
                embedding=vector,
            )
        )
    await session.commit()
    await session.refresh(document)
    return document
