# Báo cáo hoàn thành Phase 3 — Project Knowledge / Documents (owner-docs) + UC-04

> Trạng thái: **ĐÃ CODE XONG, ĐÃ TEST, ĐÃ CHẠY THẬT TRÊN DOCKER**.
> Theo đúng plan đã duyệt: `docs/PM/Phase-3/plan-phase3-documents.md`.
> Không đụng Phase 1/2 đã xong — không sửa file nào thuộc Master Template/Project/Membership.

## 0. Thay đổi so với plan lúc bắt đầu code

Trong lúc code, phát sinh 2 điểm cần quyết định thêm mà plan gốc chưa lường hết — cả 2 đều đã bàn
với PM/team trước khi làm, không tự ý đổi hướng:

1. **Trigger DB có sẵn từ trước ép "đúng 1 ACTIVE" thay vì "tối đa 1"** — khi code
   `activate_version()` và viết test, Postgres báo lỗi thật `Document X must have exactly one
   ACTIVE version, found 0`. Trigger `enforce_one_active_document_version()` (migration
   `a1b2c3d4e5f6_add_sync_fields_and_schema_invariants.py`, **không phải do Phase 3 tạo**) chặn cả
   trạng thái hợp lệ "document vừa tạo, version còn PROCESSING, chưa có ACTIVE nào" — mà đây chính
   là trạng thái bình thường của luồng PM import (SoT §14: PROCESSING → TV3 xử lý → ACTIVE, luôn ở
   2 transaction khác nhau). Đã xác nhận với team (Mai Anh, phụ trách phần TV3/embedding) đây là
   bug của trigger, được đồng ý sửa. Đã viết migration mới sửa đúng lại ý nghĩa gốc ("tối đa 1",
   cho phép 0) — xem mục 1.1. Không đụng file model `.py`/cột/bảng nào, chỉ sửa 1 hàm PL/pgSQL.
2. **Không dùng ZIP** — theo yêu cầu PM, bỏ hẳn luồng "upload file ZIP → server giải nén" (dễ có
   rủi ro zip-bomb/zip-slip). Thay bằng PM chọn thẳng **folder** dự án qua
   `<input type="file" webkitdirectory>` — trình duyệt trả về toàn bộ cây file kèm đường dẫn tương
   đối (`webkitRelativePath`), **frontend tự lọc chỉ file tài liệu hợp lệ NGAY TRƯỚC KHI upload**
   (cùng 1 bộ rule với server) nên chọn folder to (kể cả `node_modules`/`.git` bên trong) vẫn nhẹ —
   không có bước "giải nén" nào ở server nữa.
3. **AI classification dùng DeepSeek thay vì OpenAI** — PM cung cấp key riêng, muốn tách khỏi tính
   năng Chat hiện có (đang dùng OpenAI). Thêm hàm riêng `get_classifier_llm()`, không đụng `get_llm()`.

Ngoài 3 điểm trên, mọi phần còn lại đúng theo plan đã duyệt.

## 1. Backend — đã code xong toàn bộ

### 1.1 Migration sửa trigger INV2

File: `alembic/versions/9e2a4d6533a4_relax_one_active_document_version_.py` — sửa
`enforce_one_active_document_version()` từ `IF v_active_count <> 1` (đúng 1) thành
`IF v_active_count > 1` (tối đa 1, cho phép 0). `alembic upgrade head` chạy thành công,
`alembic check` sạch (không drift) — xem log ở mục 5.

### 1.2 File mới

