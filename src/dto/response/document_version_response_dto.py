from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from src.model.document_version import DocumentVersion
from src.model.enums import VersionStatus


class DocumentVersionResponseDTO(BaseModel):
    version_id: int
    document_id: int
    version_no: str
    revision_no: int
    storage_uri: str
    checksum: str
    status: VersionStatus
    created_at: datetime

    @classmethod
    def from_entity(cls, version: DocumentVersion) -> DocumentVersionResponseDTO:
        return cls(
            version_id=version.version_id,
            document_id=version.document_id,
            version_no=version.version_no,
            revision_no=version.revision_no,
            storage_uri=version.storage_uri,
            checksum=version.checksum,
            status=version.status,
            created_at=version.created_at,
        )
