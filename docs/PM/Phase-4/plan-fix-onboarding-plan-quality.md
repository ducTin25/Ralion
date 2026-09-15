# Plan: Sửa 6 lỗi phát hiện khi PM test thật tính năng Onboarding Plan (GADGETHUB)

> Chưa code — plan chuẩn. TV3 (Mai Anh) đã push code chunk PROJECT lên `develop`; `git pull` về bị
> conflict 24 file (xem mục 0). Phải resolve xong mục 0 trước, rồi mới code theo đúng thứ tự
> 3.1 → 3.7. Nối tiếp `plan-fix-reference-plan-reuse.md` (đã code xong, giữ nguyên) — không thay
> thế bản đó.

## 0. Resolve merge conflict với `develop` (làm TRƯỚC 3.1-3.7)

`git pull origin develop` đang dừng ở trạng thái merge với 24 file conflict. Đã soi từng file, quy
về đúng 4 nhóm theo người/nguyên nhân — quy tắc resolve cụ thể từng nhóm (không có tính năng nào bị
mất, vì không có 2 bên nào thực sự loại trừ nhau):

**Nhóm A — 11 file là code CŨ của chính TranAnhThu** (đã merge vào `develop` trước, nhánh làm việc
hiện tại đã đi xa hơn — quyết định "1 category nhiều document" chưa merge ngược): `PM-test/conftest.py`,
`PM-test/test_knowledge_documents_project.py`, `docs/PM/Phase-3/plan-phase3-documents.md`,
`docs/PM/Phase-3/report-phase3.md`, `DocumentsView.tsx`, `RepoScanWizard.tsx`+`.module.scss`,
`MembersView.tsx`, `CompanyCoreDrawer.tsx`+`.module.scss`, `DocumentPreviewModal.tsx`.
→ **Giữ nguyên HEAD (`git checkout --ours <file>`)** — an toàn tuyệt đối, bản kia chỉ là chính mình
2 ngày trước, không mất tính năng của ai.

**Nhóm B — 5 file của Mai Anh (TV3)**: `document_version_service.py`, `knowledge_document_service.py`,
`llm.py`, `config.py`, `routers/__init__.py`.
- `config.py`, `llm.py`, `routers/__init__.py`: cả 2 bên chỉ **thêm** setting/route khác nhau, không
  đụng cùng chỗ → merge cơ học, giữ CẢ HAI khối (Langfuse/DeepSeek/plan_generation_use_ai của mình +
  OpenRouter/BGE-M3/chat router của Mai Anh).
- `document_version_service.py`: lấy `create_active_version()` của Mai Anh (bỏ PROCESSING, tạo
  ACTIVE ngay) — đúng hướng sửa gốc #1, không mất gì của mình vì hàm `activate_version()` không đổi.
- `knowledge_document_service.py`: lấy `create_active_version()` (thay `create_processing_version()`)
  nhưng **`_find_or_create_document()` GIỮ bản của mình** (nhiều document/category) — đây là chỗ
  DUY NHẤT trong nhóm B phải ghép tay 2 phần từ 2 bên, không "chọn nguyên 1 bên".

**Nhóm C — 7 file của ducTin25** (auth/routing PM+Engineer): `PmShell.tsx`, `product-manager/page.tsx`,
`api.ts` (project-management), `lib/api.ts`, `knowledge_document_router.py`,
`knowledge_document_request_dto.py`, `PM-test/test_onboarding_plans.py`.
- Đây là nhóm rủi ro nhất: cả 2 bên cùng sửa SÂU vào cùng file (không chỉ thêm dòng). Phải đọc từng
  hunk, giữ auth-gate/routing-theo-context của ducTin25 làm lớp NGOÀI, giữ tab "Onboarding Plan" +
  state Phase 4 của mình làm lớp TRONG — không được xoá bên nào.
- `knowledge_document_request_dto.py`: MERGE_HEAD bỏ field `created_by_user_id` khỏi DTO (chuyển
  sang lấy từ session sau khi có auth) — hợp lý hơn (không tin client gửi user id), nên lấy theo
  MERGE_HEAD ở điểm này, nhưng phải kiểm tra `knowledge_document_router.py`/service có logic lấy
  user id từ session/token chưa, nếu chưa có sẵn thì tạm giữ field cũ để không vỡ luồng upload.