| File | Vai trò |
|---|---|
| `src/services/storage_service.py` | `upload_document_bytes()` — tách logic Cloudinary từ `scripts/upload_sample_docs_to_cloudinary.py`, nhận bytes thay vì Path |
| `src/services/repo_scanner_service.py` | Lõi UC-04: lọc file ứng viên, phân loại rule-based + AI fallback (DeepSeek), phát hiện trùng lặp, build Coverage Report, quản lý scan session in-memory (TTL 30 phút) |
| `src/services/document_version_service.py` | `create_processing_version()` + `activate_version()` (INV2-safe, dùng lại pattern flush đã chứng minh ăn ở Phase 2) |
| `src/services/knowledge_document_service.py` | Mở rộng: `list_project_documents`, `list_existing_checksums_for_project`, `import_single_file`, `import_scan_selection` |
| `src/api/routers/knowledge_document_router.py` | Thêm 4 route mới dưới `/knowledge-documents/pm` |
| `src/dto/response/document_version_response_dto.py`, `repo_scan_response_dto.py`, `knowledge_document_response_dto.py` (mở rộng) | DTO response |
| `src/dto/request/knowledge_document_request_dto.py` | `ImportScanSelectionRequestDTO` |
| `src/services/llm.py` | Thêm `get_classifier_llm()` (DeepSeek) |
| `src/config.py` | Thêm `deepseek_api_key` |

### 1.3 API mới

| Method | Path | Vai trò |
|---|---|---|
| `GET` | `/knowledge-documents/pm/projects/{project_id}` | Danh sách tài liệu dự án + version mới nhất |
| `POST` | `/knowledge-documents/pm/projects/{project_id}/upload` | Upload 1 file đơn lẻ (multipart) |
| `POST` | `/knowledge-documents/pm/projects/{project_id}/scan` | Quét folder (multipart nhiều file), trả Coverage Report — **không ghi DB** |
| `POST` | `/knowledge-documents/pm/projects/{project_id}/scan/{scan_session_id}/import` | Ghi DB thật + Cloudinary cho candidate PM đã duyệt |

Route `GET /knowledge-documents/policy` (Company Core, Phase 2) giữ nguyên không đổi.

### 1.4 Cơ chế quét (UC-04)

1. **Lọc** — đúng đuôi `.md/.txt/.pdf/.docx`; loại thư mục `.git/node_modules/dist/build/.next/
   __pycache__/.venv`; loại file nhạy cảm theo tên (`.env` trừ `.env.example`, `*.pem`, `*.key`,
   tên chứa `secret`/`token`/`password`). Lọc **cả ở client** (trước khi upload,
   `clientFileFilter.ts`) **và server** (double-check, không tin client).
2. **Phân loại** — ưu tiên: (a) từ khoá trong đường dẫn thư mục (confidence 0.95) → (b) từ khoá
   trong tên file (0.85) → (c) từ khoá trong ~2000 ký tự đầu nội dung, chỉ áp dụng cho `.md/.txt`
   (0.6) → (d) AI (DeepSeek, `get_classifier_llm()`) nếu vẫn không xác định được — lỗi/timeout thì
   rơi về UNCLASSIFIED, không chặn luồng.
3. **Trùng lặp** — checksum SHA-256 trùng tài liệu đã có trong project → `DUPLICATE_OR_STALE`; 2
   file trong cùng lượt quét có tên gần giống (bỏ qua từ "old/new/final/draft/copy/backup/v1/v2")
   → cả 2 gắn `DUPLICATE_OR_STALE`, PM tự chọn bản đúng.
4. **Coverage Report** — 5 category bắt buộc, category nào không có candidate FOUND → `MISSING`.

## 2. Frontend — đã code xong toàn bộ

| File | Vai trò |
|---|---|
| `dto/responseDTO/document.response.ts` | `ProjectDocumentResponseDTO`, `DocumentVersionResponseDTO` |
| `dto/responseDTO/repoScan.response.ts` | `ScanCandidateResponseDTO`, `CoverageReportResponseDTO` |
| `components/documents/clientFileFilter.ts` | Lọc file client-side, khớp đúng rule server |
| `components/documents/documentCategoryMeta.ts` | Label/icon/màu 5 category (khớp Master Template) |
| `components/documents/DocumentsView.tsx` | Trang chính: KPI, lưới 5 category, nút Quét/Tải lên |
| `components/documents/RepoScanWizard.tsx` | Modal 3 bước: chọn folder → đang quét → Coverage Report + Approve & Import |
| `components/documents/DocumentUploadModal.tsx` | Upload 1 file bù cho category MISSING |
| `PmShell.tsx` | Nav "Tài liệu dự án" bật `enabled: true` |
| `app/product-manager/page.tsx` | Nối `DocumentsView` vào route `docs` |
| `api.ts`, `lib/api.ts` | `postMultipart`, 4 hàm gọi API mới, `PM_KNOWLEDGE_DOCUMENTS_ENDPOINT` |

