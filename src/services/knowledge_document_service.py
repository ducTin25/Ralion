"""KnowledgeDocument — đọc chính sách công ty (POLICY, dùng cho "Company Core" ở Master Template)
+ CRUD tài liệu dự án thật (PROJECT): upload đơn lẻ và import từ kết quả quét repo
(repo_scanner_service).

Việc chunk/embed/version-flip KHÔNG viết lại ở đây: luồng "PM tải tay / quét thư mục" chỉ là một
ADAPTER khác của cùng lõi ingest `modules/knowledge/ingestion/versioning.ingest_or_update()` mà
luồng đồng bộ GitHub (`github_sync_worker`) đang dùng. Hai luồng dùng chung lõi để không sinh ra 2
cách chunk / 2 cách đánh version / 2 cache embedding khác nhau cùng ghi vào `document_chunks`."""

import hashlib
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.providers.embeddings import Embedder
from src.model.document_chunk import DocumentChunk
from src.model.document_version import DocumentVersion
from src.model.enums import DocumentCategory, DocumentDomain, DocumentStatus, SyncStatus, VersionStatus
from src.model.knowledge_document import KnowledgeDocument
from src.model.project import Project
from src.modules.knowledge.ingestion.versioning import ProjectIngestRequest, ingest_or_update
from src.services import document_conversion_service, repo_scanner_service, storage_service

# Nguồn "PM tải tay/quét thư mục" không có repo + commit SHA như GitHub sync, nhưng lõi ingest vẫn
# cần `source_key` (định danh ổn định để nhận ra "cùng 1 tài liệu") và `source_ref` (khác rỗng).
# Đặt tiền tố riêng để phân biệt rõ với tài liệu đến từ GitHub khi đọc dữ liệu sau này.
UPLOAD_SOURCE_KEY_PREFIX = "upload"
UPLOAD_SOURCE_REPO = "manual-upload"


def build_upload_source_key(project_id: int, category: str, title: str) -> str:
    """Định danh ổn định cho tài liệu PM tải tay.

    Gồm cả `title` (không chỉ project+category) để giữ đúng quyết định "1 category chứa NHIỀU
    document": 2 file khác tên trong cùng nhóm là 2 tài liệu riêng, upload lại đúng tên đó thì ra
    version mới của đúng tài liệu cũ. Migration `c3d4e5f6a7b8` backfill công thức này cho tài liệu
    PROJECT tạo trước khi có `source_key`, nên upload lại không sinh bản trùng.
    """
    return f"{UPLOAD_SOURCE_KEY_PREFIX}:{project_id}:{category}:{title}"


async def list_active_policy_documents(db: AsyncSession) -> list[KnowledgeDocument]:
    result = await db.execute(
        select(KnowledgeDocument)
        .where(
            KnowledgeDocument.knowledge_domain == DocumentDomain.POLICY,
            KnowledgeDocument.status == DocumentStatus.ACTIVE,
        )
        .order_by(KnowledgeDocument.policy_category)
    )
    return list(result.scalars().all())


async def list_project_documents(
    db: AsyncSession, project_id: int
) -> list[tuple[KnowledgeDocument, DocumentVersion | None]]:
    documents_result = await db.execute(
        select(KnowledgeDocument)
        .where(
            KnowledgeDocument.project_id == project_id,
            KnowledgeDocument.knowledge_domain == DocumentDomain.PROJECT,
            KnowledgeDocument.status == DocumentStatus.ACTIVE,
        )
        .order_by(KnowledgeDocument.document_category, KnowledgeDocument.title)
    )
    documents = list(documents_result.scalars().all())

    pairs: list[tuple[KnowledgeDocument, DocumentVersion | None]] = []
    for document in documents:
        latest_version = await db.scalar(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document.document_id)
            .order_by(DocumentVersion.revision_no.desc())
            .limit(1)
        )
        pairs.append((document, latest_version))
    return pairs


async def archive_project_document(
    db: AsyncSession, *, project_id: int, document_id: int
) -> None:
    """Remove a project document from active knowledge without breaking historical citations.

    Versions and chunks intentionally remain: onboarding plans may reference them. Retrieval and
    the PM inventory already scope to ACTIVE documents, so archiving is the safe delete semantic.
    """
    document = await db.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.document_id == document_id,
            KnowledgeDocument.project_id == project_id,
            KnowledgeDocument.knowledge_domain == DocumentDomain.PROJECT,
            KnowledgeDocument.status == DocumentStatus.ACTIVE,
        )
    )
    if document is None:
        raise ValueError("Project document not found")
    document.status = DocumentStatus.ARCHIVED
    await db.commit()