- `test_onboarding_plans.py`: lấy `_create_project(..., admin_id)` động của MERGE_HEAD thay vì
  hardcode `19` — an toàn hơn, không mất test nào.

**Nhóm D — 1 file của Vương Đức Thoại**: `storage_service.py` — gắn với nhóm A (multi-document):
giữ `overwrite=True, public_id=filename` (bản mình) vì khớp đúng logic "title trùng → cùng document,
ghi đè file cũ" đã chốt ở nhóm A. Không lấy `unique_filename=True` của họ vì sẽ phá vỡ giả định title
ổn định của `_find_or_create_document`.

**Sau khi resolve xong**: `git add` toàn bộ, `git commit` (giữ message merge mặc định), rồi chạy
`pytest PM-test/ tests/ -q` NGAY để bắt lỗi resolve sai sớm nhất có thể — trước khi đụng tới 3.1-3.7.

**Lưu ý quan trọng — mục 3.1 cũ cần đọc lại sau khi resolve**: sau merge, tài liệu PROJECT sẽ có
`DocumentVersion.status = ACTIVE` ngay khi upload (nhờ nhóm B), nhưng **vẫn CHƯA có dòng nào trong
`document_chunks`** — module `src/modules/knowledge/ingestion/chunkers.py` Mai Anh push lên là thuật
toán chunk theo cấu trúc (đã test), nhưng CHƯA được gọi ở đâu trong luồng import cả (đã grep xác
nhận). Cần hỏi lại Mai Anh ai nối bước này, hoặc tự nối nếu cô ấy không làm tiếp — xem lại mục 3.1
sau khi resolve xong mục 0.

## 1. Context

PM vừa chạy thử tính năng "Lộ trình chuẩn" vừa code xong trên project GADGETHUB (ảnh chụp màn hình
thật) và phát hiện 6 vấn đề thật, không phải ý kiến chủ quan:

1. **Nội dung bịa ra dù không có tài liệu nguồn.** Task "Cài đặt công cụ phát triển..." hiện
   "TÀI LIỆU NGUỒN (0)" nhưng phần "Mục tiêu"/"Các bước thực hiện" vẫn đầy đủ như thể có nguồn thật.
2. **PM tự suy luận đúng nguyên nhân**: tài liệu GADGETHUB đứng "ACTIVE" ở cột `KnowledgeDocument`
   nhưng `DocumentVersion` kẹt ở `PROCESSING` mãi mãi — kiểm chứng bằng SQL thật, đúng vậy.
3. **Thiếu phần "Tìm hiểu công ty"** trong Onboarding Plan thật — Master Template có hiển thị khối
   này (đọc thẳng 19 tài liệu POLICY) nhưng plan sinh ra cho kỹ sư lại không có nhóm task nào tương
   ứng, dù PM đúng: 1 lộ trình chuẩn phải có 1 phần công ty + 5 phần dự án.
4. **Không cho PM thêm/xoá task** trên trang Lộ trình chuẩn — chỉ sửa được nội dung task có sẵn.
5. **Nguồn trích dẫn dồn hết xuống cuối** thay vì gắn ngay tại đoạn nội dung dùng nguồn đó.
6. **Markdown hiển thị sai** — danh sách đánh số (`1. 2. 3.`) và checkbox (`- [ ]`) trong nội dung AI
   sinh ra bị in nguyên văn thành 1 đoạn văn dính cục, không xuống dòng/không có checkbox thật.

## 2. Nguyên nhân gốc (đã đọc code + query DB thật, không đoán)

### 2a. Vì sao luôn "Thiếu nguồn" — 2 lỗi cộng dồn

- `src/services/knowledge_document_service.py::_import_one()` gọi
  `document_version_service.create_processing_version()` rồi **dừng lại** — không có nơi nào gọi
  `activate_version()` cho tài liệu PROJECT (khác hẳn `policy_ingestion.py` dòng 166-169, tự
  activate ngay sau khi ghi chunk). Comment đầu file `document_version_service.py` xác nhận: "Phase 3
  chỉ tạo version ở PROCESSING... `activate_version()` viết sẵn cho TV3 gọi khi worker embedding thật
  xử lý xong — Phase 3 không gọi hàm này ở đâu cả". Nhưng TV3 chưa làm phần đó, nên tài liệu PROJECT
  **kẹt PROCESSING vĩnh viễn trong thực tế** dù `steps.py::_active_documents()` lọc cứng
  `DocumentVersion.status == ACTIVE`.