Tái dùng thẳng `ui/DocumentPreviewModal.tsx` (đã có từ Company Core) để xem lại tài liệu vừa import
— không viết lại.

## 3. Sample repo test fixture

`docs/PM/Phase-3/sample-repo/` — 1 project FastAPI "Todo API" **chạy được thật** (`app/main.py`,
`models.py`, `schemas.py`, `routes.py`, `tests/test_todos.py`, `requirements.txt`), cùng bộ tài
liệu 5 category viết dài/chi tiết đúng chuẩn 1 dự án thật. Giữ tối giản, chỉ đúng 1 case biên:
`notes-final.md` (tên sai convention, nội dung khớp SETUP — test phân loại theo nội dung), cộng
`.env`/`.env.example`, `node_modules/fake-pkg/`, `assets/demo-diagram.png`, `app.log` (đều bị loại
theo đuôi file/thư mục). **Cập nhật sau báo cáo này**: đã bỏ `old-setup.md`/`setup.md`/
`CONTRIBUTING.md` khỏi fixture (PM phản hồi quá nhiều file nhiễu không cần thiết) — case
DUPLICATE_OR_STALE vẫn còn test riêng đầy đủ ở `PM-test/test_repo_scanner.py`, không mất bằng
chứng, chỉ không lặp lại trong fixture thật nữa. Evidence JSON ở mục 6.1 dưới đây là chụp lại từ
lúc fixture còn 2 file đó — nội dung 5 file chính (README/architecture/setup/access/codebase) và
cơ chế loại trừ (.env/node_modules/code) không đổi.

## 4. Bug tìm thấy khi code (không phải trigger)

Test `test_activate_version_rejects_version_from_other_document` lỗi
`sqlalchemy.exc.MissingGreenlet` — nguyên nhân: `await db.rollback()` expire mọi object trong
session, sau đó code truy cập `doc_2.document_id` (đã hết hạn) kích hoạt lazy-load đồng bộ, không
hợp lệ với async session. Sửa bằng cách cache `document_id`/`version_id` vào biến local **trước**
khi gọi `rollback()`, dùng biến đó cho các câu dọn dữ liệu sau — bug thuộc về test, không phải code
service.

## 5. Bằng chứng — test tự động

```
$ pytest PM-test/ tests/ -v
...
============================= 64 passed in 9.10s ==============================
```

8 file test PM (không tính Phase 1/2), riêng Phase 3 có 3 file mới:
- `PM-test/test_repo_scanner.py` — 13 test (lọc extension/thư mục/tên nhạy cảm, phân loại theo
  path/filename/content, fallback AI khi lỗi, Coverage Report, giới hạn dung lượng/số file, vòng
  đời scan session).
- `PM-test/test_knowledge_documents_project.py` — 3 test (upload tạo `PROCESSING`, version 2 vẫn
  `PROCESSING` không tự activate, scan+import end-to-end dùng `sample-repo/` thật qua API, assert
  đúng file bị loại).
- `PM-test/test_document_version_activation.py` — 2 test (`activate_version()` archive đúng bản
  cũ, từ chối version không thuộc document).

```
$ alembic check
No new upgrade operations detected.

$ ruff check src/ PM-test/
All checks passed!

$ (frontend) npx tsc --noEmit          → sạch
$ (frontend) npx eslint --max-warnings=0 → sạch
$ (frontend) npx prettier --write        → chỉ đổi whitespace
$ (frontend) npx next build              → Compiled successfully, 13/13 static pages
```

## 6. Bằng chứng — chạy thật trên Docker