def _rebuild_markdown(chunks: list[DocumentChunk]) -> str:
    """Ghép các chunk của 1 version thành 1 tài liệu markdown đọc được.

    Chunker (`chunk_markdown_document`) chia tài liệu thành các khối KHÔNG chồng lấn và giữ lại
    tiêu đề của mỗi khối trong `section_path` (dạng "Cài đặt > Yêu cầu hệ thống"), nên ghép lại
    theo `chunk_index` + phát lại dòng heading khi đổi mục là dựng lại được bản đọc.
    """
    parts: list[str] = []
    previous: list[str] = []
    for chunk in chunks:
        segments = [s.strip() for s in (chunk.section_path or "").split(">") if s.strip()]
        if segments == ["Document"]:
            # Nhánh tài liệu không có heading nào — `parse_markdown_ast` đặt path mặc định này,
            # nó không phải tiêu đề thật nên không in ra.
            segments = []
        shared = 0
        while shared < len(segments) and shared < len(previous) and segments[shared] == previous[shared]:
            shared += 1
        for level in range(shared, len(segments)):
            parts.append(f"{'#' * (level + 1)} {segments[level]}")
        previous = segments
        content = chunk.content.strip()
        if content:
            parts.append(content)
    return "\n\n".join(parts)


async def get_project_document_content(
    db: AsyncSession, *, project_id: int, document_id: int
) -> tuple[KnowledgeDocument, DocumentVersion, str]:
    """Nội dung tài liệu dự án để ĐỌC NGAY TRONG APP (không mở tab ngoài, không tải file về).

    Nguồn nội dung là các chunk đã ingest, KHÔNG phải file gốc trên storage. Đây là quyết định có
    chủ đích:
      - Tài liệu đến từ GitHub đã đi qua secret-scan/redaction trước khi ingest — đọc lại file gốc
        sẽ trả về bản CHƯA redact, tức là làm yếu đúng ràng buộc bảo mật của luồng đồng bộ.
      - Tài liệu `.pdf`/`.docx` PM tải lên được lưu nguyên bản nhị phân trên storage; bản markdown
        đọc được chỉ tồn tại sau bước convert lúc ingest.
      - Không phải fetch mạng lúc xem, không dính CORS, và PM đọc đúng thứ hệ thống thật sự biết
        về tài liệu (cùng nội dung mà retrieval/citation dùng).
    """
    document = await db.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.document_id == document_id,
            KnowledgeDocument.project_id == project_id,
            KnowledgeDocument.knowledge_domain == DocumentDomain.PROJECT,
        )
    )
    if document is None:
        raise ValueError("Project document not found")

    version = await db.scalar(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.revision_no.desc())
        .limit(1)
    )
    if version is None:
        raise ValueError("Tài liệu chưa có phiên bản nào để xem")

    chunks = list(
        (
            await db.execute(
                select(DocumentChunk)
                .where(DocumentChunk.version_id == version.version_id)
                .order_by(DocumentChunk.chunk_index)
            )
        )
        .scalars()
        .all()
    )
    return document, version, _rebuild_markdown(chunks)


async def list_existing_checksums_for_project(db: AsyncSession, project_id: int) -> set[str]:
    """Checksum của MỌI version (mọi status) thuộc tài liệu dự án — dùng để scanner phát hiện
    DUPLICATE_OR_STALE khi PM quét lại file đã import trước đó."""
    result = await db.execute(
        select(DocumentVersion.checksum)
        .join(KnowledgeDocument, DocumentVersion.document_id == KnowledgeDocument.document_id)
        .where(
            KnowledgeDocument.project_id == project_id,
            KnowledgeDocument.knowledge_domain == DocumentDomain.PROJECT,
        )
    )
    return set(result.scalars().all())