- Dù có activate, `search_project_docs()` (bm25_search) tìm trong bảng `document_chunks` — bảng này
  **0 dòng cho mọi tài liệu PROJECT** (kiểm tra SQL thật: version 222-234 đều 0 chunk). Chỉ có
  `policy_ingestion.py` tạo `DocumentChunk` cho POLICY; tài liệu PROJECT chưa từng được chunk.
- Vì `hits` luôn rỗng, `generate_ai_content()` (content_llm.py dòng 200-202) rơi vào baseline **im
  lặng**: `generate_baseline_content()` luôn điền `instruction_template`/`objective` của TemplateTask
  (nội dung PM soạn sẵn trong Master Template) bất kể có nguồn hay không, chỉ thêm 1 dòng cảnh báo
  nhỏ `NO_SOURCE_NOTICE` — đây chính là điều PM thấy "có nội dung mà không có tài liệu".

### 2b. Vì sao thiếu "Tìm hiểu công ty"

`TaskCategory` enum (`src/model/enums.py`) chỉ có 5 giá trị dùng thật + 3 giá trị hoãn
(`CONVENTION/FIRST_TASK/FIRST_PR`) — **không có category nào cho company policy**. Khối "Tìm hiểu
công ty" ở Master Template (`TemplateView.tsx` dòng 340-357) là UI đọc thẳng `policyDocuments`
(danh sách tài liệu), **không phải TemplateTask thật** — nên không bao giờ chảy vào
`generate_candidate_plan`. `TASK_CATEGORY_POLICY_MAP` (steps.py) hiện chỉ gắn thêm policy làm nguồn
PHỤ cho task ORIENTATION có sẵn ("Đọc tài liệu Overview"), không tạo ra 1 nhóm task riêng.

### 2c. Vì sao trích dẫn dồn cuối trang, markdown vỡ

- `content_llm.py::_build_sources_block()` đã đánh số `[1] [2]...` sẵn khi đưa vào prompt LLM và
  prompt (`prompts.py`) yêu cầu viết theo khung 3 mục — nhưng **không có chỉ dẫn nào bắt LLM chèn lại
  `[1]`/`[2]` vào đúng chỗ trong "Các bước thực hiện"**, nên output không có inline citation, và FE
  cũng không có chỗ render citation dù có.
- `frontend/.../ui/markdownPreview.tsx` (bộ render tự viết, không dùng thư viện) chỉ xử lý heading
  `#/##/###`, list gạch đầu dòng `- `/`* `, và đoạn văn — **không có nhánh nào cho danh sách đánh số
  `1. `/`2. `** hay checkbox `- [ ]`. Dòng `1. Cài đúng phiên bản...` rơi vào nhánh `else` (đoạn văn
  thường), bị nối chung với các dòng số khác thành 1 đoạn dính cục — đúng như ảnh 6 PM chụp.

## 3. Cách sửa

### 3.1. Chờ TV3 chunk PROJECT xong, verify + tích hợp — KHÔNG tự viết chunker (sửa gốc #1)

