# Plan: Phase 3 — Project Knowledge / Documents (owner-docs) + UC-04 Repo Scan & Coverage Report

> **Cập nhật sau khi merge `develop`**: nhánh `develop` (pipeline embedding POLICY — BGE-M3,
> ParadeDB) đổi schema `DocumentVersion` (`version_no` từ `int` → `str`, thêm `revision_no`/
> `embedding_model_version` bắt buộc). Đã điều chỉnh code Phase 3 khớp lại, không đổi ý nghĩa
> nghiệp vụ nào ở plan này (chỉ đổi cách lưu số thứ tự version trong DB) — xem đầy đủ diễn biến +
> bằng chứng ở `report-phase3.md` mục 9.
>
> **Cập nhật — đảo quyết định "1 category = 1 document"**: quyết định ban đầu (mỗi
> `(project, category)` chỉ giữ đúng 1 `KnowledgeDocument`) đã bị đảo lại thành **1 category chứa
> được nhiều document**, khớp đúng pattern Master Template (`TemplateTask`) vốn đã dùng từ đầu. Xem
> `docs/PM/Phase-3/plan-fix-multi-document-per-category.md` (plan đã duyệt) và `report-phase3.md`
> mục 10 (bằng chứng đầy đủ).

## Context

Phase 2 (Master Template 5-category + Company Core) đã xong, đã chạy Docker, đã test — không liên
quan tới plan này. Phase 3 là 1 task độc lập, có thể làm song song Phase 2 nếu có 2 người, theo
đúng `docs/PM/plan-pm.md`. PM yêu cầu 2 việc:

1. **Trước khi code**: viết plan đầy đủ, lưu thành file `.md` thật trong repo tại
   `docs/PM/Phase-3/` (file này), có test plan + kế hoạch tìm bằng chứng, để PM đọc và duyệt trước
   khi code bất kỳ dòng nào.
2. **Sau khi PM duyệt**: code Phase 3 backend (CRUD `KnowledgeDocument`/`DocumentVersion` thật +
   upload file + INV2) và luồng UC-04 (PM upload ZIP repo → scanner quét file tài liệu ứng viên →
   đề xuất category → Coverage Report (FOUND/MISSING/UNCLASSIFIED/DUPLICATE_OR_STALE) → PM sửa/chọn
   → Approve & Import), cộng với 1 sample repo code thật đặt ở `docs/PM/Phase-3/` để PM tự tay
   import thử qua UI.

Luồng UC-04 PM đặc tả gần khớp 100% với `BO_06_CLAUDE_PROJECT_SOURCE_OF_TRUTH.md` §14/§17 và
`docs/PM/plan-pm.md` (đã đọc lại nguyên văn, xác nhận khớp). Plan này hình thức hoá lại thành task
cụ thể + chỉ rõ vài chỗ cần quyết định (đánh dấu **Quyết định** bên dưới) vì SoT có 1-2 điểm không
khớp 100% với hạ tầng hiện có (chưa có worker async TV3, chưa có hệ thống đăng nhập nên chưa thể ký
"signed URL sau khi kiểm tra quyền").

## Đã khảo sát — hiện trạng thật (không phải giả định)

- **Model đã có sẵn, khớp schema mong muốn, KHÔNG cần sửa**: `src/model/knowledge_document.py`
  (`KnowledgeDocument`), `src/model/document_version.py` (`DocumentVersion`, đã có unique index
  `postgresql_where="status='ACTIVE'"` — **INV2 đã được enforce ở DB bằng deferred constraint
  trigger** `trg_document_versions_one_active`/`trg_knowledge_documents_one_active`, xem migration
  `a1b2c3d4e5f6_add_sync_fields_and_schema_invariants.py`), `src/model/document_chunk.py` (pgvector
  `VECTOR(1536)` + HNSW index — bảng rỗng, thuộc TV3, KHÔNG đụng vào).