`docker compose up -d --build backend` → container `p-040-backend-1` healthy. Tạo project test
`PHASE3EVID` (project_id=563), quét trực tiếp các file thật trong `docs/PM/Phase-3/sample-repo/`
qua `curl` multipart tới API thật đang chạy trong Docker (không mock).

### 6.1 Coverage Report thật (12 file gửi lên, gồm cả file phải bị loại)

```json
{
  "scan_session_id": "d505b257b9e0467c9ceb6cf2e20a4436",
  "candidates": [
    { "relative_path": "README.md", "suggested_category": "OVERVIEW", "status": "FOUND" },
    { "relative_path": "docs/architecture/system-design.md", "suggested_category": "ARCHITECTURE", "status": "FOUND" },
    { "relative_path": "docs/setup/local-setup.md", "suggested_category": "SETUP", "status": "FOUND" },
    { "relative_path": "docs/access/security-guide.md", "suggested_category": "ACCESS_SECURITY", "status": "FOUND" },
    { "relative_path": "docs/codebase-guide.md", "suggested_category": "CODEBASE_GUIDE", "status": "FOUND" },
    { "relative_path": "old-setup.md", "status": "DUPLICATE_OR_STALE", "reason": "tên file gần giống file khác trong lượt quét..." },
    { "relative_path": "setup.md", "status": "DUPLICATE_OR_STALE" },
    { "relative_path": "notes-final.md", "suggested_category": "SETUP", "confidence": 0.6, "reason": "nội dung chứa từ khoá liên quan", "status": "FOUND" }
  ],
  "missing_categories": []
}
```

Gửi thêm `.env`, `.env.example`, `app/main.py`, `node_modules/fake-pkg/index.js` trong cùng request
— **cả 4 file này KHÔNG xuất hiện trong `candidates`** (bị loại đúng như thiết kế), xác nhận cơ chế
lọc hoạt động thật, không chỉ đúng trên unit test.

### 6.2 Import thật — ghi DB + Cloudinary thật

Import 5 candidate FOUND, bỏ qua 3 candidate còn lại. Kết quả (rút gọn):

```json
[
  { "document_id": 76, "document_category": "OVERVIEW",
    "latest_version": { "status": "PROCESSING",
      "storage_uri": "https://res.cloudinary.com/lwqx5mla/raw/upload/.../PHASE3EVID/README.md" } },
  { "document_id": 77, "document_category": "ARCHITECTURE", ... },
  { "document_id": 78, "document_category": "SETUP", ... },
  { "document_id": 79, "document_category": "ACCESS_SECURITY", ... },
  { "document_id": 80, "document_category": "CODEBASE_GUIDE", ... }
]
```

Verify file thật sự nằm trên Cloudinary (không phải URL giả):
```
$ curl -I https://res.cloudinary.com/lwqx5mla/raw/upload/.../PHASE3EVID/README.md
HTTP 200
```

### 6.3 Bằng chứng INV2 (query DB trực tiếp, không qua code Python)

```sql
SELECT document_id, COUNT(*) FROM document_versions
WHERE status='ACTIVE' GROUP BY document_id HAVING COUNT(*) > 1;
-- (0 rows)

SELECT document_id, version_no, status FROM document_versions WHERE document_id IN (76,77,78,79,80);
--  document_id | version_no |   status
-- -------------+------------+------------
--           76 |          1 | PROCESSING
--           77 |          1 | PROCESSING
--           78 |          1 | PROCESSING
--           79 |          1 | PROCESSING
--           80 |          1 | PROCESSING
```

Xác nhận đúng thiết kế: import xong dừng ở `PROCESSING`, Phase 3 không tự activate.

### 6.4 Bằng chứng `activate_version()` + trigger đã sửa (giả lập việc TV3 sẽ làm)

```
>>> activate_version(document_id=76, version_id=76)
after activate v76: ACTIVE
active count for doc 76: 1

>>> tạo version 2 (id=81) cho document 76, gọi activate_version(76, 81)
v1 (old) status: ARCHIVED
v2 (new) status: ACTIVE
active count for doc 76 after 2nd activate: 1
```