**Cập nhật 14/08 tối**: đã trao đổi trực tiếp với Mai Anh (TV3) qua Messenger. TV3 xác nhận đang
chủ động làm pipeline chunk PROJECT (chốt 1 chunk strategy, khác `policy_chunker.py`), dự kiến xong
tối nay, và hiểu đúng yêu cầu citation (PM duyệt plan cần bấm trỏ tới đúng đoạn tài liệu để kiểm
tra; Engineer đọc task cũng bấm citation xem lại đúng đoạn nguồn). TV1 sẽ pull code về khi TV3 xong
và tự tích hợp/verify — **không tự viết chunker tạm** (bỏ hướng "tái dùng `chunk_policy_markdown()`
với tham số riêng" đã cân nhắc trước đó) vì:
- Tránh code vứt đi (throwaway) — TV3 xong cùng ngày, viết tạm rồi thay lại tốn công 2 lần.
- Tránh 2 kiểu chunk lẫn lộn trong cùng version nếu cả 2 bên cùng ghi (đúng rủi ro đã phân tích).
- Chunk thật của TV3 (được thiết kế riêng cho PROJECT domain) chất lượng tốt hơn giải pháp tạm.

**Checklist verify khi pull code TV3 về** (không code gì thêm nếu tất cả đều đạt):
1. SQL: `document_chunks` có dòng cho tài liệu PROJECT (mọi category), `DocumentVersion.status`
   chuyển `ACTIVE` sau khi chunk xong (giống `activate_version()` POLICY đã làm) — nếu TV3 CHƯA tự
   activate thì chỉ cần thêm đúng 1 dòng gọi `document_version_service.activate_version()` ở đúng
   chỗ pipeline của TV3 kết thúc, không viết lại logic chunk.
2. SQL: đếm số chunk trung bình mỗi tài liệu PROJECT — nếu ≤1 chunk/file (tức bị gộp nguyên văn do
   target size lớn hơn cả file, đã cảnh báo trước với TV3 vì file mẫu chỉ ~600-900 token) thì báo
   lại TV3 điều chỉnh tham số, KHÔNG tự chunk lại phía Phase 4 (giữ đúng 1 nguồn ghi dữ liệu).
3. Chạy thử sinh plan GADGETHUB → xác nhận `bm25_search()` (đã có sẵn, không cần sửa) trả về kết
   quả khác rỗng cho ít nhất 1 task.

### 3.2. Thêm nhóm "Tìm hiểu công ty" thành task thật trong plan (sửa gốc #3)

Thêm giá trị enum mới `TaskCategory.COMPANY` (migration `ALTER TYPE task_category ADD VALUE`, an
toàn — chỉ thêm, không xoá giá trị cũ nào). Đây là hướng đúng thay vì "vá" bằng cách nhét thêm 1 task
vào ORIENTATION, vì:
- Khớp đúng mong muốn của PM: 1 nhóm hiển thị riêng "Tìm hiểu công ty" trong Onboarding Plan thật,
  giống hệt khối đã có ở Master Template.
- Tái dùng được toàn bộ hạ tầng nhóm-theo-category có sẵn (`CATEGORY_OPTIONS`, `PlanReviewView` gom
  nhóm theo `task.category`) — không cần thêm field/nhánh rẽ mới.

Việc cần làm:
- `src/model/enums.py`: thêm `COMPANY = "COMPANY"` vào `TaskCategory`; **không** thêm vào
  `DEFERRED_TASK_CATEGORIES` (category này phải sinh task thật ngay).
- Migration Alembic: `op.execute("ALTER TYPE task_category ADD VALUE IF NOT EXISTS 'COMPANY'")`
  (Postgres yêu cầu chạy ngoài transaction block hoặc dùng `AUTOCOMMIT` — khớp cách migration
  `766d77208fd9_add_architecture_task_category.py` đã làm trong repo, dùng lại nguyên văn cách viết
  `upgrade()`/`downgrade()` no-op của migration đó).
- `src/services/plan_generation/steps.py`:
  - `TASK_CATEGORY_DOCUMENT_MAP`: KHÔNG thêm COMPANY vào đây (category này không đọc tài liệu
    PROJECT, chỉ đọc POLICY).
  - `TASK_CATEGORY_POLICY_MAP[TaskCategory.COMPANY] = None` (đọc toàn bộ policy, giống cách
    ORIENTATION đang đọc — tái dùng nguyên nhánh code hiện có ở `map_task_sources()`, không cần
    nhánh mới vì nó vốn đã lặp qua `TASK_CATEGORY_POLICY_MAP` chung).
- Seed 1 `TemplateTask` mới ở **GLOBAL Master Template** (không phải sửa từng project — project mới
  tự fork từ GLOBAL, project cũ cần 1 script backfill nhỏ tương tự
  `scripts/backfill_project_templates.py` đã có sẵn pattern): `category=COMPANY,
  title_pattern="Tìm hiểu chính sách công ty", objective="Nắm chính sách nhân sự, bảo mật, phúc lợi
  trước khi bắt đầu công việc kỹ thuật"`, `mandatory=true`, `display_order` đứng trước ORIENTATION
  (company trước, kỹ thuật sau — đúng thứ tự PM mong muốn "1 phần công ty rồi 5 phần dự án").
- Frontend: `TaskFormModal.tsx` `CATEGORY_OPTIONS` thêm `{ value: "COMPANY", label: "Tìm hiểu công
  ty", icon: "shield", variant: "accent" }` (icon `shield` đã dùng sẵn ở khối cũ của Master Template
  — giữ nhất quán hình ảnh). `PlanReviewView.tsx` dùng chung `CATEGORY_OPTIONS` nên tự động có nhóm
  mới, không cần sửa gì thêm ở đó.
- `TemplateView.tsx`: khối "Tìm hiểu công ty" cũ (dòng 339-357, đọc thẳng `policyDocuments`) giữ
  nguyên như hiện tại cho mục đích xem nhanh danh sách chính sách — không xung đột, vì giờ nó là 1
  trong 6 thẻ category (thẻ đặc biệt luôn đứng đầu), còn task thật nằm trong version data như các
  category khác.

### 3.3. Không bịa nội dung khi thiếu nguồn (sửa gốc #1 phần hiển thị)

`content_llm.py::generate_baseline_content()`: khi `task_input.allowed_documents` rỗng, **không**
điền `instruction_template`/`objective` như đang làm. Thay bằng nội dung ngắn nêu rõ tình trạng:
```python
if not task_input.allowed_documents:
    instruction = (
        f"## Trạng thái\n{prompts.NO_SOURCE_NOTICE}\n\n"
        f"## Mục tiêu (tham khảo, chưa có tài liệu xác nhận)\n{task.objective.strip()}\n"
    )
```
Giữ lại `objective` dạng "tham khảo" (không xoá trắng hoàn toàn) vì PM vẫn cần biết task này định
làm gì để biết có nên bổ sung tài liệu hay không — nhưng đổi tiêu đề để không đánh lừa là "đã có
hướng dẫn đầy đủ". `generate_ai_content()` khi `hits` rỗng cũng rơi về nhánh này (đã dùng chung
`baseline[...]`) nên chỉ cần sửa 1 chỗ.