- **`DocumentCategory`** (`src/model/enums.py`) đã đúng: `OVERVIEW, ARCHITECTURE, SETUP,
  ACCESS_SECURITY, CODEBASE_GUIDE, CONVENTION, FIRST_TASK` — 5 giá trị đầu khớp 5 category "project"
  đã chốt ở Phase 2 (`DEFERRED_TASK_CATEGORIES` cùng logic). UI Phase 3 chỉ dùng **5 giá trị đầu**,
  2 giá trị cuối (`CONVENTION`, `FIRST_TASK`) coi là mở rộng làm sau — nhất quán với quyết định
  Master Template.
- **Backend hiện tại chỉ là khung**: `knowledge_document_service.py`/`router.py` chỉ có 1 hàm đọc
  policy (`GET /knowledge-documents/policy`, không đổi, giữ nguyên). `document_version_router.py`,
  `document_chunk_router.py` là TODO thuần docstring, chưa có code. Không có DTO nào cho
  `DocumentVersion`, không có request DTO nào cho document. Không có endpoint upload file nào từng
  tồn tại trong codebase (không có pattern `UploadFile`/multipart để tham khảo — đây sẽ là cái đầu
  tiên).
- **Cloudinary**: `scripts/upload_sample_docs_to_cloudinary.py` có sẵn logic dùng thẳng
  `cloudinary.uploader.upload(path, resource_type="raw", folder=f"knowledge-documents/{folder}",
  public_id=..., overwrite=True)` trả `secure_url` (public). Không có storage-service abstraction
  nào để tái dùng — sẽ tách thành `src/services/storage_service.py` mới, nhận bytes thay vì Path.
- **TV3 (extract/chunk/embedding) chưa build gì cả** — chỉ có schema (`document_chunks` rỗng),
  không có thư viện đọc PDF/DOCX, không có embeddings client. Đây rõ ràng KHÔNG thuộc Phase 3.
- **Frontend**: `PmShell.tsx` đã có sẵn nav `{ key: "docs", label: "Tài liệu dự án", icon: "doc",
  enabled: false }` — chỉ cần bật `enabled: true` và nối route. `DocumentPreviewModal.tsx` (vừa
  làm xong cho Company Core) tái dùng được thẳng để xem tài liệu dự án. `api.ts` chưa có helper
  multipart/FormData — cần thêm mới. Có 1 stub `frontend/src/app/documents/page.tsx` +
  `features/documents/` (`.gitkeep` rỗng) — đây là placeholder generic không liên quan tới PM
  shell, **không đụng vào**, Phase 3 UI sẽ nằm trong `features/project-management/components/documents/`
  giống pattern `template/`.
- **AI classification — đổi sang DeepSeek (PM yêu cầu, đã có sẵn key riêng)**: không dùng
  `get_llm()` hiện tại (đang trỏ OpenAI, dùng cho tính năng Chat khác — không đụng vào để tránh ảnh
  hưởng tính năng đó). Thêm hàm riêng `get_classifier_llm()` trong `src/services/llm.py`, dùng
  `langchain_openai.ChatOpenAI(model="deepseek-chat", api_key=settings.deepseek_api_key,
  base_url="https://api.deepseek.com", temperature=0)` — DeepSeek expose API **tương thích chuẩn
  OpenAI** nên tái dùng thẳng `ChatOpenAI`, chỉ đổi `base_url`/`model`, không cần SDK riêng.
  `temperature=0` vì đây là tác vụ phân loại (muốn ổn định, không cần sáng tạo).
  Thêm field mới `deepseek_api_key: str = ""` vào `Settings` (`src/config.py`). Key thật PM đã cung
  cấp sẽ được điền vào `.env` cục bộ (**đã xác nhận `.env` nằm trong `.gitignore`, không commit lên
  git** — không ghi giá trị key thật vào bất kỳ file nào sẽ commit, kể cả file plan/report này).
  **Chi phí token**: rất thấp — (1) chỉ gọi AI cho file rule không xác định được (thường chỉ vài
  file/lượt quét, không phải mọi file), (2) prompt ngắn (tên file + ~2000 ký tự đầu nội dung, khoảng
  500-700 token), output ngắn (chỉ trả category + % tin cậy, vài chục token), (3) giá DeepSeek rẻ
  hơn nhiều so với OpenAI cho cùng chất lượng phân loại đơn giản này — tổng chi phí 1 lượt quét
  thường dưới 1 cent kể cả khi có nhiều file UNCLASSIFIED.