Xác nhận: version cũ tự động `ARCHIVED` khi version mới được activate, luôn đúng 1 `ACTIVE` — cả
lúc document mới tạo (0 ACTIVE, trigger đã sửa cho phép) lẫn lúc activate lần 2 (archive-trước-rồi-
mới-active, không có khoảnh khắc 2 ACTIVE cùng lúc).

Dọn dữ liệu test: `DELETE /api/v1/projects/pm/563` → `status=ARCHIVED` (xoá mềm, giữ lịch sử, đúng
quy ước dự án).

### 6.5 Frontend sống

```
$ npx next start
✓ Ready in 242ms
$ curl -o /dev/null -w "%{http_code}" http://localhost:3000/product-manager
200
$ curl http://localhost:3000/product-manager | grep "Tài liệu dự án"
Tài liệu dự án
```

## 7. Gap đã biết (ghi nhận, không phải thiếu sót bỏ quên)

- **Cloudinary public URL** — SoT khuyến nghị signed URL cho tài liệu nội bộ, nhưng dự án chưa có
  Auth (quyết định giữ từ Phase 2) nên chưa có ai để "kiểm tra quyền" trước khi ký URL — giữ pattern
  public `resource_type="raw"` như Company Core đang chạy, làm signed URL khi có Auth thật.
- **TV3 (extract/chunk/embedding) chưa build** — `document_chunks` vẫn rỗng, đúng phạm vi giao cho
  phần khác (SoT §17.4). `activate_version()` đã viết sẵn + test để TV3 gọi trực tiếp.
- **Rename-mapping thông minh + báo "file bị xoá khỏi repo"** ở lần quét lại sau — chưa làm, ghi rõ
  là mở rộng làm sau trong plan.
- **Không hỗ trợ kết nối Git URL trực tiếp** (OAuth GitHub/GitLab) — chỉ chọn folder local, đúng
  phạm vi MVP.

## 8. Không làm trong Phase 3 (đúng theo plan, không lấn phạm vi)

Không sửa file model `.py` nào (`KnowledgeDocument`, `DocumentVersion`, `DocumentChunk`,
`src/model/enums.py` giữ nguyên 100%) — ngoại lệ duy nhất là migration sửa hàm trigger PL/pgSQL đã
nêu ở mục 0/1.1. Không thêm authorization/đăng nhập. Không đụng bất kỳ file Phase 1/2 nào ngoài
`PM-test/conftest.py` (thêm dọn dẹp `KnowledgeDocument`/`DocumentVersion` theo `project_ids` đã
track, tránh vướng FK khi test Phase 3 xoá project — không đổi logic dọn dẹp cũ).

## 9. Cập nhật sau khi merge `develop` (pipeline embedding POLICY — BGE-M3 + ParadeDB)

Sau khi Phase 3 đã hoàn thành (mục 1-8), nhánh `pm-document-management` merge `develop` — mang theo
thiết kế lại `DocumentVersion`/`DocumentChunk`/`KnowledgeDocument` phục vụ pipeline embedding POLICY
(BGE-M3, ParadeDB BM25 hybrid retrieval). Việc merge này đổi schema `DocumentVersion` mà Phase 3
đang dùng — **đã điều chỉnh lại Phase 3 cho khớp, không đụng gì tới phần POLICY/`develop`**.

### 9.1 Thay đổi schema (từ `develop`, không phải Phase 3 tạo ra)

| Cột | Trước (Phase 3 gốc) | Sau (từ `develop`) |
|---|---|---|
| `version_no` | `int` — số đếm 1/2/3 | `str` — nhãn version lấy từ tài liệu nguồn (POLICY dùng, VD "3.2") |
| `revision_no` | không có | **mới, `int` NOT NULL** — số thứ tự nội bộ thật, thay cho ý nghĩa `version_no` cũ |
| `embedding_model_version` | không có | **mới, `str` NOT NULL** — tên model embedding đã xử lý version đó |
| Unique constraint | `(document_id, version_no)` | `(document_id, version_no, embedding_model_version)` + thêm `(document_id, revision_no)` |