### 3.4. Trích dẫn nguồn ngay trong nội dung + mở đúng đoạn khi bấm (sửa gốc #5)

- `prompts.py::SYSTEM_PROMPT`: thêm quy tắc bắt buộc thứ 6 vào `INSTRUCTION_TEMPLATE_CONTRACT`/quy
  tắc: "Mỗi bước trong 'Các bước thực hiện' lấy thông tin từ NGUỒN nào thì chèn số trích dẫn `[n]`
  ngay cuối câu đó (khớp số thứ tự trong khối NGUỒN)". Giữ khung 3 mục như cũ, chỉ thêm yêu cầu chèn
  `[n]` inline — không đổi cấu trúc.
- `frontend/.../ui/markdownPreview.tsx`: thêm khả năng nhận `sources: PlanTaskSourceResponseDTO[]`
  và render `[n]` thành nút bấm nhỏ mở `DocumentPreviewModal` đúng nguồn thứ n (tái dùng
  `DocumentPreviewModal` đã có ở `PlanTaskDrawer.tsx`) — thêm 1 token pattern mới trong
  `renderInline()` cho `\[\d+\]`.
- Khối "Tài liệu nguồn (N)" ở cuối `PlanTaskDrawer.tsx` **vẫn giữ** làm danh sách tham chiếu đầy đủ
  (bấm để xem nguyên văn file) — không xoá, chỉ thêm inline citation clickable ngay trong nội dung,
  đúng ý PM "đoạn nào tài liệu nào nhét ngay đoạn đó" mà không mất chỗ xem toàn bộ nguồn.