async def confirm_project_document_category(
    db: AsyncSession, *, project_id: int, document_id: int, category: DocumentCategory
) -> KnowledgeDocument:
    """Apply the PM's HITL decision for a PROJECT document's category.

    Covers two cases with the same write path:
    - AMBIGUOUS -> CLASSIFIED: the classifier could not decide, PM reviews a staged
      GitHub document for the first time. The next full GitHub sync uses this
      confirmed category to run the normal version/chunk/embedding pipeline
      against a newly pinned source snapshot.
    - CLASSIFIED -> CLASSIFIED (different category): PM overrides a category that
      was already set (by the classifier, by a prior HITL confirm, or chosen by
      themselves during upload/scan-import) but turns out to be wrong. This is a
      metadata-only correction -- document_category only gates retrieval scope
      (`scope_predicates`), so no re-embed/re-chunk is needed.
    """
    document = await db.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.document_id == document_id,
            KnowledgeDocument.project_id == project_id,
            KnowledgeDocument.knowledge_domain == DocumentDomain.PROJECT,
        )
    )
    if document is None:
        raise ValueError("Project document not found")

    if document.category_classification_status == "AMBIGUOUS":
        document.category_review_reason = "confirmed by project reviewer"
    elif document.document_category != category:
        document.category_review_reason = (
            f"overridden by project reviewer: {document.document_category} -> {category}"
        )
    else:
        return document

    document.document_category = category
    document.category_confirmed = True
    document.category_classification_status = "CLASSIFIED"
    # PARTIAL means the persisted GitHub inventory still has at least one document awaiting a
    # category decision. Recompute it after every decision instead of waiting for another sync.
    project = await db.get(Project, project_id)
    outstanding_reviews = int(
        await db.scalar(
            select(func.count())
            .select_from(KnowledgeDocument)
            .where(
                KnowledgeDocument.project_id == project_id,
                KnowledgeDocument.knowledge_domain == DocumentDomain.PROJECT,
                KnowledgeDocument.status == DocumentStatus.ACTIVE,
                KnowledgeDocument.category_confirmed.is_(False),
            )
        )
        or 0
    )
    if project is not None and project.sync_status == SyncStatus.PARTIAL and outstanding_reviews == 0:
        project.sync_status = SyncStatus.SUCCESS
    await db.commit()
    await db.refresh(document)
    return document


async def _import_one(
    db: AsyncSession,
    *,
    project_id: int,
    category: str,
    title: str,
    content: bytes,
    created_by_user_id: int,
    embedder: Embedder,
    filename: str | None = None,
) -> tuple[KnowledgeDocument, DocumentVersion]:
    """Adapter: biến 1 file PM tải lên thành `ProjectIngestRequest` rồi giao cho lõi ingest chung.

    Lõi (`ingest_or_update`) tự lo: tìm/tạo document theo `source_key` → chunk theo cấu trúc
    (`chunk_markdown_document`) → embed (có cache theo `content_hash`) → archive version cũ →
    activate version mới → ghi `DocumentChunk` kèm `anchor`/`section_path`. Ở đây KHÔNG tự dựng
    `DocumentVersion` hay tự chunk, để tài liệu tải tay và tài liệu đồng bộ GitHub nằm cùng một
    định dạng dữ liệu — nhờ vậy `bm25_search()` của pipeline sinh plan đọc được cả hai như nhau.
    """
    project = await db.get(Project, project_id)
    if project is None:
        raise ValueError("Project not found")
    project_key = project.key
    # Conversion/storage can be slow (PDF/DOCX and remote object storage). The project read is
    # complete, so release its transaction before doing either.
    await db.commit()

    # Đọc nội dung THEO ĐỊNH DẠNG, không decode UTF-8 mù quáng: `.md/.txt` decode thẳng, còn
    # `.pdf/.docx` là nhị phân nên phải qua converter. Dùng đúng converter mà luồng HR đang dùng
    # (`document_conversion_service`) thay vì viết bộ đọc thứ hai — hai luồng ingest cùng một cách
    # biến file thành markdown thì chunk/embed phía sau mới giống nhau.
    #
    # `filename` (tên file thật PM tải lên / đường dẫn trong repo) mới là nguồn đuôi file đáng tin;
    # `title` là chữ PM gõ tay, có thể không có đuôi.
    source_filename = filename or title
    extension = Path(source_filename).suffix.lower()
    if extension not in document_conversion_service.PROJECT_SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(document_conversion_service.PROJECT_SUPPORTED_EXTENSIONS))
        raise ValueError(
            f"Tài liệu {title!r} có định dạng {extension or 'không xác định'} không được hỗ trợ. "
            f"Chỉ nhận: {supported}."
        )
    try:
        raw_content = document_conversion_service.convert_to_markdown(content, source_filename)
    except document_conversion_service.DocumentConversionError as exc:
        raise ValueError(f"Tài liệu {title!r}: {exc}") from exc

    # Nội dung giống hệt lần trước -> lõi ingest nhận ra qua checksum và bỏ qua bước chunk/embed
    # (chỉ cập nhật lại permalink), nên `source_ref` gắn theo checksum là mốc "phiên bản nội dung"
    # đúng nghĩa cho nguồn tải tay, thay cho commit SHA của GitHub.
    checksum = hashlib.sha256(content).hexdigest()
    source_key = build_upload_source_key(project_id, category, title)
    source_ref = f"{UPLOAD_SOURCE_KEY_PREFIX}:{checksum[:16]}"

    # A candidate may match an older archived revision of the same logical file. Importing that
    # revision again must not roll the document back and make stale content ACTIVE. Exact matches
    # of the current revision are harmless no-ops; genuinely changed content continues below and
    # becomes the new ACTIVE revision through the shared versioning core.
    existing_document = await db.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.knowledge_domain == DocumentDomain.PROJECT,
            KnowledgeDocument.project_id == project_id,
            KnowledgeDocument.source_key == source_key,
        )
    )
    if existing_document is not None:
        active_version = await db.scalar(
            select(DocumentVersion).where(
                DocumentVersion.document_id == existing_document.document_id,
                DocumentVersion.status == VersionStatus.ACTIVE,
            )
        )
        matching_version = await db.scalar(
            select(DocumentVersion).where(
                DocumentVersion.document_id == existing_document.document_id,
                DocumentVersion.source_ref == source_ref,
            )
        )
        if matching_version is not None and active_version is not None:
            existing_document.status = DocumentStatus.ACTIVE
            return existing_document, active_version

    safe_filename = title.replace("/", "__")
    storage_uri = storage_service.upload_document_bytes(content, project_key, safe_filename)

    request = ProjectIngestRequest(
        project_id=project_id,
        created_by_user_id=created_by_user_id,
        source_key=source_key,
        source_url=storage_uri,
        source_repo=UPLOAD_SOURCE_REPO,
        source_path=title,
        document_category=DocumentCategory(category),
        raw_content=raw_content,
        source_ref=source_ref,
        title=title,
        # PM tự chọn category lúc upload là quyết định HITL có thẩm quyền, không phải phỏng đoán của
        # classifier — đánh dấu CLASSIFIED/confirmed ngay (cũng là điều kiện của CHECK
        # `ck_knowledge_documents_project_category_classification`).
        category_confirmed=True,
        category_classification_status="CLASSIFIED",
        category_review_reason="PM chọn nhóm khi tải tài liệu lên",
    )
    document = await ingest_or_update(db, request, embedder, release_before_external=True)

    version = await db.scalar(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document.document_id,
            DocumentVersion.status == VersionStatus.ACTIVE,
        )
    )
    if version is None:
        raise ValueError(f"Ingest xong nhưng tài liệu {title!r} không có version ACTIVE nào")
    # End this file's read transaction before the next file waits on storage or embeddings.
    await db.commit()
    return document, version