`KnowledgeDocument` thêm `source_key` nhưng CHECK constraint chỉ bắt buộc cho nhánh POLICY — nhánh
PROJECT (Phase 3 dùng) không bị ảnh hưởng, không cần sửa gì.

### 9.2 Quyết định cho nhánh PROJECT (tài liệu dự án PM tự import)

Tài liệu PROJECT không có "nhãn version nguồn" như POLICY, và Phase 3 không chạy embedding (đúng
ranh giới TV3 đã chốt) — nên:
- `revision_no` = số đếm tăng dần (giữ đúng ý nghĩa `version_no` cũ trước đây).
- `version_no` = `str(revision_no)` — mirror số đếm dưới dạng chuỗi, vì PROJECT không có nhãn riêng.
- `embedding_model_version` = `"pending"` (hằng số `PENDING_EMBEDDING_MODEL_VERSION` trong
  `document_version_service.py`) — placeholder rõ ràng, KHÔNG bịa tên model thật. TV3 sẽ ghi đè giá
  trị thật khi họ mở rộng pipeline sang PROJECT domain.

### 9.3 File đã sửa

`src/services/document_version_service.py` (`next_version_no`→`next_revision_no`,
`create_processing_version` set đủ 3 field mới), `src/services/knowledge_document_service.py`
(gọi hàm đổi tên, `order_by` đổi sang `revision_no`), `src/dto/response/document_version_response_dto.py`
(`version_no: str`, thêm `revision_no: int`), `frontend/.../document.response.ts` (type khớp lại),
`PM-test/test_document_version_activation.py` + `test_knowledge_documents_project.py` (set đủ field
mới khi tạo `DocumentVersion` trực tiếp, thêm `source_key` cho `KnowledgeDocument` domain POLICY
trong test, assertion đổi sang check `revision_no`).

### 9.4 Hạ tầng — đổi image Postgres

`develop` đổi `docker-compose.yml`: `db` từ `pgvector/pgvector:pg16` → `paradedb/paradedb:v0.23.4-pg16`
(thêm extension `pg_search`, cần `shared_preload_libraries=pg_search`). Đã `docker compose pull db`
+ `docker compose up -d db` (volume `pgdata` giữ nguyên, không mất dữ liệu — cùng Postgres 16).

### 9.5 Alembic — gộp 2 nhánh migration

Nhánh Phase 3 (`9e2a4d6533a4`) và nhánh `develop` (`a8b9c0d1e2f3`) rẽ từ cùng gốc `b3c4d5e6f7a8`
→ sau merge có 2 head. Đã tạo migration gộp
`alembic/versions/781ee9706e41_merge_phase3_documents_branch_with_.py` (`alembic merge heads`,
`upgrade`/`downgrade` rỗng — chỉ gộp điểm, không đổi schema). `alembic upgrade head` chạy sạch từ
đầu tới `781ee9706e41`.

`alembic check` báo lệch 1 bảng/index (`retrieval_index_configurations`,
`ix_document_chunks_lexical_bm25`) — đã xác nhận đây là do migration của `develop` tạo bằng SQL thô,
không có model SQLAlchemy tương ứng trong `src/`, **không liên quan/không do Phase 3 gây ra** (grep
toàn bộ `src/` xác nhận không model nào tham chiếu 2 object này).

### 9.6 Bằng chứng chạy thật (sau merge)

```
$ pytest PM-test/ tests/ -q
74 passed, 1 failed in 10.62s
```
1 fail duy nhất (`tests/test_ai/test_policy_embedding_artifact.py`) do thiếu file artifact
`policy_category_labels.json` — cần chạy script sinh dữ liệu riêng của `develop`
(`scripts/generate_database_truth.py`), không liên quan Phase 3. **Toàn bộ test Phase 3 xanh.**

```
$ ruff check src/ PM-test/
All checks passed!
```

Curl thật vào Docker backend đã rebuild (project test `MERGEEVID`, project_id=845 — đã xoá mềm sau
khi lấy bằng chứng):