- **Mở đúng đoạn khi bấm nguồn** (không chỉ mở nguyên file): `DocumentPreviewModal.tsx` hiện tải
  nguyên văn file rồi render toàn bộ, không cuộn/tô sáng tới đúng heading — đã đọc code xác nhận.
  Thêm prop `headingToScrollTo?: string` (truyền `citation_note`/heading của nguồn vừa bấm); trong
  `renderMarkdown()` gắn `id` (slug hoá từ text heading) cho mỗi thẻ `<h2>/<h3>` khi render; sau khi
  markdown tải xong, `useEffect` tìm heading khớp rồi `scrollIntoView({behavior:"smooth"})` + thêm
  class tô sáng tạm 2 giây rồi fade — không cần thư viện ngoài, tận dụng cấu trúc heading đã tách
  sẵn trong `renderMarkdown()`.

### 3.5. PM thêm/xoá/sửa task trên Lộ trình chuẩn (sửa gốc #4)

- `src/services/plan_task_service.py`: thêm `create_task(db, plan_id, dto)` và
  `delete_task(db, plan_task_id)` — copy đúng pattern guard đã có trong `update_task()` (chỉ cho khi
  `plan.status == DRAFT`; bản chuẩn luôn DRAFT nên PM sửa được vĩnh viễn, đúng thiết kế đã duyệt
  trước đó). `create_task` cần `display_order` mới (max hiện có + 1). **Bản chuẩn không có khái niệm
  "phát hành" nên KHÔNG áp rule 10 SoT "không xoá task mandatory"** (rule đó áp cho pipeline tự
  động, không áp cho PM chủ động sửa tay bản chuẩn) — PM được xoá tự do vì đây là nội dung PM tự
  biên tập.
- Router `plan_task_router.py`: thêm `POST /plan-tasks` (tạo, nhận `plan_id`), `DELETE
  /plan-tasks/{id}`.
- Frontend `PlanReviewView.tsx`: thêm nút "+ Thêm task" mỗi nhóm category (mở `PlanTaskDrawer` ở chế
  độ tạo mới — thêm prop `mode: "create" | "edit"` tái dùng UI có sẵn thay vì viết form riêng); mỗi
  `taskRow` thêm nút xoá (icon `trash`) kèm `PmConfirmModal` xác nhận (tái dùng `PmConfirmModal` đã
  dùng cho approve). Chỉ hiện các nút này khi `!isApproved` (đã có biến sẵn) — plan kỹ sư đã duyệt
  thì không đổi gì (đúng bất biến hiện có).

### 3.6. Sửa markdown renderer (sửa gốc #6)

`markdownPreview.tsx::renderMarkdown()`: thêm 2 nhánh trước nhánh `else` (đoạn văn):
- Regex `^\d+[.)]\s+` → gom vào `<ol>` (buffer riêng `orderedListBuffer`, giống `listBuffer` hiện có
  nhưng dùng thẻ `<ol>`).
- Regex `^-\s*\[( |x|X)\]\s+` → render `<li>` có `<input type="checkbox" checked disabled>` +
  text còn lại — checkbox chỉ hiển thị trạng thái (không tương tác, vì PlanTask không lưu trạng
  thái từng dòng checklist, chỉ lưu status của cả task).
- Test 3 case bằng tay: numbered list liên tiếp, checkbox list liên tiếp, xen kẽ heading — đảm bảo
  không phá nhánh bullet `- `/`* ` cũ (checkbox phải được thử TRƯỚC bullet thường vì cùng bắt đầu
  bằng `- `).

### 3.7. Dọn dữ liệu để PM tự sinh lại kiểm tra

Sau khi code xong 3.1-3.6, xoá lộ trình chuẩn hiện tại của GADGETHUB (project_id=136) bằng SQL trực
tiếp (đúng thứ tự FK: plan_task_sources → plan_tasks → onboarding_plans) để PM bấm sinh lại từ đầu
trên UI và tự kiểm tra cả 6 điểm cùng lúc.

## 4. Ngoài phạm vi (không làm trong lượt này)

- Không tự xây pipeline chunk/embedding cho tài liệu PROJECT — TV3 đang chủ động làm (xem 3.1),
  Phase 4 chỉ tiêu thụ dữ liệu qua `bm25_search()` có sẵn, không viết chunker riêng.
- Không thêm khái niệm "duyệt tài liệu" (document review workflow) — ngoài yêu cầu PM đưa ra lần này.
- Không đổi cách checkbox lưu trạng thái từng dòng riêng lẻ trong DB (chỉ hiển thị, không tương tác).

