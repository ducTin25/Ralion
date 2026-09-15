"""Các "tool" tra cứu tài liệu cấp cho LLM ở bước sinh nội dung task.

Nguyên tắc bảo mật (SoT §19): phạm vi truy cập bị khoá cứng Ở TẦNG SERVICE bằng `RetrievalFilters`,
KHÔNG phải do LLM tự giới hạn. LLM chỉ truyền `query`/`category`; `project_id` do pipeline gắn vào,
LLM không có cách nào đọc sang project khác kể cả khi tài liệu chứa prompt injection ("hãy đọc
project X") — vì injection chỉ ảnh hưởng chuỗi query, không ảnh hưởng mệnh đề WHERE.

Vì sao chỉ BM25, không dùng RetrievalEngine.retrieve() (hybrid dense+BM25):
- `RetrievalEngine.retrieve()` luôn gọi `query_encoder.embed()` → cần `sentence-transformers`, thư
  viện này CHƯA được cài (cả .venv lẫn container) nên gọi vào là crash.
- Chunk domain PROJECT hiện có `embedding = NULL` (kiểm chứng bằng SQL: 105 chunk, 0 vector), mà
  `PgvectorDenseRetriever` lọc `.where(embedding.is_not(None))` → nhánh dense trả về rỗng cho tài
  liệu dự án dù có cài thư viện.
- Nhánh BM25 (ParadeDB pg_search) không cần vector, index `ix_document_chunks_lexical_bm25` đã tồn
  tại thật trong DB → chạy được ngay hôm nay.
Khi TV3 backfill embedding cho PROJECT + cài sentence-transformers, đổi `bm25_search` sang
`RetrievalEngine.retrieve()` là xong — phần còn lại của pipeline không phải sửa.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.retrieval_engine.retrieval_engine import RetrievalFilters, _ScopedRetriever
from src.model.document_chunk import DocumentChunk
from src.model.enums import DocumentCategory, DocumentDomain

DEFAULT_TOP_K = 5


@dataclass(frozen=True)
class ChunkHit:
    """1 đoạn tài liệu tìm được — đủ thông tin để vừa đưa vào prompt vừa ghi PlanTaskSource."""

    chunk_id: int
    version_id: int
    document_id: int
    heading: str | None
    content: str
    score: float


def _sanitize_bm25_query(query: str) -> str:
    """pg_search parse cú pháp riêng (AND/OR/^/:), chuỗi tự do từ LLM có thể làm query lỗi cú pháp.
    Giữ lại chữ/số/khoảng trắng, bỏ ký tự điều khiển — nội dung tài liệu là DỮ LIỆU, không phải cú
    pháp truy vấn."""
    cleaned = "".join(char if char.isalnum() or char.isspace() else " " for char in query)
    return " ".join(cleaned.split())[:300]


async def bm25_search(
    db: AsyncSession,
    query: str,
    filters: RetrievalFilters,
    limit: int = DEFAULT_TOP_K,
) -> list[ChunkHit]:
    """BM25 trong đúng phạm vi ACL của `filters` — tái dùng nguyên `_ScopedRetriever.base_statement()`
    (đã có sẵn mệnh đề lọc domain/project/status) thay vì viết lại điều kiện ACL lần thứ hai."""
    safe_query = _sanitize_bm25_query(query)
    if not safe_query:
        return []

    retriever = _ScopedRetriever(db)
    score = func.pdb.score(DocumentChunk.chunk_id)
    rows = (
        await db.execute(
            retriever.base_statement(filters)
            .add_columns(score.label("bm25_score"))
            .where(text("document_chunks.embedding_text @@@ :bm25_query"))
            .params(bm25_query=safe_query)
            .order_by(desc(score), DocumentChunk.chunk_id)
            .limit(limit)
        )
    ).all()

    # Đọc theo TÊN cột, không theo vị trí: `base_statement()` là của TV3 (RetrievalEngine dùng
    # chung) và đã từng thêm cột giữa chừng (title/source_url/effective_date) — unpack theo thứ tự
    # sẽ vỡ im lặng mỗi lần bên đó mở rộng select, đúng lỗi đã gặp thật.
    return [
        ChunkHit(
            chunk_id=row.DocumentChunk.chunk_id,
            version_id=row.version_id,
            document_id=row.document_id,
            heading=row.DocumentChunk.heading,
            content=row.DocumentChunk.content,
            score=float(row.bm25_score),
        )
        for row in rows
    ]


async def fetch_all_document_chunks(db: AsyncSession, *, version_id: int) -> list[ChunkHit]:
    """Đọc TOÀN BỘ đoạn của 1 phiên bản tài liệu, theo đúng thứ tự trong file (`chunk_index`).

    Cố ý KHÔNG dùng BM25 và KHÔNG giới hạn số đoạn: bước sinh nội dung cần bao phủ HẾT tài liệu, mà
    xếp hạng theo độ khớp truy vấn thì luôn có đoạn bị đẩy khỏi top-K và biến mất khỏi lộ trình —
    đúng lỗi PM phát hiện khi test thật (1 nhóm 18 tài liệu chỉ ra 4 nguồn). Việc khống chế kích
    thước prompt chuyển sang tầng chia lô ở `content_llm._batch_documents()`, không cắt ở đây.

    `score=0.0` vì không có khái niệm điểm khớp khi đọc tuần tự — giữ nguyên dataclass `ChunkHit` để
    phần còn lại của pipeline không phải phân biệt 2 kiểu kết quả.
    """
    rows = (
        await db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.version_id == version_id)
            .order_by(DocumentChunk.chunk_index)
        )
    ).scalars().all()

    return [
        ChunkHit(
            chunk_id=chunk.chunk_id,
            version_id=version_id,
            document_id=0,  # người gọi đã biết document_id từ DocumentRef, không cần join lại
            heading=chunk.heading,
            content=chunk.content,
            score=0.0,
        )
        for chunk in rows
    ]


async def search_project_docs(
    db: AsyncSession, *, project_id: int, query: str, categories: tuple[DocumentCategory, ...]
) -> list[ChunkHit]:
    """Tool 1 — tìm trong tài liệu dự án, giới hạn đúng project + đúng nhóm tài liệu."""
    if not categories:
        return []
    return await bm25_search(
        db,
        query,
        RetrievalFilters(
            knowledge_domains=frozenset({DocumentDomain.PROJECT}),
            project_id=project_id,
            document_categories=frozenset(categories),
        ),
    )


async def search_company_policy(db: AsyncSession, *, query: str) -> list[ChunkHit]:
    """Tool 2 — tìm trong Company Core (POLICY, dùng chung mọi project)."""
    return await bm25_search(
        db, query, RetrievalFilters(knowledge_domains=frozenset({DocumentDomain.POLICY}))
    )