```json
// Upload lần 1
{ "document_id": 138, "latest_version": {
    "version_no": "1", "revision_no": 1, "status": "PROCESSING" } }
// Upload lần 2 (cùng category) — version mới của ĐÚNG document cũ
{ "document_id": 138, "latest_version": {
    "version_no": "2", "revision_no": 2, "status": "PROCESSING" } }
```

Query DB trực tiếp xác nhận đúng `embedding_model_version='pending'` cho cả 2 version:

```
 version_id | version_no | revision_no | embedding_model_version |   status
------------+------------+-------------+--------------------------+------------
        152 | 1          |           1 | pending                  | PROCESSING
        153 | 2          |           2 | pending                  | PROCESSING
```

Frontend: `npx tsc --noEmit` sạch, `next build` thành công, restart `next start`,
`localhost:3000/product-manager` HTTP 200.

## 10. Cập nhật — đảo quyết định "1 category = 1 document" → "1 category nhiều document"

Sau mục 9, xem lại thấy Master Template (`TemplateTask`) vốn đã cho 1 category chứa nhiều task
(VD "Tìm hiểu công ty — 3 TASK") — quyết định trước đó ở Phase 3 (mỗi `(project, category)` chỉ
giữ đúng 1 `KnowledgeDocument`) đi ngược pattern này. Đã đảo lại theo
`docs/PM/Phase-3/plan-fix-multi-document-per-category.md` (đã duyệt): **1 category giờ chứa được
nhiều document**, khớp đúng cách Master Template vốn hoạt động.

### 10.1 Model — không migration, chỉ đổi khoá so khớp tầng service

Không có UNIQUE constraint nào trên `(project_id, document_category)` ở tầng DB — giới hạn cũ chỉ
là 1 dòng `WHERE` trong `_find_or_create_document` (`src/services/knowledge_document_service.py`).
Đổi khoá so khớp từ `(project_id, category)` sang `(project_id, category, title)`: title trùng →
version mới của đúng document cũ (không đổi); title khác → tạo document MỚI trong cùng category
(trước đây bị gộp/ghi đè vào document duy nhất).

### 10.2 Đã kiểm tra — Master Template và Phase 4 không bị ảnh hưởng

- **Master Template** (`TemplateTask`/`TaskCategory`, `CompanyCoreDrawer` chính sách): không sửa gì
  — cả 2 vốn đã đúng kiểu "1 category nhiều mục" từ trước giờ, không hề có giới hạn như Documents.
- **Phase 4** (`src/services/onboarding_plan_service.py`): đọc file thật, hiện chỉ có 2 hàm đọc
  (`get_plan_by_membership`, `list_plans_by_project`), chưa có logic sinh Candidate Plan từ
  `KnowledgeDocument` — quyết định "nhiều document/category" không phá gì ở đây.

### 10.3 File đã sửa

- Backend: `src/services/knowledge_document_service.py` (`_find_or_create_document`).
- Test: `PM-test/test_knowledge_documents_project.py` — đổi
  `test_upload_different_title_same_category_reuses_same_document` thành
  `test_upload_different_title_same_category_creates_new_document` (title khác → document khác,
  cùng category), thêm mới `test_upload_same_title_same_category_reuses_document_new_version`
  (title trùng vẫn tái sử dụng đúng document, chỉ tạo version mới — giữ hành vi cũ cho trường hợp
  này).
- Frontend: `DocumentsView.tsx` (card hiện đúng số lượng thật, bấm mở Drawer thay vì giả định ≤ 1
  document), `CategoryDocumentsDrawer.tsx` (mới — liệt kê toàn bộ document trong 1 category, cùng
  pattern `CategoryTaskDrawer` bên Master Template), `RepoScanWizard.tsx` (Coverage Report đổi radio
  → checkbox, PM tick được nhiều candidate/category, bỏ dòng "Bỏ qua nhóm này").

### 10.4 Bằng chứng — test tự động

