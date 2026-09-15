"""Test document_version_service.activate_version() — hàm INV2-safe, giờ được gọi ngay trong
`knowledge_document_service._import_one()` sau khi tạo version (xem
docs/PM/Phase-4/plan-fix-onboarding-plan-quality.md mục 0/3.1). Test gọi thẳng service (không qua
API) để kiểm tra đúng phần lõi archive-cũ/activate-mới, không phụ thuộc luồng upload.

`VersionStatus` giờ chỉ còn ACTIVE/ARCHIVED (PROCESSING/FAILED đã bị bỏ ở migration
`0c1d2e3f4a5b_document_version_active_archived_lifecycle.py` — mọi version phải ACTIVE ngay khi
tạo) nên các version "chưa active" trong test dựng sẵn ở trạng thái ARCHIVED, không phải PROCESSING
như bản cũ."""

import uuid

import pytest
from sqlalchemy import func, select

from src.model.document_version import DocumentVersion
from src.model.enums import DocumentDomain, DocumentStatus, VersionStatus
from src.model.knowledge_document import KnowledgeDocument
from src.model.session import AsyncSessionLocal
from src.services import document_version_service
from src.services.document_version_service import PENDING_EMBEDDING_MODEL_VERSION


def _unique_title() -> str:
    return f"activation-test-{uuid.uuid4().hex[:8]}.md"


def _unique_source_key() -> str:
    # Nhánh POLICY của CHECK constraint knowledge_domain_category (từ develop) giờ bắt buộc
    # source_key IS NOT NULL — test tạo KnowledgeDocument giả lập POLICY cần set field này.
    return f"activation-test-{uuid.uuid4().hex[:8]}"


@pytest.mark.asyncio
async def test_activate_version_archives_previous_active_inv2():
    async with AsyncSessionLocal() as db:
        document = KnowledgeDocument(
            project_id=None,
            created_by_user_id=19,
            knowledge_domain=DocumentDomain.POLICY,
            document_category=None,
            policy_category="GENERAL",
            source_key=_unique_source_key(),
            title=_unique_title(),
            source_url="https://example.test/doc.md",
            status=DocumentStatus.ACTIVE,
        )
        db.add(document)
        await db.flush()
        document_id = document.document_id

        # Trigger DB giờ đòi "đúng 1 ACTIVE tại mọi thời điểm commit" (không chỉ "tối đa 1" như
        # INV2 gốc) — version_a phải ACTIVE ngay từ lúc tạo, khớp thực tế luôn có đúng 1 bản đang
        # dùng; version_b là bản mới CHƯA kích hoạt nên ARCHIVED.
        version_a = DocumentVersion(
            document_id=document_id, revision_no=1, version_no="1",
            embedding_model_version=PENDING_EMBEDDING_MODEL_VERSION,
            storage_uri="https://example.test/v1.md",
            checksum="checksum-a", status=VersionStatus.ACTIVE,
        )
        version_b = DocumentVersion(
            document_id=document_id, revision_no=2, version_no="2",
            embedding_model_version=PENDING_EMBEDDING_MODEL_VERSION,
            storage_uri="https://example.test/v2.md",
            checksum="checksum-b", status=VersionStatus.ARCHIVED,
        )
        db.add_all([version_a, version_b])
        await db.commit()
        await db.refresh(version_a)
        await db.refresh(version_b)

        try:
            active_count = await db.scalar(
                select(func.count()).select_from(DocumentVersion).where(
                    DocumentVersion.document_id == document_id, DocumentVersion.status == VersionStatus.ACTIVE
                )
            )
            assert active_count == 1

            # Kích hoạt version B — version A phải tự ARCHIVED, không có 2 ACTIVE cùng lúc (đây
            # chính là INV2, đã được ép cả ở DB bằng deferred constraint trigger).
            await document_version_service.activate_version(db, document_id, version_b.version_id)
            await db.commit()

            await db.refresh(version_a)
            await db.refresh(version_b)
            assert version_a.status == VersionStatus.ARCHIVED
            assert version_b.status == VersionStatus.ACTIVE

            active_count_after = await db.scalar(
                select(func.count()).select_from(DocumentVersion).where(
                    DocumentVersion.document_id == document_id, DocumentVersion.status == VersionStatus.ACTIVE
                )
            )
            assert active_count_after == 1
        finally:
            await db.execute(
                DocumentVersion.__table__.delete().where(DocumentVersion.document_id == document_id)
            )
            await db.execute(
                KnowledgeDocument.__table__.delete().where(KnowledgeDocument.document_id == document_id)
            )
            await db.commit()


@pytest.mark.asyncio
async def test_activate_version_rejects_version_from_other_document():
    async with AsyncSessionLocal() as db:
        doc_1 = KnowledgeDocument(
            project_id=None, created_by_user_id=19, knowledge_domain=DocumentDomain.POLICY,
            document_category=None, policy_category="GENERAL", source_key=_unique_source_key(),
            title=_unique_title(), source_url="https://example.test/1.md", status=DocumentStatus.ACTIVE,
        )
        doc_2 = KnowledgeDocument(
            project_id=None, created_by_user_id=19, knowledge_domain=DocumentDomain.POLICY,
            document_category=None, policy_category="GENERAL", source_key=_unique_source_key(),
            title=_unique_title(), source_url="https://example.test/2.md", status=DocumentStatus.ACTIVE,
        )
        db.add_all([doc_1, doc_2])
        await db.flush()

        # Trigger DB đòi MỌI document phải có đúng 1 ACTIVE tại thời điểm commit — doc_1 cũng cần
        # 1 version ACTIVE riêng dù test không dùng tới nó, chỉ để commit không bị chặn.
        doc_1_version = DocumentVersion(
            document_id=doc_1.document_id, revision_no=1, version_no="1",
            embedding_model_version=PENDING_EMBEDDING_MODEL_VERSION,
            storage_uri="https://example.test/1-v1.md",
            checksum="checksum-doc1", status=VersionStatus.ACTIVE,
        )
        version = DocumentVersion(
            document_id=doc_2.document_id, revision_no=1, version_no="1",
            embedding_model_version=PENDING_EMBEDDING_MODEL_VERSION,
            storage_uri="https://example.test/v1.md",
            # ACTIVE ngay từ đầu — doc_2 phải có đúng 1 ACTIVE tại thời điểm commit (trigger DB).
            checksum="checksum-x", status=VersionStatus.ACTIVE,
        )
        db.add_all([doc_1_version, version])
        await db.commit()
        await db.refresh(version)

        doc_1_id = doc_1.document_id
        doc_2_id = doc_2.document_id
        version_id = version.version_id

        try:
            with pytest.raises(ValueError):
                await document_version_service.activate_version(db, doc_1_id, version_id)
        finally:
            # await db.rollback() ở đây sẽ expire doc_1/doc_2, khiến truy cập .document_id sau đó
            # kích hoạt lazy-load đồng bộ (lỗi MissingGreenlet với async session) — dùng id đã cache
            # ở trên thay vì đọc lại thuộc tính object sau rollback.
            await db.rollback()
            await db.execute(
                DocumentVersion.__table__.delete().where(DocumentVersion.document_id.in_([doc_1_id, doc_2_id]))
            )
            await db.execute(
                KnowledgeDocument.__table__.delete().where(KnowledgeDocument.document_id.in_([doc_1_id, doc_2_id]))
            )
            await db.commit()
