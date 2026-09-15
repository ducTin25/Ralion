"""Idempotent persistence job for the precomputed BGE-M3 policy artifact."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.providers.embeddings import EMBEDDING_DIMENSION, EMBEDDING_MODEL_VERSION
from src.ai.retrieval_engine.lexical import lexical_identifiers
from src.core.security.secret_scan import scan
from src.model.document_chunk import DocumentChunk
from src.model.document_version import DocumentVersion
from src.model.enums import DocumentDomain, DocumentStatus, PolicyCategory, VersionStatus
from src.model.knowledge_document import KnowledgeDocument
from src.model.user import User
from src.modules.knowledge.policy_metadata import normalize_policy_source_key, parse_policy_version_metadata

EXPECTED_MODEL = EMBEDDING_MODEL_VERSION
EXPECTED_DIMENSION = EMBEDDING_DIMENSION


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_number}") from exc
            rows.append(row)
    return rows


def validate_row(row: dict[str, Any], category: str) -> None:
    if category not in {item.value for item in PolicyCategory}:
        raise ValueError(f"Invalid policy_category {category!r}")
    if row.get("checksum") is None or not row.get("source_file"):
        raise ValueError("Each artifact row requires source_file and checksum")
    if not row.get("chunks"):
        raise ValueError(f"No chunks for {row.get('source_file')}")
    for chunk in row["chunks"]:
        vector = chunk.get("embedding")
        if not isinstance(vector, list) or len(vector) != EXPECTED_DIMENSION:
            raise ValueError(f"Embedding dimension must be {EXPECTED_DIMENSION}")
        if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in vector):
            raise ValueError("Embedding must contain only finite numeric values")
        norm = math.sqrt(sum(value * value for value in vector))
        if not math.isclose(norm, 1.0, rel_tol=0.0, abs_tol=1e-3):
            raise ValueError(f"Embedding must be normalized; got norm {norm:.6f}")
        if not chunk.get("embedding_text") or not chunk.get("content"):
            raise ValueError("Each chunk requires content and embedding_text")
        if not isinstance(chunk.get("token_count"), int) or chunk["token_count"] < 0:
            raise ValueError("Each chunk requires a non-negative integer token_count")
        # Reject rather than redact. The vector was computed offline from this exact
        # text; rewriting the text here would leave content and embedding describing
        # different things. Redaction for this path belongs upstream, in the script
        # that produces the artifact.
        for field in ("content", "embedding_text"):
            if scan(chunk[field]).has_findings:
                raise ValueError(
                    f"Secret detected in {field} of chunk {chunk.get('chunk_index')} "
                    f"({row.get('source_file')}); re-generate the artifact with redaction applied"
                )
    indices = [chunk.get("chunk_index") for chunk in row["chunks"]]
    if indices != list(range(len(indices))):
        raise ValueError("chunk_index values must be contiguous and zero-based")


def resolve_source(source_file: str, source_root: Path) -> Path:
    candidate = Path(source_file)
    if candidate.is_file():
        return candidate
    candidate = source_root / Path(source_file).name
    if not candidate.is_file():
        raise FileNotFoundError(f"Cannot find policy source for {source_file!r} under {source_root}")
    return candidate


async def import_policy_embeddings(
    db: AsyncSession,
    *,
    embedding_path: Path,
    labels_path: Path,
    source_root: Path,
    source_uri_for: Callable[[Path, str, str], str],
    hr_email: str = "hr@onboarding.dev",
) -> tuple[int, int]:
    """Import rows and return (documents_created_or_updated, chunks_written).

    Source uploads are outside PostgreSQL's transaction, so the caller must
    make them idempotent from ``source_key`` and ``checksum``. Each database
    document is committed independently, allowing safe resume after a failure.
    """
    labels_data = json.loads(labels_path.read_text(encoding="utf-8"))
    labels: dict[str, str] = {}
    for item in labels_data.get("labels", []):
        filename = Path(item["file"]).name
        category = item["policy_category"]
        confidence = item.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 100:
            raise ValueError(f"Invalid confidence for {filename}: {confidence!r}")
        if category not in {value.value for value in PolicyCategory}:
            raise ValueError(f"Invalid policy_category {category!r} for {filename}")
        if filename in labels and labels[filename] != category:
            raise ValueError(f"Conflicting labels for {filename}")
        labels[filename] = category

    hr_user = await db.scalar(select(User).where(User.email == hr_email, User.system_role == "HR"))
    if hr_user is None:
        raise ValueError(f"Missing HR seed user {hr_email!r}; run scripts/seed_dev_data.py first")

    rows = load_jsonl(embedding_path)
    artifact_files = {Path(row.get("source_file", "")).name for row in rows}
    if set(labels) != artifact_files:
        missing = sorted(artifact_files - set(labels))
        extra = sorted(set(labels) - artifact_files)
        raise ValueError(f"Labels must exactly match artifact files; missing={missing}, extra={extra}")

    prepared: list[tuple[dict[str, Any], str, Path, str, str, date]] = []
    seen_source_keys: set[str] = set()
    for row in rows:
        filename = Path(row["source_file"]).name
        category = labels.get(filename)
        if category is None:
            raise ValueError(f"No policy_category label for {filename}")
        document_code = row.get("document_code")
        if not isinstance(document_code, str):
            raise ValueError(f"Artifact row for {filename} requires document_code")
        source_key = normalize_policy_source_key(document_code)
        if source_key in seen_source_keys:
            raise ValueError(f"Duplicate policy document_code/source_key {source_key!r}")
        seen_source_keys.add(source_key)
        validate_row(row, category)
        source_path = resolve_source(row["source_file"], source_root)
        source_content = source_path.read_text(encoding="utf-8")
        source_checksum = hashlib.sha256(source_content.encode("utf-8")).hexdigest()
        if source_checksum != row["checksum"]:
            raise ValueError(f"Checksum mismatch for {filename}: artifact={row['checksum']} source={source_checksum}")
        version_label, effective_date = parse_policy_version_metadata(source_content)
        prepared.append((row, category, source_path, source_key, version_label, effective_date))

    created_documents = 0
    written_chunks = 0
    for row, category, source_path, source_key, version_label, effective_date in prepared:
        try:
            await db.execute(select(func.pg_advisory_xact_lock(func.hashtext(f"POLICY:{source_key}"))))
            document = await db.scalar(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.knowledge_domain == DocumentDomain.POLICY,
                    KnowledgeDocument.source_key == source_key,
                )
            )
            source_uri: str | None = None
            if document is None:
                # Upgrade legacy imports that predate source_key without
                # duplicating their document/version/chunks on the first retry.
                # This title/checksum lookup is only a legacy migration bridge;
                # all subsequent identity is source_key based.
                document = await db.scalar(
                    select(KnowledgeDocument)
                    .join(DocumentVersion)
                    .where(
                        KnowledgeDocument.knowledge_domain == DocumentDomain.POLICY,
                        KnowledgeDocument.source_key.like("legacy-policy-%"),
                        KnowledgeDocument.title == (row.get("title") or source_path.stem),
                        DocumentVersion.checksum == row["checksum"],
                    )
                    .order_by(DocumentVersion.version_id.desc())
                )
                if document is None:
                    source_uri = source_uri_for(source_path, source_key, row["checksum"])
                    document = await db.scalar(
                        select(KnowledgeDocument).where(
                            KnowledgeDocument.knowledge_domain == DocumentDomain.POLICY,
                            KnowledgeDocument.source_url == source_uri,
                            KnowledgeDocument.source_key.like("legacy-policy-%"),
                        )
                    )
                if document is not None:
                    document.source_key = source_key
            if document is not None:
                existing_source_version = await db.scalar(
                    select(DocumentVersion).where(
                        DocumentVersion.document_id == document.document_id,
                        DocumentVersion.version_no == version_label,
                        DocumentVersion.embedding_model_version == EXPECTED_MODEL,
                    )
                )
                if existing_source_version is not None:
                    if existing_source_version.checksum != row["checksum"]:
                        raise ValueError(
                            f"Source version {version_label!r} for {source_key!r} already exists with a different checksum"
                        )
                    await db.commit()
                    continue

            if source_uri is None:
                source_uri = source_uri_for(source_path, source_key, row["checksum"])
            if document is None:
                document = KnowledgeDocument(
                    project_id=None,
                    created_by_user_id=hr_user.user_id,
                    knowledge_domain=DocumentDomain.POLICY,
                    policy_category=PolicyCategory(category),
                    source_key=source_key,
                    title=row.get("title") or source_path.stem,
                    source_url=source_uri,
                    status=DocumentStatus.ACTIVE,
                )
                db.add(document)
                await db.flush()
                created_documents += 1
            else:
                if document.policy_category != PolicyCategory(category):
                    document.policy_category = PolicyCategory(category)
                document.title = row.get("title") or source_path.stem
                document.source_url = source_uri

            active = await db.scalar(
                select(DocumentVersion).where(
                    DocumentVersion.document_id == document.document_id,
                    DocumentVersion.status == VersionStatus.ACTIVE,
                )
            )
            revision_no = (
                int(
                    await db.scalar(
                        select(func.coalesce(func.max(DocumentVersion.revision_no), 0)).where(
                            DocumentVersion.document_id == document.document_id
                        )
                    )
                )
                + 1
            )

            # The artifact has already been fully validated. Archive the current
            # version in this write transaction before inserting the replacement
            # ACTIVE row, avoiding a partial-unique-index conflict.
            if active is not None:
                active.status = VersionStatus.ARCHIVED
                await db.flush()

            version = DocumentVersion(
                document_id=document.document_id,
                version_no=version_label,
                embedding_model_version=EXPECTED_MODEL,
                revision_no=revision_no,
                storage_uri=source_uri,
                checksum=row["checksum"],
                effective_date=effective_date,
                status=VersionStatus.ACTIVE,
            )
            db.add(version)
            await db.flush()
            for chunk in row["chunks"]:
                content_hash = hashlib.sha256(chunk["embedding_text"].encode("utf-8")).hexdigest()
                db.add(
                    DocumentChunk(
                        version_id=version.version_id,
                        heading=chunk.get("heading"),
                        content=chunk["content"],
                        chunk_index=chunk["chunk_index"],
                        token_count=chunk["token_count"],
                        embedding_text=chunk["embedding_text"],
                        lexical_identifiers=lexical_identifiers(chunk["embedding_text"]),
                        lexical_technical=chunk["embedding_text"],
                        section_path=chunk.get("heading"),
                        content_hash=content_hash,
                        embedding_model_version=EXPECTED_MODEL,
                        embedding=chunk["embedding"],
                    )
                )
                written_chunks += 1
            await db.flush()
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return created_documents, written_chunks