async def import_single_file(
    db: AsyncSession,
    *,
    project_id: int,
    category: str,
    title: str,
    content: bytes,
    created_by_user_id: int,
    embedder: Embedder,
    filename: str | None = None,
) -> tuple[KnowledgeDocument, DocumentVersion]:
    document, version = await _import_one(
        db,
        filename=filename,
        project_id=project_id,
        category=category,
        title=title,
        content=content,
        created_by_user_id=created_by_user_id,
        embedder=embedder,
    )
    await db.commit()
    await db.refresh(document)
    await db.refresh(version)
    return document, version


async def import_scan_selection(
    db: AsyncSession,
    *,
    project_id: int,
    scan_session_id: str,
    selections: list[tuple[str, str, str | None]],
    created_by_user_id: int,
    embedder: Embedder,
) -> list[tuple[KnowledgeDocument, DocumentVersion]]:
    """selections: [(candidate_id, category, title_override), ...] — chỉ chứa candidate PM đã
    chọn include=True (router lọc trước khi gọi hàm này). Mỗi file commit sau khi indexing hoàn
    tất để không giữ transaction trong lúc file kế tiếp chờ storage/embedding."""
    session = repo_scanner_service.get_scan_session(scan_session_id)
    if session is None or session.project_id != project_id:
        raise ValueError("Scan session không tồn tại hoặc đã hết hạn")

    results: list[tuple[KnowledgeDocument, DocumentVersion]] = []
    for candidate_id, category, title_override in selections:
        content = session.file_bytes.get(candidate_id)
        candidate = session.candidates.get(candidate_id)
        if content is None or candidate is None:
            raise ValueError(f"Candidate '{candidate_id}' không tồn tại trong scan session này")
        title = title_override or candidate.relative_path
        document, version = await _import_one(
            db,
            filename=candidate.relative_path,
            project_id=project_id,
            category=category,
            title=title,
            content=content,
            created_by_user_id=created_by_user_id,
            embedder=embedder,
        )
        results.append((document, version))

    await db.commit()
    for document, version in results:
        await db.refresh(document)
        await db.refresh(version)

    repo_scanner_service.cleanup_scan_session(scan_session_id)
    return results