## Quyết định cần chốt (đã chọn hướng hợp lý nhất, nói lại nếu muốn khác)

1. **DocumentVersion sau khi import → ACTIVE ngay hay PROCESSING chờ TV3?**
   **Đã phát hiện lúc code**: trigger DB có sẵn từ trước (migration
   `a1b2c3d4e5f6_add_sync_fields_and_schema_invariants.py`, hàm
   `enforce_one_active_document_version()`, **không phải do Phase 3 tạo**) ép **đúng 1** (`<> 1` →
   lỗi) ACTIVE version/document tại mọi thời điểm commit — chặn cả trạng thái hợp lệ "document vừa
   tạo, version còn PROCESSING, chưa có ACTIVE nào" mà thiết kế gốc SoT §14 mô tả (TV3 xử lý
   PROCESSING → ACTIVE ở 1 transaction khác, sau này — chắc chắn có lúc document tồn tại mà chưa
   ACTIVE). Đã bàn với Mai Anh (phụ trách TV3/embedding) — xác nhận đây là bug của trigger (lẽ ra
   phải là "tối đa 1", không phải "đúng 1"), **đồng ý sửa trigger**.

   **Chốt cuối cùng**: giữ đúng luồng gốc — PM import xong, version tạo ở `PROCESSING`, Phase 3
   không tự activate. TV3 lấy version đang `PROCESSING`, chạy extract → chunk → embedding, xong thì
   gọi `activate_version()` (đã viết sẵn, INV2-safe) để tự chuyển `ACTIVE` (archive bản ACTIVE cũ
   trong cùng transaction). Lỗi thì set `FAILED`, bản ACTIVE cũ giữ nguyên.
   **Migration mới** `9e2a4d6533a4_relax_one_active_document_version_.py`: sửa
   `enforce_one_active_document_version()` từ `IF v_active_count <> 1` thành
   `IF v_active_count > 1` — đúng lại ý nghĩa "tối đa 1 ACTIVE", cho phép 0 (document mới tạo/đang
   PROCESSING). Đã chạy `alembic upgrade head` + `alembic check` sạch. Đây là sửa trigger/schema,
   không đụng file model `.py` nào (không vi phạm "không sửa model" — chỉ sửa đúng hàm trigger có
   bug, đã được team xác nhận).
2. **Cloudinary public URL vs signed URL nội bộ**: SoT nói không dùng public URL cho tài liệu nội
   bộ, nhưng dự án **chưa có hệ thống đăng nhập/phân quyền** (quyết định đã chốt từ Phase 2 — không
   thêm authorization). Không thể "ký URL sau khi kiểm tra quyền" khi chưa có ai để kiểm tra quyền.
   **Chọn**: giữ nguyên pattern hiện có (Cloudinary `resource_type="raw"`, public secure_url,
   giống Company Core đang chạy) cho MVP, ghi rõ trong report đây là gap đã biết, sẽ làm signed URL
   khi có Auth (Phase sau).
3. **Nơi lưu tạm file ZIP giữa bước "scan" và bước "PM duyệt & Approve & Import"**: 2 bước là 2
   request riêng (đúng theo luồng PM mô tả: xem Coverage Report trước, sửa category, rồi mới bấm
   Approve). Cần giữ file đã giải nén ở đâu đó giữa 2 request. **Chọn**: thư mục tạm cục bộ
   `var/scan-sessions/{scan_session_id}/` trên server (KHÔNG lưu DB, KHÔNG lưu Cloudinary cho tới
   khi PM approve), theo dõi bằng dict in-memory `{session_id: {expires_at, candidates}}` trong
   process backend (dự án chạy 1 instance backend — đủ cho MVP/demo). Tự dọn sau 30 phút không
   approve, và dọn ngay sau khi import xong hoặc PM huỷ.
