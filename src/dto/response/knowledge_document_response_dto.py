from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from src.dto.response.document_version_response_dto import DocumentVersionResponseDTO
from src.model.document_version import DocumentVersion
from src.model.enums import DocumentCategory, DocumentStatus, PolicyCategory
from src.model.knowledge_document import KnowledgeDocument


class KnowledgeDocumentResponseDTO(BaseModel):
    document_id: int
    title: str
    source_url: str
    policy_category: PolicyCategory
    status: DocumentStatus
    created_at: datetime

    @classmethod
    def from_entity(cls, document: KnowledgeDocument) -> KnowledgeDocumentResponseDTO:
        return cls(
            document_id=document.document_id,
            title=document.title,
            source_url=document.source_url,
            policy_category=document.policy_category,
            status=document.status,
            created_at=document.created_at,
        )


class ProjectDocumentResponseDTO(BaseModel):
    document_id: int
    project_id: int
    document_category: DocumentCategory | None
    category_confirmed: bool
    category_classification_status: str | None
    title: str
    status: DocumentStatus
    latest_version: DocumentVersionResponseDTO | None
    created_at: datetime

    @classmethod
    def from_entity(
        cls, document: KnowledgeDocument, latest_version: DocumentVersion | None
    ) -> ProjectDocumentResponseDTO:
        return cls(
            document_id=document.document_id,
            project_id=document.project_id,  # type: ignore[arg-type]
            document_category=document.document_category,
            category_confirmed=document.category_confirmed,
            category_classification_status=document.category_classification_status,
            title=document.title,
            status=document.status,
            latest_version=DocumentVersionResponseDTO.from_entity(latest_version) if latest_version else None,
            created_at=document.created_at,
        )


class ProjectDocumentContentResponseDTO(BaseModel):
    """Nội dung tài liệu dự án đã chuẩn hoá về markdown, để đọc ngay trong Ralion.

    Backend chịu trách nhiệm biến MỌI định dạng nguồn (`.md/.txt/.docx/.pdf`, GitHub hay PM tải
    tay) thành một dạng duy nhất; frontend chỉ việc render markdown, không cần biết định dạng gốc
    và không phải tự parse file nhị phân trong trình duyệt.

    `source_url` vẫn trả về để giữ đúng ngữ nghĩa cũ (link tới bản gốc trên GitHub/Cloudinary) —
    nó là lối thoát phụ, không còn là cách đọc chính.
    """

    document_id: int
    title: str
    source_url: str
    version_no: str
    revision_no: int
    content: str

    @classmethod
    def from_entity(
        cls, document: KnowledgeDocument, version: DocumentVersion, content: str
    ) -> ProjectDocumentContentResponseDTO:
        return cls(
            document_id=document.document_id,
            title=document.title,
            source_url=document.source_url,
            version_no=version.version_no,
            revision_no=version.revision_no,
            content=content,
        )