## 5. Kiểm chứng

1. `pytest PM-test/ tests/ -q` xanh; test mới cần thêm, mỗi cái map đúng 1 mục ở phần 3:
   - `test_generate_plan_finds_sources_after_import` (3.1) — sau khi tài liệu PROJECT có chunk +
     ACTIVE (dữ liệu TV3 tạo), sinh plan → task tương ứng phải có `sources` khác rỗng.
   - `test_reference_plan_has_company_group` (3.2) — sinh bản chuẩn, có ≥1 task `category=COMPANY`,
     đứng trước các task category khác theo `display_order`.
   - `test_baseline_no_source_does_not_fabricate` (3.3) — task không có tài liệu nguồn, assert nội
     dung KHÔNG chứa `instruction_template` gốc, có chứa `NO_SOURCE_NOTICE`.
   - `test_ai_content_has_inline_citation` (3.4) — mock LLM trả nội dung có `[1]`, assert
     `PlanTaskSource` ghi đúng, không assert nội dung UI (phần render là FE, kiểm bằng tay ở bước 7).
   - `test_pm_create_and_delete_plan_task` (3.5) — tạo task mới vào plan DRAFT, xoá task, xác nhận
     `display_order` không trùng; thử xoá/tạo trên plan đã APPROVED → 409.
   - Test hiện có `test_plan_generation.py` (đã có ở PM-test) chạy lại để đảm bảo không phá hành vi
     cũ (đặc biệt các test dùng `_generate_reference_plan` fixture — giờ sẽ có thêm nhóm COMPANY,
     cần cập nhật assertion số lượng task nếu test nào đếm cứng số task).
2. `ruff check` sạch; FE `tsc`/`eslint` sạch.
3. `alembic upgrade head` chạy được, không lỗi thêm enum value.
4. **Tracing/observability**: bước chunk PROJECT thuộc pipeline của TV3 (CRUD/import, không phải
   bước AI trong `generate_candidate_plan`) — theo đúng nguyên tắc hiện có (`observe_step` chỉ bọc
   các bước của pipeline sinh plan, xem `pipeline.py`), Phase 4 **không** cần thêm Langfuse span
   mới. Các bước 3.2-3.4 vẫn chảy qua pipeline sẵn có nên tự động được trace/log (`log_step_event`,
   `@observe_step`) như mọi lần sinh plan khác — chỉ cần xác minh trace mới xuất hiện đúng trên
   Langfuse dashboard ở bước 7 dưới đây (đối chiếu span `generate_plan_task_content` có nội dung +
   citation `[n]` trong output).
5. Nhắn TV3 báo trước khi bắt đầu tích hợp (đã làm — xem 3.1), không cần chờ duyệt thêm.
6. Dọn dữ liệu cũ GADGETHUB theo 3.7.
7. Chạy thật trên GADGETHUB:
   - Xác nhận `DocumentVersion`/`document_chunks` của GADGETHUB đã có dữ liệu từ TV3.
   - Sinh lộ trình chuẩn → xác nhận có nhóm "Tìm hiểu công ty" đứng đầu + 5 nhóm dự án.
   - Mở task có tài liệu → thấy trích dẫn `[1]` bấm được ngay trong đoạn văn; bấm vào mở đúng file
     và cuộn/tô sáng tới đúng đoạn, không chỉ mở nguyên file.
   - Mở task cố tình không có tài liệu nguồn (xoá hết tài liệu 1 category để test) → thấy nội dung
     báo rõ "chưa có tài liệu", không còn hướng dẫn chi tiết giả.
   - Bấm "+ Thêm task" và nút xoá task → xác nhận hoạt động, chỉ khi plan còn DRAFT.
   - Xem 1 task có numbered list/checkbox trong nội dung → render đúng `<ol>`/checkbox thật.
   - Xem trace mới trên Langfuse dashboard đúng job sinh plan vừa chạy.
8. Dọn sạch dữ liệu test sau khi lấy bằng chứng, cập nhật `docs/PM/Phase-4/report-phase4.md` với
   bằng chứng SQL/ảnh chụp/log cho từng điểm ở trên.