4. **File đổi tên / file bị xoá khỏi repo (re-scan sau này)**: nằm trong SoT §14 nhưng là luồng
   "cập nhật repository lần 2" — phức tạp hơn nhiều (cần fuzzy-match tên cũ/mới). **Chọn**: MVP chỉ
   làm phần so khớp theo `(project_id, document_category)` khi 1 candidate trùng với 1
   `KnowledgeDocument` đã có → tự động coi là version mới của đúng document đó (không tạo document
   trùng). Rename-mapping thông minh + báo "file bị xoá" đầy đủ → ghi là **mở rộng làm sau**, không
   làm trong Phase 3 này.
5. **KHÔNG sửa model** (yêu cầu mới của PM — chốt lại, không thương lượng): bỏ hẳn ý định thêm cột
   `source_repository_path` vào `knowledge_documents` (đã bỏ khỏi plan). Đường dẫn file trong repo
   (`relative_path`) chỉ tồn tại tạm thời trong `CoverageReport`/scan session (in-memory, không lưu
   DB) để PM xem lúc duyệt, và được ghép thẳng vào `title` khi import (ví dụ title =
   `"docs/setup/local-setup.md"` hoặc tên file gọn hơn PM sửa tay ở bước duyệt) — không cần cột
   riêng. Mỗi (project, category) chỉ giữ đúng 1 document — việc so khớp version mới của tài liệu
   cũ dùng `(project_id, document_category)` (không cần title), title tự cập nhật theo file mới. Model `KnowledgeDocument`, `DocumentVersion`, `DocumentChunk`,
   `src/model/enums.py` (file `.py`) — **giữ nguyên 100%, không sửa file model nào**. Ngoại lệ duy
   nhất: migration sửa hàm trigger `enforce_one_active_document_version()` (Quyết định #1) — đây là
   sửa 1 hàm PL/pgSQL có bug tại DB, không đụng bất kỳ file model `.py`/cột/bảng nào, đã được team
   (Mai Anh) xác nhận trước khi làm.

## Việc sẽ làm — Backend

### B1. `src/services/storage_service.py` (mới)
- `upload_document_bytes(content: bytes, project_slug: str, filename: str) -> str` — tách logic
  Cloudinary từ `scripts/upload_sample_docs_to_cloudinary.py`, nhận bytes thay vì Path, cùng
  `resource_type="raw", folder=f"knowledge-documents/{project_slug}"`.

### B2. `src/services/repo_scanner_service.py` (mới) — lõi UC-04

**Kỹ thuật quét (đã đổi theo yêu cầu PM — không bắt PM tự nén ZIP nữa)**: PM chọn thẳng **folder
dự án** trên máy (không cần tự tay nén file). Trình duyệt hỗ trợ chọn cả thư mục qua
`<input type="file" webkitdirectory multiple>` (Chrome/Edge — trình duyệt PM dùng thực tế), mỗi
file trong thư mục con vẫn giữ đường dẫn tương đối qua `file.webkitRelativePath`. FE gửi thẳng toàn
bộ file này lên BE trong 1 request multipart (`FormData`, mỗi file append kèm
`file.webkitRelativePath` làm tên) — **không zip ở client, không unzip ở server** — bỏ hẳn bước
`extract_zip_safely`/zip-slip/zip-bomb vì không còn xử lý file `.zip` nữa, đơn giản hoá đúng như PM
muốn. BE nhận `files: list[UploadFile]`, lấy `file.filename` làm đường dẫn tương đối (browser đã tự
đặt đúng dạng `thư-mục-con/tên-file.md`), lưu trực tiếp từng file được lọc hợp lệ vào thư mục scan
session tạm — không có bước "giải nén" nào cả.

**Chọn folder to/nặng (nhiều node_modules, .git, build output, ảnh...) vẫn ổn, vì lọc diễn ra ở
CLIENT trước khi upload, không phải upload hết rồi mới lọc**: `input.files` (`FileList`) khi chọn
folder trả về metadata (tên, đường dẫn, dung lượng) của **toàn bộ** cây thư mục ngay lập tức, không
tốn chi phí đọc nội dung. FE duyệt qua `FileList` này, áp đúng bộ lọc đuôi file + tên thư mục loại
trừ (giống hệt danh sách phía server, xem bên dưới) **trước khi** gọi `formData.append(...)` — chỉ
những file thật sự khớp (`.md/.txt/.pdf/.docx`, không nằm trong `.git/node_modules/dist/build/.next/
__pycache__/.venv`) mới được đọc bytes và đẩy lên mạng. Vì vậy PM chọn nguyên repo hàng nghìn file/
vài trăm MB (kể cả `node_modules` bên trong) vẫn nhẹ nhàng — phần thật sự gửi lên server chỉ là vài
chục file tài liệu, thường không quá vài MB.
BE vẫn tự lọc lại y hệt (không tin tưởng tuyệt đối client) + giữ 2 chốt an toàn: tổng dung lượng
request tối đa (50MB) và số file tối đa (500) sau lọc — vượt thì trả lỗi 413, phòng trường hợp
client bị qua mặt hoặc lỗi.
- Bộ lọc file ứng viên: chỉ nhận đuôi `.md .txt .pdf .docx`; bỏ qua thư mục
  `.git node_modules dist build .next __pycache__ .venv`; bỏ qua file nhạy cảm theo tên
  (`.env` trừ `.env.example`, `*.pem`, `*.key`, tên chứa `secret`/`token`/`password`).
- Phân loại rule-based theo (a) path segment keyword, (b) filename keyword, (c) heading/keyword
  trong ~2000 ký tự đầu nội dung — map vào đúng 5 `DocumentCategory` đầu. Không xác định được →
  gọi `get_classifier_llm()` (DeepSeek, xem mục khảo sát ở trên) 1 lần (prompt ngắn: filename +
  đoạn đầu nội dung → chọn 1 trong 5 category hoặc UNCLASSIFIED + confidence) — lỗi/timeout thì rơi
  về UNCLASSIFIED, không chặn luồng.
- Trùng lặp: so checksum SHA-256 candidate với checksum các `DocumentVersion` đang ACTIVE trong
  project → `DUPLICATE_OR_STALE` (đã có, bỏ qua). 2 candidate cùng scan trùng stem tên
  (`old-setup.md`/`setup.md`) → cả 2 gắn `DUPLICATE_OR_STALE`, PM tự chọn bản đúng.
- So khớp `document_category` với `KnowledgeDocument` đã có trong project → nếu trùng, đánh dấu
  "sẽ tạo version mới của tài liệu đã có" thay vì tài liệu mới (mỗi category chỉ 1 document/project).
- Build `CoverageReport`: liệt kê đúng 5 category bắt buộc, đánh dấu `MISSING` category nào không
  có candidate nào khớp (kể cả sau khi PM sửa tay — coverage tính lại ở FE theo state hiện tại).

### B3. `src/services/document_version_service.py` (mới)
- `create_processing_version(db, document_id, storage_uri, checksum, version_no)`: tạo
  `DocumentVersion(status=PROCESSING)` — Phase 3 dừng ở đây, không tự activate.
- `activate_version(db, document_id, version_id)`: trong 1 transaction — set version khác đang
  ACTIVE của cùng document (nếu có) → ARCHIVED, `await db.flush()` (dùng lại đúng pattern đã chứng
  minh ăn ở Phase 2 `template_version_service.approve_version`, tránh lỗi flush-order với
  constraint), rồi set version chỉ định → ACTIVE. **Viết sẵn + test cho TV3 dùng, Phase 3 không tự
  gọi hàm này ở bất kỳ endpoint nào.**

### B4. `src/services/knowledge_document_service.py` (mở rộng, không xoá hàm cũ)
- `list_project_documents(db, project_id)`.
- `import_single_file(db, project_id, category, title, content)`: tính checksum, upload Cloudinary
  qua storage_service, tìm/tạo `KnowledgeDocument` (match theo `category` trong cùng project —
  mỗi category chỉ 1 document, else tạo mới), gọi `create_processing_version` với `version_no`
  tăng dần. Dừng ở
  `PROCESSING`, không gọi `activate_version`.
- `import_scan_selection(db, project_id, scan_session_id, selections)`: đọc file từ thư mục tạm
  theo `scan_session_id`, lặp qua từng candidate PM đã duyệt, gọi `import_single_file` cho mỗi cái,
  dọn thư mục tạm.

### B5. Router mới `src/api/routers/knowledge_document_router.py` (thêm route, giữ nguyên route cũ)
Tất cả dưới prefix mới `/knowledge-documents/pm` (đồng bộ pattern `_pm` các router khác):
- `GET /knowledge-documents/pm/projects/{project_id}` — danh sách tài liệu dự án + version ACTIVE.
- `POST /knowledge-documents/pm/projects/{project_id}/upload` — multipart, 1 file + category, cho
  ca "MISSING thì upload bù" hoặc tài liệu ngoài repo.
- `POST /knowledge-documents/pm/projects/{project_id}/scan` — multipart nhiều file (PM chọn thẳng
  folder, mỗi file kèm đường dẫn tương đối qua `webkitRelativePath`, không phải file `.zip`) → trả
  về `{scan_session_id, candidates[], missing_categories[]}`. Không ghi DB.
- `POST /knowledge-documents/pm/projects/{project_id}/scan/{scan_session_id}/import` — body JSON
  danh sách candidate PM đã duyệt (kèm category có thể đã sửa) → ghi DB thật + Cloudinary.

### B6. DTO mới
- `src/dto/response/document_version_response_dto.py`, mở rộng
  `knowledge_document_response_dto.py` thêm `ProjectDocumentResponseDTO` (khác DTO policy hiện có).
- `src/dto/response/repo_scan_response_dto.py`: `ScanCandidateDTO`, `CoverageReportDTO`.
- `src/dto/request/knowledge_document_request_dto.py`: `ImportScanSelectionRequestDTO`.

### B7. Test — `PM-test/`
- `test_repo_scanner.py`: test trực tiếp service scanner với vài file fixture nhỏ tự tạo trong test
  (dict `{relative_path: content}`, không phụ thuộc sample-repo ở bước D) — assert đúng category,
  đúng MISSING, đúng loại trừ `.git`/`.env`/file lớn, đúng DUPLICATE_OR_STALE.
- `test_knowledge_documents_project.py`: upload 1 file → version tạo đúng `PROCESSING` (không tự
  ACTIVE); upload version 2 cùng category/document → vẫn `PROCESSING`, không tự chuyển; scan+import
  end-to-end dùng sample-repo/ (bước D) qua API thật, assert mọi version import ra đều `PROCESSING`.
- `test_document_version_activation.py`: test riêng gọi thẳng `activate_version()` (không qua API,
  Phase 3 không có endpoint nào gọi nó) — activate version A, rồi activate version B của cùng
  document → xác nhận A tự chuyển ARCHIVED, chỉ B là ACTIVE (bằng chứng INV2 sau khi sửa trigger,
  query DB trực tiếp giống cách đã làm ở Phase 2 cho `template_versions`). Đây là hàm TV3 sẽ gọi
  thật sau này.

## Việc sẽ làm — Frontend

### F0. `PmShell.tsx`: bật `enabled: true` cho nav `docs`, nối route sang `DocumentsView` mới (tìm
đúng chỗ compose `PmShell` hiện tại, cùng chỗ đang nối `template`).

