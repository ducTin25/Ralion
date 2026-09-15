"""Helpers for document-version persistence.

Document versions have only two persisted states: ACTIVE and ARCHIVED. The
upload/ingestion owner must call these helpers only in the short write
transaction that also persists the replacement chunks.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.model.document_version import DocumentVersion
from src.model.enums import VersionStatus

PENDING_EMBEDDING_MODEL_VERSION = "pending"


async def next_revision_no(db: AsyncSession, document_id: int) -> int:
    last = await db.scalar(
        select(func.max(DocumentVersion.revision_no)).where(DocumentVersion.document_id == document_id)
    )
    return (last or 0) + 1


async def create_active_version(
    db: AsyncSession, document_id: int, storage_uri: str, checksum: str, revision_no: int
) -> DocumentVersion:
    version = DocumentVersion(
        document_id=document_id,
        revision_no=revision_no,
        version_no=str(revision_no),
        embedding_model_version=PENDING_EMBEDDING_MODEL_VERSION,
        storage_uri=storage_uri,
        checksum=checksum,
        status=VersionStatus.ACTIVE,
    )
    db.add(version)
    await db.flush()
    return version


async def activate_version(db: AsyncSession, document_id: int, version_id: int) -> DocumentVersion:
    """Archive the current version, then activate the specified replacement."""
    target = await db.get(DocumentVersion, version_id)
    if target is None or target.document_id != document_id:
        raise ValueError("Version không hợp lệ hoặc không thuộc document này")

    currently_active = await db.scalar(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.status == VersionStatus.ACTIVE,
        )
    )
    if currently_active is not None and currently_active.version_id != target.version_id:
        currently_active.status = VersionStatus.ARCHIVED
        await db.flush()

    target.status = VersionStatus.ACTIVE
    await db.flush()
    await db.refresh(target)
    return target
