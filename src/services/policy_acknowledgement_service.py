"""Xác nhận đã đọc chính sách — nghiệp vụ tuân thủ của miền HR.

Vấn đề tính năng này giải quyết: HR Policy Library hiện là kho chỉ-ghi. HR tải tài liệu
lên, TV3 chunk + embed, và kể từ đó cách duy nhất một kỹ sư gặp được nội dung là tình cờ
hỏi AI đúng câu hỏi. Không hỏi thì không bao giờ thấy — mà ngày đầu đi làm thì người ta
chưa biết có thứ gì để hỏi.

Ba quy tắc nghiệp vụ được ghi tường minh ở đây, không để ngầm định:

1. Người phải xác nhận = user ACTIVE có `system_role IS NULL` (kỹ sư). ADMIN/HR là người
   quản lý chính sách, không phải đối tượng áp dụng. Muốn đổi thì sửa `_eligible_users()`
   — một chỗ duy nhất.
2. Chỉ xác nhận được version ACTIVE. Version đang PROCESSING (TV3 chưa embed xong) thì
   trả 409, vì nội dung có thể còn thay đổi.
3. Xác nhận là bất biến. Không có hàm xoá, và sẽ không thêm.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.model.document_version import DocumentVersion
from src.model.enums import DocumentDomain, DocumentStatus, UserStatus, VersionStatus
from src.model.knowledge_document import KnowledgeDocument
from src.model.policy_acknowledgement import PolicyAcknowledgement
from src.model.user import User


@dataclass(frozen=True)
class AckUser:
    user_id: int
    display_name: str
    email: str
    acknowledged_at: object | None = None


async def _eligible_user_ids(db: AsyncSession) -> list[int]:
    """Những ai được tính vào mẫu số của tỷ lệ xác nhận.

    Loại ADMIN/HR vì họ là người ban hành chính sách, và loại tài khoản INACTIVE vì
    người đã nghỉ không nên kéo tỷ lệ xuống mãi mãi — nếu tính họ thì tỷ lệ không bao
    giờ đạt 100% và HR sẽ học cách bỏ qua con số đó.
    """
    rows = await db.execute(
        select(User.user_id).where(
            User.status == UserStatus.ACTIVE,
            User.system_role.is_(None),
        )
    )
    return list(rows.scalars())


async def _active_version(db: AsyncSession, document_id: int) -> DocumentVersion | None:
    return await db.scalar(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.status == VersionStatus.ACTIVE,
        )
    )


async def _latest_version(db: AsyncSession, document_id: int) -> DocumentVersion | None:
    return await db.scalar(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.revision_no.desc())
        .limit(1)
    )


async def _load_policy(db: AsyncSession, document_id: int) -> KnowledgeDocument:
    document = await db.get(KnowledgeDocument, document_id)
    if document is None or document.knowledge_domain != DocumentDomain.POLICY:
        raise HTTPException(
            status_code=404,
            detail={"code": "POLICY_NOT_FOUND", "message": "Không tìm thấy chính sách."},
        )
    return document


async def acknowledge(db: AsyncSession, user: User, document_id: int) -> dict:
    """Ghi nhận người dùng đã đọc phiên bản đang hiệu lực.

    Idempotent: bấm hai lần trả cùng kết quả, không tạo bản ghi thứ hai. Ràng buộc
    `unique(version_id, user_id)` là chốt chặn thật ở tầng DB cho trường hợp hai request
    song song cùng đọc thấy "chưa xác nhận".
    """
    document = await _load_policy(db, document_id)
    if document.status != DocumentStatus.ACTIVE:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "POLICY_ARCHIVED",
                "message": "Chính sách này đã được lưu trữ, không cần xác nhận.",
            },
        )

    version = await _active_version(db, document_id)
    if version is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "POLICY_NOT_READY",
                "message": "Chính sách đang được xử lý, vui lòng thử lại sau ít phút.",
            },
        )

    existing = await db.scalar(
        select(PolicyAcknowledgement).where(
            PolicyAcknowledgement.version_id == version.version_id,
            PolicyAcknowledgement.user_id == user.user_id,
        )
    )
    if existing is not None:
        return {
            "document_id": document_id,
            "version_id": version.version_id,
            "acknowledged_at": existing.acknowledged_at,
            "already_acknowledged": True,
        }

    record = PolicyAcknowledgement(version_id=version.version_id, user_id=user.user_id)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return {
        "document_id": document_id,
        "version_id": version.version_id,
        "acknowledged_at": record.acknowledged_at,
        "already_acknowledged": False,
    }


async def list_pending_for_user(db: AsyncSession, user: User) -> list[dict]:
    """Chính sách người dùng cần xác nhận: bật cờ, đang ACTIVE, chưa xác nhận bản hiện tại."""
    rows = await db.execute(
        select(KnowledgeDocument, DocumentVersion)
        .join(DocumentVersion, DocumentVersion.document_id == KnowledgeDocument.document_id)
        .where(
            KnowledgeDocument.knowledge_domain == DocumentDomain.POLICY,
            KnowledgeDocument.status == DocumentStatus.ACTIVE,
            KnowledgeDocument.requires_acknowledgement.is_(True),
            DocumentVersion.status == VersionStatus.ACTIVE,
        )
        .order_by(DocumentVersion.effective_date.desc().nullslast())
    )
    candidates = list(rows.all())
    if not candidates:
        return []

    acked_version_ids = set(
        (
            await db.execute(
                select(PolicyAcknowledgement.version_id).where(
                    PolicyAcknowledgement.user_id == user.user_id
                )
            )
        ).scalars()
    )

    # Từng xác nhận một bản CŨ HƠN của cùng tài liệu -> đây là bản cập nhật, không phải
    # chính sách mới. UI cần phân biệt: người ta phản ứng khác nhau với "chính sách mới"
    # và "chính sách bạn đã đọc vừa thay đổi".
    acked_document_ids: set[int] = set()
    if acked_version_ids:
        acked_document_ids = set(
            (
                await db.execute(
                    select(DocumentVersion.document_id).where(
                        DocumentVersion.version_id.in_(acked_version_ids)
                    )
                )
            ).scalars()
        )

    pending = []
    for document, version in candidates:
        if version.version_id in acked_version_ids:
            continue
        pending.append(
            {
                "document_id": document.document_id,
                "title": document.title,
                "policy_category": document.policy_category,
                "version_no": version.version_no,
                "effective_date": version.effective_date,
                "is_new_version": document.document_id in acked_document_ids,
            }
        )
    return pending


async def coverage_summary(db: AsyncSession) -> list[dict]:
    """Cho HR: mỗi chính sách bắt buộc xác nhận kèm số người đã xác nhận."""
    required_count = len(await _eligible_user_ids(db))

    rows = await db.execute(
        select(
            KnowledgeDocument.document_id,
            KnowledgeDocument.title,
            KnowledgeDocument.policy_category,
            DocumentVersion.version_id,
            DocumentVersion.version_no,
            DocumentVersion.effective_date,
            func.count(PolicyAcknowledgement.ack_id).label("acked"),
        )
        .join(DocumentVersion, DocumentVersion.document_id == KnowledgeDocument.document_id)
        .outerjoin(
            PolicyAcknowledgement,
            PolicyAcknowledgement.version_id == DocumentVersion.version_id,
        )
        .where(
            KnowledgeDocument.knowledge_domain == DocumentDomain.POLICY,
            KnowledgeDocument.status == DocumentStatus.ACTIVE,
            KnowledgeDocument.requires_acknowledgement.is_(True),
            DocumentVersion.status == VersionStatus.ACTIVE,
        )
        .group_by(
            KnowledgeDocument.document_id,
            KnowledgeDocument.title,
            KnowledgeDocument.policy_category,
            DocumentVersion.version_id,
            DocumentVersion.version_no,
            DocumentVersion.effective_date,
        )
        .order_by(KnowledgeDocument.title)
    )

    summary = []
    for document_id, title, category, _version_id, version_no, effective_date, acked in rows.all():
        summary.append(
            {
                "document_id": document_id,
                "title": title,
                "policy_category": category,
                "version_no": version_no,
                "effective_date": effective_date,
                "acknowledged_count": acked,
                "required_count": required_count,
                # Tính sẵn ở server để mọi client hiển thị cùng một con số; chia ở client
                # là cách chắc chắn nhất để hai màn hình nói hai kết quả khác nhau.
                "coverage_percent": round(acked * 100 / required_count, 1) if required_count else 0.0,
            }
        )
    return summary


async def coverage_detail(db: AsyncSession, document_id: int) -> dict:
    """Ai đã xác nhận (kèm thời điểm) và ai chưa — danh sách thứ hai mới là thứ HR cần."""
    document = await _load_policy(db, document_id)
    version = await _active_version(db, document_id)

    eligible_ids = set(await _eligible_user_ids(db))
    users = {
        user.user_id: user
        for user in (
            await db.execute(select(User).where(User.user_id.in_(eligible_ids)))
        ).scalars()
    } if eligible_ids else {}

    acked: dict[int, object] = {}
    if version is not None:
        rows = await db.execute(
            select(PolicyAcknowledgement.user_id, PolicyAcknowledgement.acknowledged_at).where(
                PolicyAcknowledgement.version_id == version.version_id
            )
        )
        acked = dict(rows.all())

    acknowledged_rows = []
    pending_rows = []
    for user_id, user in sorted(users.items(), key=lambda item: item[1].display_name):
        row = {
            "user_id": user_id,
            "display_name": user.display_name,
            "email": user.email,
            "acknowledged_at": acked.get(user_id),
        }
        (acknowledged_rows if user_id in acked else pending_rows).append(row)

    return {
        "document_id": document.document_id,
        "title": document.title,
        "version_no": version.version_no if version else None,
        "requires_acknowledgement": document.requires_acknowledgement,
        "acknowledged": acknowledged_rows,
        "pending": pending_rows,
    }


async def set_requires_acknowledgement(
    db: AsyncSession, document_id: int, *, required: bool
) -> dict:
    """HR bật/tắt yêu cầu xác nhận cho một chính sách."""
    document = await _load_policy(db, document_id)
    document.requires_acknowledgement = required
    await db.commit()
    return await coverage_detail(db, document_id)


async def _policy_content(
    db: AsyncSession, document: KnowledgeDocument, version: DocumentVersion
) -> dict:
    from src.model.document_chunk import DocumentChunk

    chunks = list(
        (
            await db.execute(
                select(DocumentChunk)
                .where(DocumentChunk.version_id == version.version_id)
                .order_by(DocumentChunk.chunk_index)
            )
        ).scalars()
    )
    return {
        "document_id": document.document_id,
        "title": document.title,
        "policy_category": document.policy_category,
        "version_no": version.version_no,
        "effective_date": version.effective_date,
        "content": "\n\n".join(chunk.content for chunk in chunks),
        "source_url": document.source_url,
    }


async def get_policy_content(db: AsyncSession, document_id: int) -> dict:
    """Nội dung để người dùng đọc trước khi xác nhận.

    Không thể bắt người ta xác nhận thứ họ không đọc được ngay tại chỗ. Nếu chỉ đưa link
    tải file rồi hỏi "đã đọc chưa" thì tính năng chỉ còn là hình thức.

    Nội dung ghép từ các chunk của version ACTIVE — dữ liệu TV3 đã tạo sẵn khi ingest,
    nên không cần đọc lại file từ storage.
    """
    document = await _load_policy(db, document_id)
    version = await _active_version(db, document_id)
    if version is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "POLICY_NOT_READY",
                "message": "Chính sách đang được xử lý, vui lòng thử lại sau ít phút.",
            },
        )

    return await _policy_content(db, document, version)


async def get_policy_content_for_hr(db: AsyncSession, document_id: int) -> dict:
    """Read the effective revision, or the latest archived revision, for HR/Admin only.

    The member endpoint deliberately continues to call ``get_policy_content`` so an
    archived policy cannot be exposed to engineers by guessing its document id.
    """
    document = await _load_policy(db, document_id)
    version = await _active_version(db, document_id) or await _latest_version(db, document_id)
    if version is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "POLICY_HAS_NO_VERSION",
                "message": "Chính sách chưa có phiên bản nội dung để xem.",
            },
        )
    return await _policy_content(db, document, version)