### F1. DTO
- `dto/responseDTO/document.response.ts`: `ProjectDocumentResponseDTO`, `DocumentVersionResponseDTO`.
- `dto/responseDTO/repoScan.response.ts`: `ScanCandidateDTO`, `CoverageReportDTO`.
- `dto/requestDTO/document.request.ts`: `ImportScanSelectionRequestDTO`.

### F2. `api.ts`
- Thêm helper `postMultipart` (FormData, không set `Content-Type` tay).
- `listProjectDocuments`, `uploadProjectDocument`, `scanRepository`, `importScanSelection`.
- `lib/api.ts` thêm `PM_KNOWLEDGE_DOCUMENTS_ENDPOINT`.

### F3. `components/documents/` (thư mục mới, theo đúng pattern `components/template/`)
- `DocumentsView.tsx` — trang chính: KPI (tổng tài liệu / đủ 5 nhóm hay thiếu), danh sách tài liệu
  theo 5 category (dùng lại style card/label/icon đã thống nhất ở `TaskFormModal` cho 5 category),
  nút "Quét repository" mở `RepoScanWizard`, nút "Tải lên tài liệu" mở `DocumentUploadModal` cho
  từng category đang MISSING.
- `RepoScanWizard.tsx` — modal nhiều bước (`PmModal size="wide"`, tái dùng stepper UI đã có ở
  `TaskFormModal.tsx`): (1) chọn **folder** dự án (input `webkitdirectory`, không phải chọn file
  ZIP), (2) đang quét, (3) bảng Coverage Report — mỗi candidate
  có checkbox chọn/bỏ, dropdown sửa category, badge trạng thái (FOUND/MISSING/UNCLASSIFIED/
  DUPLICATE_OR_STALE), (4) xác nhận → "Approve & Import".