```
$ pytest PM-test/test_knowledge_documents_project.py -v
test_upload_single_document_creates_processing_version PASSED
test_upload_second_version_stays_processing_no_auto_activate PASSED
test_upload_different_title_same_category_creates_new_document PASSED
test_upload_same_title_same_category_reuses_document_new_version PASSED
test_scan_sample_repo_excludes_junk_and_builds_coverage PASSED
5 passed in 9.39s

$ pytest PM-test/ -q            # toàn bộ PM-test, không riêng Documents
63 passed in 17.28s

$ pytest PM-test/ tests/ -q     # + suite chung (ruff/pytest CI job)
76 passed in 12.21s

$ ruff check src/ PM-test/
All checks passed!
```

### 10.5 Bằng chứng — chạy thật trên Docker (backend rebuild + curl + query DB trực tiếp)

Rebuild image (`docker compose build backend`) rồi recreate container (`docker compose up -d
backend`) để chạy đúng code mới — `/health` trả `{"status":"ok"}` sau khi container lên.

Tạo project test `EVID2` (project_id=894, đã dọn sạch sau khi lấy bằng chứng — xem cuối mục này),
upload 2 file **khác title, CÙNG category `CODEBASE_GUIDE`**:

```json
// Upload 1: title "A.md"
{ "document_id": 163, "document_category": "CODEBASE_GUIDE", "title": "A.md",
  "latest_version": { "revision_no": 1, "status": "PROCESSING" } }

// Upload 2: title "B.md" — CÙNG category, KHÁC title
{ "document_id": 164, "document_category": "CODEBASE_GUIDE", "title": "B.md",
  "latest_version": { "revision_no": 1, "status": "PROCESSING" } }
```

`document_id` khác nhau (163 ≠ 164) — đúng hành vi mới (trước đây upload 2 sẽ trả về CÙNG
`document_id=163`, chỉ tăng `revision_no`). Listing endpoint trả về đúng 2 document riêng biệt
cùng category. Query DB trực tiếp xác nhận lại:

```
$ docker exec p-040-db-1 psql -U app -d pgonboarding -c \
  "SELECT document_id, project_id, document_category, title, status \
   FROM knowledge_documents WHERE project_id=894 ORDER BY document_id;"

 document_id | project_id | document_category | title | status
-------------+------------+--------------------+-------+--------
         163 |        894 | CODEBASE_GUIDE    | A.md  | ACTIVE
         164 |        894 | CODEBASE_GUIDE    | B.md  | ACTIVE
(2 rows)
```

Sau khi lấy đủ bằng chứng, đã dọn sạch toàn bộ dữ liệu demo (`document_versions`,
`knowledge_documents`, chuỗi `onboarding_templates`/`template_versions`/`template_tasks`/
`task_dependencies` tự sinh kèm project test, và chính project `EVID2`) — verify lại bằng SQL
`SELECT` trả về 0 dòng ở cả 3 bảng liên quan trước khi kết thúc, không để sót data test trong DB
dùng chung (đúng bài học từ 2 lần rò rỉ data trước đó trong Phase 3).

### 10.6 Frontend — verify code, chưa có screenshot trình duyệt

`npx tsc --noEmit` sạch, `npx eslint` sạch (folder `documents/`), `npx prettier --check` sạch (sau
khi auto-format `RepoScanWizard.tsx`), `npm run build` (Next.js Turbopack) thành công — 13 route
build tĩnh không lỗi. Dev server (`npm run dev`) chạy lại, `curl localhost:3000/product-manager`
trả HTTP 200 đúng `<title>`.

**Giới hạn thành thật**: môi trường này không có sẵn công cụ browser headless (`chromium-cli`/
Playwright) để tự chụp screenshot click-qua-click Drawer mới — đã verify bằng code (tsc/eslint/
build xanh) + bằng chứng API/DB thật ở mục 10.5 (chứng minh đúng cơ chế multi-document phía sau
UI dùng), nhưng CHƯA có ảnh chụp màn hình thao tác UI thật. Nên tự tay bấm thử "Quét repository"
với nhiều file cùng nhóm + mở Drawer 1 category để xác nhận UI hiển thị đúng trước khi coi Phase
3 phần này là xong hoàn toàn.