- `DocumentUploadModal.tsx` — upload 1 file bù cho category MISSING.
- Tái dùng thẳng `ui/DocumentPreviewModal.tsx` đã có để PM xem lại tài liệu vừa import.

## Sample repo để test (đặt tại `docs/PM/Phase-3/`)

Tạo 1 project demo nhỏ nhưng có code thật (không phải file rỗng) + bộ tài liệu chuẩn, giữ nguyên
dạng **folder** tại `docs/PM/Phase-3/sample-repo/` (không cần nén `.zip` — đúng cơ chế "chọn folder"
ở trên, PM chọn thẳng thư mục này khi test) — dùng để PM import thử qua UI sau khi code xong:
- 1 app nhỏ thật (FastAPI "Todo API" — vài route, model, test) đủ để có cấu trúc thư mục thực tế.
- `README.md` (OVERVIEW), `docs/architecture/system-design.md` (ARCHITECTURE),
  `docs/setup/local-setup.md` (SETUP), `docs/access/security-guide.md` (ACCESS_SECURITY),
  `docs/codebase-guide.md` (CODEBASE_GUIDE) — đủ 5 nhóm bắt buộc để test coverage FOUND đầy đủ.
- Giữ TỐI GIẢN, chỉ đúng 2 case biên, mỗi case test đúng 1 tầng của cơ chế phân loại (không nhồi
  nhiều file nhiễu như bản đầu):
  - `notes-final.md` — path/tên không khớp, nhưng **nội dung** khớp SETUP → test tầng phân loại
    theo nội dung (tầng 3), không cần gọi AI.
  - `docs/adr/0001-single-service.md` (ADR bàn quyết định giữ 1 service duy nhất, viết như 1 ADR
    thật, cố tình không dùng từ khoá "architecture"/"kiến trúc" nào) — path/tên/nội dung **đều
    không khớp rule nào** → bắt buộc rơi xuống tầng cuối, gọi AI (DeepSeek) mới phân loại đúng
    được. Đã verify thật: AI trả về đúng `ARCHITECTURE`, confidence 0.95.
  - `.env` chứa secret giả + `.env.example` (cả 2 đều bị loại vì đuôi file không thuộc nhóm tài
    liệu `.md/.txt/.pdf/.docx` — giữ cả 2 để đối chứng, không phải vì `.env.example` "phải được
    quét"), `node_modules/fake-pkg/index.js` (bị bỏ qua theo thư mục loại trừ),
    `assets/demo-diagram.png` + `app.log` (bị loại theo đuôi file, không phải tài liệu).
  - *(Đã bỏ `old-setup.md`/`setup.md`/`CONTRIBUTING.md` khỏi bản đầu — quá nhiều file nhiễu không
    cần thiết so với mục đích demo, DUPLICATE_OR_STALE đã có test riêng đầy đủ ở
    `PM-test/test_repo_scanner.py`, không cần lặp lại trong fixture thật.)*
  - Test tự động (`PM-test/test_knowledge_documents_project.py`) **không** đưa file ADR vào danh
    sách quét — giữ test xác định (deterministic), không phụ thuộc mạng/API key khi chạy CI/local.
    File ADR chỉ dùng để PM tự tay test qua UI thật, nơi gọi AI là đúng ý nghĩa tính năng.
- **Việc tạo sample-repo này KHÔNG phải "code sản phẩm"** — đây là dữ liệu test/fixture. Sẽ làm
  ngay sau khi PM duyệt plan này, làm trước tiên, độc lập, không phụ thuộc code backend/frontend.

## Test + bằng chứng + báo cáo (sau khi có code)

- `pytest PM-test/ tests/ -v` xanh hết, `alembic check` sạch, `ruff check`, `tsc --noEmit`,
  `eslint --max-warnings=0`, `prettier --check`, `next build`.
- Bằng chứng INV2: query SQL trực tiếp `SELECT document_id, COUNT(*) FROM document_versions WHERE
  status='ACTIVE' GROUP BY document_id HAVING COUNT(*) > 1` → phải rỗng, chạy sau khi gọi
  `activate_version()` 2 lần liên tiếp cho cùng 1 document (giả lập đúng việc TV3 sẽ làm) để chứng
  minh trigger (đã sửa) + hàm hoạt động đúng.
- Bằng chứng UC-04: curl/log thật của luồng scan thư mục `sample-repo/` (multipart nhiều file) →
  xem JSON Coverage Report → gọi import → query DB xác nhận đúng số `KnowledgeDocument`/
  `DocumentVersion` được tạo, đúng file bị loại (`.env`, `node_modules/*`) không xuất hiện trong
  candidate list.
- `docker compose up -d --build backend`, restart frontend `next start`, verify UI sống thật (mở
  DocumentsView, chọn folder `sample-repo/`, xem Coverage Report, approve, xem lại tài liệu qua
  `DocumentPreviewModal`).
- Viết `docs/PM/Phase-3/report-phase3.md` theo đúng format bằng chứng như
  `docs/PM/Phase-2/report-phase2.md` (đã có sẵn làm mẫu).

## Không làm trong Phase 3 này (ghi rõ để không lấn phạm vi)

- Không code TV3 (extract/chunk/embedding thật, `document_chunks` vẫn rỗng) — đúng theo SoT §17.4
  giao cho phần khác.
- Không thêm authorization/đăng nhập (giữ quyết định cũ).
- Không làm signed-URL Cloudinary thật (cần Auth trước — ghi nhận là gap đã biết).
- Không làm rename-mapping thông minh + báo "file bị xoá khỏi repo" ở lần scan sau — để lại làm
  sau.
- Không hỗ trợ kết nối Git URL trực tiếp (OAuth GitHub/GitLab) — chỉ ZIP, đúng phạm vi MVP PM ghi.

## Thứ tự thực hiện sau khi duyệt

1. ~~Lưu plan này thành `docs/PM/Phase-3/plan-phase3-documents.md`~~ (file này — đã lưu, đang chờ
   PM duyệt).
2. Tạo sample-repo + zip tại `docs/PM/Phase-3/` (không phụ thuộc code, làm trước, để PM xem trước
   luôn nếu muốn).
3. Backend B1 → B7 lần lượt, chạy test sau mỗi bước lớn. 1 migration duy nhất: sửa hàm trigger
   `enforce_one_active_document_version()` (không đụng model `.py`/cột/bảng nào).
4. Frontend F0 → F3.
5. Docker rebuild + verify sống + viết report kèm bằng chứng.
