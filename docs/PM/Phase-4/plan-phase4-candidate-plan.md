# Plan Phase 4 — Candidate Plan Generation & Review (owner-plan-generating, owner-plan-review)

> Trạng thái: **ĐÃ DUYỆT, CHƯA CODE**. Bổ sung cho `docs/PM/plan-pm.md` Phase 4.

## 1. Context

Mục tiêu: từ **tài liệu thật của 1 project** (5 nhóm PROJECT) + **Company Core** (18 chính sách),
sinh ra một **lộ trình onboarding hoàn chỉnh** cho kỹ sư mới — mỗi task có hướng dẫn từng bước,
**kết quả cần đạt** (checklist tick được), **trích nguồn bấm xem đúng đoạn tài liệu**, và mốc thời
gian. PM xem, sửa, Approve rồi phát hành cho Engineer. Đây là phần BE phức tạp nhất của Thành viên 1.

## 2. Bằng chứng khảo sát code — đã đọc/chạy thật, không suy đoán

| # | Phát hiện | Bằng chứng |
|---|---|---|
| 1 | **`RetrievalEngine` đã có sẵn, ACL-safe** — dense (pgvector cosine) + BM25 (ParadeDB) + RRF fusion, có `RetrievalFilters(project_id, document_categories, ...)` và `_validate_evidence()` re-check ACL sau fusion | `src/ai/retrieval_engine/retrieval_engine.py` (287 dòng) |
| 2 | **Nhưng chunk PROJECT có 0 embedding** → nhánh dense vô dụng cho tài liệu dự án (`PgvectorDenseRetriever` lọc `.where(embedding.is_not(None))`) | SQL: PROJECT = 105 chunk / **0** vector; POLICY = 192 chunk / 192 vector |
| 3 | **`sentence-transformers` KHÔNG được cài** (cả `.venv` lẫn container) → gọi `RetrievalEngine.retrieve()` sẽ crash vì nó luôn `query_encoder.embed()` | `python -c "import sentence_transformers"` → `ModuleNotFoundError` ở cả 2 nơi |
| 4 | **BM25 chạy được NGAY**: index `ix_document_chunks_lexical_bm25` (access method `bm25`, 3200 kB) tồn tại thật; 105/105 chunk PROJECT có `embedding_text` | `\di+ ix_document_chunks_lexical_bm25` |
| 5 | **`PlanTask` KHÔNG có cột acceptance criteria** — chỉ `(title, instruction, display_order, mandatory, due_at, status, started_at, completed_at)` | `src/model/plan_task.py` |
| 6 | **`PlanTaskSource` KHÔNG có `chunk_id`** — chỉ `(plan_task_id, version_id, citation_note)` → hiện chỉ trỏ được tới cả file | `src/model/plan_task_source.py` |
| 7 | **`TaskDependency` trỏ tới `template_tasks`, KHÔNG phải `plan_tasks`** | FK `fk_task_dependencies_predecessor_task_id_template_tasks` |
| 8 | **INV7 trigger có thật**: `BEFORE UPDATE OF status` → chặn lùi rank DRAFT(1)→…→CLOSED(5) | `enforce_onboarding_plan_forward_status()` trong DB + migration `a1b2c3d4e5f6` |
| 9 | **Chỉ được 1 plan "chưa đóng" / membership**: `uq_onboarding_plans_one_open_per_membership UNIQUE (membership_id) WHERE status <> 'ONBOARDING_CLOSED'` | `\d onboarding_plans` |
| 10 | **Chưa project nào có TemplateVersion APPROVED** — FURNISTORE/TOURBOOK/FITECH đều DRAFT (7 task) | SQL join `template_versions` |
| 11 | **Langfuse hoàn toàn chưa có** (không trong `requirements.txt`, `src/`, `.env`, compose) | grep toàn repo → rỗng |
| 12 | **`src/agents/` chỉ là scaffold TODO stub** (`example_node.py`, `example_tool.py`) — không phải logic thật | đọc file, toàn `# TODO` |
| 13 | Đã có sẵn pattern **job in-memory + TTL prune** để tái dùng | `_SCAN_SESSIONS` trong `src/services/repo_scanner_service.py` |
| 14 | **FURNISTORE + TOURBOOK là data test hoàn hảo**: đủ nhóm tài liệu, version ACTIVE, có chunk | SQL group by category |

**Hệ quả trực tiếp**: Phase 4 dùng **BM25-only retrieval** (chạy được hôm nay, không cần cài torch
~2.5GB). Khi TV3 backfill embedding cho PROJECT + cài `sentence-transformers`, đổi sang hybrid chỉ
là thay 1 lời gọi — thiết kế sẵn cho việc đó, không phải viết lại.

---

## 3. Chốt phạm vi category: chỉ dùng 5, hoãn 2 — **trả lời 3 câu hỏi của PM**

PM chốt: `DocumentCategory` chỉ dùng **5** giá trị (`OVERVIEW`, `ARCHITECTURE`, `SETUP`,
`ACCESS_SECURITY`, `CODEBASE_GUIDE`); `CONVENTION` + `FIRST_TASK` **hoãn làm sau**.

### 3.1. Có phải sửa model không? → **KHÔNG, không sửa dòng nào**

**Không được xoá 2 giá trị khỏi enum**, vì 3 lý do có bằng chứng:

1. **PostgreSQL không hỗ trợ xoá giá trị enum** — chỉ có `ADD VALUE`, không có `DROP VALUE`. Muốn
   xoá phải tạo type mới + `ALTER TABLE ... TYPE` + migrate dữ liệu → rủi ro cao, không đáng.
2. **Đang có dữ liệu thật tham chiếu**: FURNISTORE và TOURBOOK mỗi project có 1 tài liệu
   `CONVENTION` (7 chunk) và 1 tài liệu `FIRST_TASK` (5 chunk), version ACTIVE. Xoá enum = hỏng
   những dòng này.
3. **Đã có tiền lệ y hệt trong chính codebase** — `src/model/enums.py` xử lý đúng tình huống này
   cho `TaskCategory` bằng cách **giữ enum, thêm 1 tuple hoãn**:

```python
# src/model/enums.py — code ĐANG CÓ, không phải đề xuất mới
DEFERRED_TASK_CATEGORIES = (TaskCategory.CONVENTION, TaskCategory.FIRST_TASK, TaskCategory.FIRST_PR)
```
kèm comment giải thích nguyên văn: *"KHÔNG xoá khỏi enum vì Postgres không hỗ trợ xoá giá trị enum
và 1 số TemplateTask cũ ở GLOBAL vẫn còn bị PlanTask demo tham chiếu"*.

→ **Phase 4 làm y đúng cách đó**: chỉ map 5 category trong bảng ở §5, không đụng file model nào,
không migration cho việc này. (Và Phase 4 cũng **không có migration nào khác** — xem §5.)

### 3.2. Có ảnh hưởng Thành viên 2 (làm task list cho kỹ sư) không? → **KHÔNG**

| Lý do | Bằng chứng |
|---|---|
| TV2 **không đọc `DocumentCategory`**, cũng không đọc `TemplateTask` — chỉ đọc `PlanTask` snapshot | SoT §17.5 contract #4: *"TV1 phát hành Approved Plan; TV2 đọc và thực thi snapshot đó, **không đọc trực tiếp TemplateTask** để chạy checklist"* |
| Task list của TV2 **vốn đã không có** CONVENTION/FIRST_TASK/FIRST_PR — bị lọc bỏ từ Phase 2 khi fork template cho project | `template_version_service.py:52` — `TemplateTask.category.not_in(DEFERRED_TASK_CATEGORIES)` |
| Kiểm chứng trên DB thật: **toàn bộ project template chỉ có đúng 5 nhóm task** | SQL: ORIENTATION 11, ACCESS 22, SETUP 22, CODEBASE 11, ARCHITECTURE 11 — **không có** CONVENTION/FIRST_TASK/FIRST_PR |

→ Quyết định này **không đổi gì** với TV2. Lộ trình họ nhận vẫn đúng 5 nhóm như trước giờ.

### 3.3. Có ảnh hưởng người khác (TV3, TV4, HR) không? → **KHÔNG**

- **TV3** (pipeline chunk/embedding) chạy theo `DocumentVersion`, không phân biệt category → không đụng.
- **TV4/HR** chỉ quản lý domain POLICY (`PolicyCategory`, enum khác hẳn) → không đụng.
- **Phần đã code của chính TV1 cũng đã chỉ dùng 5 từ trước**:
  - BE `repo_scanner_service.py:35-39` — tuple phân loại chỉ có đúng 5 category, keyword map cũng chỉ 5 key.
  - FE `documentCategoryMeta.ts:21-27` — `REQUIRED_DOCUMENT_CATEGORIES` đúng 5; 2 cái còn lại đã gắn nhãn `"(mở rộng làm sau)"`.

→ Nói cách khác: **quyết định "chỉ 5" đã được thực thi sẵn ở mọi nơi quan trọng**, Phase 4 chỉ cần
đi theo cho nhất quán, không phải sửa ngược cái gì.

### 3.4. Dữ liệu CONVENTION/FIRST_TASK đang có thì sao?

FURNISTORE + TOURBOOK đang có 2 tài liệu thuộc 2 nhóm hoãn (12 chunk). **Đề xuất: giữ nguyên,
không xoá** — chúng hợp lệ, hiện đã không hiện trên UI Tài liệu dự án (FE chỉ render 5 card), và sẽ
dùng được ngay khi mở rộng 2 nhóm này sau. Phase 4 đơn giản là không lấy chúng làm nguồn. Ghi rõ
trong report để người sau không tưởng là data rác.

---

## 4. Bốn quyết định kiến trúc

| Quyết định | Chốt | Lý do |
|---|---|---|
| **Schema** | **KHÔNG sửa model, KHÔNG migration nào.** Trích dẫn ở mức **file** bằng `PlanTaskSource.version_id` (đã có sẵn); tên mục trong file ghi vào `citation_note` (cột Text đã có sẵn). "Kết quả cần đạt" nằm trong `PlanTask.instruction` dạng markdown có cấu trúc cố định | PM chốt (14/08): trích dẫn tới file là đủ dùng, vì 1 category giờ có nhiều file nên biết đúng file nào đã là thông tin chính. Trích tới đúng đoạn (`chunk_id`) → **hoãn, phát triển sau** (§18). Giữ trọn vẹn lệnh "không sửa model" của Phase 3 |
| **Kiến trúc AI** | Pipeline 6 bước deterministic; **chỉ bước 5** gọi LLM, LLM được cấp 4 tool truy xuất tài liệu | Khớp SoT §15.3 + §24.5 (*"không gọi LLM cho validation/state transition"*); 5 bước test bằng `pytest`, eval AI chỉ cho 1 bước; chi phí/latency đoán được; không thể vi phạm rule 10 *"không xoá task mandatory"* |
| **Phạm vi sinh** | Sinh 1 lần cho mỗi `(project, template_version)` → cache → nhân bản cho từng kỹ sư | PM chọn. Đúng SoT §12 (*"kỹ sư cùng dự án nhận nội dung giống nhau"*); chi phí LLM không nhân theo số kỹ sư |
| **Tiến độ 6 bước** | POST tạo job → GET polling (in-memory, TTL) | Repo không có SSE/worker queue nào; tái dùng đúng pattern `_SCAN_SESSIONS` đã chạy tốt ở Phase 3; tiến độ **thật**, không animation giả |

**Model LLM**: **DeepSeek** (`deepseek-chat`) cho bước sinh nội dung — đã có key thật + đã dùng ở
Phase 3 (`get_classifier_llm()`), rẻ hơn OpenAI ~10x. Giữ **OpenAI `gpt-4o-mini`** làm **judge** ở
phần eval — đúng khuyến nghị Day-14 *"judge model khác model sinh để tránh self-preference bias"*.

## 5. Thay đổi dữ liệu — **KHÔNG có migration, KHÔNG sửa model nào**

Toàn bộ Phase 4 chạy trên schema hiện tại. Trích dẫn nguồn dùng `PlanTaskSource` **đúng như đang
có**:

| Cột sẵn có | Phase 4 dùng để làm gì |
|---|---|
| `version_id` (NOT NULL) | Trỏ tới **đúng 1 file** (`DocumentVersion`) đã dùng làm nguồn → FE bấm mở tài liệu đó |
| `citation_note` (Text, nullable) | Ghi **tên mục/heading** trong file (ví dụ `"Mục 3.2 — Chạy service ở local"`) để người đọc biết tìm ở đâu trong file, mà không cần cột `chunk_id` |
| `UniqueConstraint(plan_task_id, version_id)` | Giữ nguyên → 1 task cite 1 lần/file; nhiều đoạn cùng file thì gộp mô tả vào `citation_note` |

Bước sinh nội dung **vẫn tìm kiếm theo từng đoạn** (BM25 trên `document_chunks`) để lấy đúng ngữ
cảnh đưa vào prompt — chỉ là khi **lưu** thì quy về mức file + ghi heading vào `citation_note`.
Không mất gì về chất lượng nội dung, chỉ khác ở độ chi tiết của cái link.

## 6. Pipeline 6 bước (`src/services/plan_generation/`)

| # | Bước | Loại | Việc làm |
|---|---|---|---|
| 1 | `load_template` | code | Tìm `TemplateVersion` APPROVED của project → load `TemplateTask` + `TaskDependency`. Không có APPROVED → lỗi 422 rõ ràng (SoT rule 16 *"không tạo âm thầm"*) |
| 2 | `merge_company_core` | code | Load `KnowledgeDocument` domain POLICY status ACTIVE (18 chính sách) làm nguồn dùng chung |
| 3 | `collect_project_docs` | code | Load tài liệu PROJECT của **đúng project_id**, chỉ `DocumentVersion.status=ACTIVE` (SoT rule 7), group theo `document_category`, **chỉ lấy 5 nhóm đang dùng** (§3) |
| 4 | `map_task_sources` | code | Map `TaskCategory → DocumentCategory` (bảng dưới) → mỗi TemplateTask biết được đọc nhóm tài liệu nào |
| 5 | `generate_content` | **LLM + tools** | Với mỗi task: LLM gọi tool tra tài liệu → sinh `instruction` (markdown §8) + chọn chunk trích dẫn |
| 6 | `validate_and_persist` | code | Kiểm tra: đủ task mandatory (rule 10), `display_order` duy nhất, dependency không cycle (**tái dùng `_has_cycle()`** ở `template_version_service.py:92`), mọi citation trỏ tới chunk thuộc đúng project → ghi DB 1 transaction |

**Bảng map category** — đúng 5 nhóm đang dùng, deterministic, không để AI tự đoán:

| TaskCategory (template) | DocumentCategory được đọc |
|---|---|
| `ORIENTATION` | `OVERVIEW` + toàn bộ POLICY (Company Core) |
| `ARCHITECTURE` | `ARCHITECTURE` |
| `ACCESS` | `ACCESS_SECURITY` + POLICY nhóm `SECURITY_POLICY` |
| `SETUP` | `SETUP` |
| `CODEBASE` | `CODEBASE_GUIDE` |

> `CONVENTION` / `FIRST_TASK` / `FIRST_PR` **không có trong bảng** vì template project không sinh ra
> task thuộc các nhóm đó (đã lọc bằng `DEFERRED_TASK_CATEGORIES` từ Phase 2). Khi nào mở rộng thì
> thêm 3 dòng vào bảng này + bỏ khỏi 2 tuple `DEFERRED_*` — không cần đổi kiến trúc.

**Mốc thời gian (`due_at`)** — tính deterministic ở bước 6, **không cần cột mới**: cộng dồn
`TemplateTask.estimated_minutes` theo `display_order`, quy đổi 8h/ngày làm việc (bỏ T7/CN) từ ngày
tạo plan → ra lộ trình có mốc ngày rõ ràng theo chuẩn onboarding thị trường.

## 7. Tools cấp cho LLM (`plan_generation/tools.py`)

Mỗi tool là `@tool` (`langchain_core.tools`, đã có sẵn trong `requirements.txt`), **bọc quanh
`_ScopedRetriever.base_statement()` + `RetrievalFilters` bị khoá cứng `project_id` ở tầng service**
→ LLM **không thể** đọc chéo project kể cả khi prompt bị injection (SoT §19 *"chặn cross-project
retrieval"*, *"prompt injection trong tài liệu được coi là dữ liệu, không phải system instruction"*).

| Tool | Input | Trả về |
|---|---|---|
| `search_project_docs` | `query`, `category` | Top-k chunk BM25 trong đúng project + đúng nhóm tài liệu |
| `search_company_policy` | `query` | Top-k chunk BM25 trong domain POLICY |
| `get_document_outline` | `document_id` | Danh sách `heading`/`section_path` để LLM nắm cấu trúc trước khi trích |
| `read_chunk` | `chunk_id` | Nội dung đầy đủ 1 chunk (khi cần đọc kỹ trước khi cite) |

Dùng `ParadeDbBm25Retriever` **trực tiếp** (không qua `RetrievalEngine.retrieve()`) vì bằng chứng
#2/#3. Viết 1 hàm `bm25_search(session, query, filters, k)` nhỏ, **tái dùng nguyên
`scope_predicates()` có sẵn — không copy lại logic ACL**.

## 8. Hợp đồng nội dung `PlanTask.instruction`

LLM **bắt buộc** sinh đúng khung markdown này; BE validate ở bước 6, FE parse để render, script eval
chấm theo từng mục:

```markdown
## Mục tiêu
<1-2 câu, vì sao task này cần thiết>

## Các bước thực hiện
1. <bước cụ thể, có lệnh/đường dẫn thật lấy từ tài liệu>
2. ...

## Kết quả cần đạt
- [ ] <tiêu chí kiểm chứng được, ví dụ: "gọi GET /health trả 200">
- [ ] ...

## Nguồn tham khảo
- <tên tài liệu> › <tên mục>   ← FE map sang PlanTaskSource để bấm mở đúng FILE tài liệu
```

Không tìm được nguồn: **không bịa** — ghi `> ⚠️ Chưa có tài liệu nguồn cho task này, PM cần bổ sung.`
và để `PlanTaskSource` rỗng; màn Review hiện cảnh báo (đúng mockup *"cảnh báo thiếu nguồn"* + edge
case bắt buộc trong `plan-pm.md` §4.3).

## 9. API (BE)

**Mở rộng `src/api/routers/onboarding_plan_router.py`** (2 route đọc hiện có giữ nguyên):

| Method | Path | Việc |
|---|---|---|
| POST | `/onboarding-plans/pm/generate` | Body `{membership_id}` → tạo job, trả `{job_id, correlation_id}` ngay (202) |
| GET | `/onboarding-plans/pm/generate/{job_id}` | Tiến độ 6 bước: `[{step, status, duration_ms}]` + `plan_id` khi xong |
| POST | `/onboarding-plans/pm/{plan_id}/regenerate` | Chỉ khi DRAFT (§12) |
| PATCH | `/onboarding-plans/pm/{plan_id}/approve` | DRAFT → APPROVED, set `approved_by_user_id`/`approved_at` |
| GET | `/onboarding-plans/pm/{plan_id}/tasks` | PlanTask + PlanTaskSource + thông tin tài liệu để render citation |

**Router mới `plan_task_router.py`**: `PATCH /plan-tasks/pm/{id}` (PM sửa title/instruction),
`PATCH /plan-tasks/pm/reorder` — chỉ cho sửa khi plan còn DRAFT (rule 11: PlanTask là snapshot).

**File BE mới**:
```
src/services/plan_generation/__init__.py
                              pipeline.py      # orchestrate 6 bước + emit tiến độ vào job store
                              steps.py         # 5 bước deterministic
                              content_llm.py   # bước 5: LLM + tools
                              tools.py         # 4 tool + bm25_search
                              prompts.py       # system prompt (tách riêng để eval/version hoá)
                              job_store.py     # in-memory job, TTL — pattern _SCAN_SESSIONS
src/services/plan_task_service.py
src/observability/__init__.py, langfuse_client.py, logging.py
src/dto/request/onboarding_plan_request_dto.py, plan_task_request_dto.py
src/dto/response/onboarding_plan_response_dto.py (mở rộng), plan_task_response_dto.py,
                 plan_generation_job_response_dto.py
```
`onboarding_plan_service.py` giữ 2 hàm đọc cũ, thêm `approve_plan`, `regenerate_plan`,
`persist_generated_plan`.

## 10. Observability (Day 13)

- Thêm `langfuse>=3.0` vào `requirements.txt`; env `LANGFUSE_PUBLIC_KEY`/`SECRET_KEY`/`HOST` vào
  `src/config.py` (mặc định `""` → **thiếu key thì no-op**, không chặn dev/CI — CI không có secret).
- `@observe` bọc từng bước → 1 trace / lần generate, 6 span con. Span bước 5 gắn
  `gen_ai.usage.input_tokens`/`output_tokens`; 5 span còn lại tên `execute_tool <tên bước>`.
- `correlation_id` (uuid4) sinh ở router, xuyên suốt log, trả về FE trong response.
- Log JSON mỗi bước: `{event, correlation_id, plan_id, step, duration_ms, chunk_count}` —
  **không log nội dung tài liệu/instruction** (SoT §19 *"không log nội dung nhạy cảm"*).
- `duration_ms` từng bước chính là nguồn dữ liệu cho UI 6 bước — không animation giả.

## 11. Frontend

**DTO mới** (`frontend/src/features/project-management/dto/`): `requestDTO/plan.request.ts`,
`responseDTO/planTask.response.ts`, `responseDTO/planGenerationJob.response.ts`; mở rộng
`onboardingPlan.response.ts`.

**Component mới** (`components/plan/`):

| File | Việc |
|---|---|
| `PlanGeneratingView.tsx` | Màn 6 bước, poll 1s/lần, mỗi bước `pending → active → done` kèm thời gian thật |
| `PlanReviewView.tsx` | Task gom theo `TaskCategory` (tái dùng pattern `CategoryTaskDrawer`), badge cảnh báo thiếu nguồn, checklist trước duyệt, nút Approve |
| `PlanTaskDrawer.tsx` | Chi tiết 1 task: render markdown (**tái dùng `renderMarkdown()`** ở `components/ui/markdownPreview.tsx`), hiện "Kết quả cần đạt", danh sách nguồn |
| `PlanTaskEditModal.tsx` | PM sửa tay title/instruction khi còn DRAFT |
| `SourceCitationList.tsx` | Mỗi nguồn bấm được → mở **`DocumentPreviewModal`** đã có sẵn (mở đúng file); hiển thị kèm `citation_note` để biết xem mục nào trong file |

**Sửa file có sẵn**: `MembersView.tsx` bật nút "Tạo Onboarding Plan" (hiện `disabled title="Sắp có —
Phase 4"`, dòng ~253) → điều hướng sang `PlanGeneratingView`. `PmShell.tsx` giữ nguyên (vào từ trang
Thành viên, không thêm mục nav).

## 12. Regenerate & INV7 — **sửa lại giả định sai trong `plan-pm.md`**

`plan-pm.md` dòng 105 ghi: *"phải tạo `OnboardingPlan` mới (bản DRAFT mới) thay thế, giữ bản cũ
nguyên trạng"*. **Cách này chạy sẽ lỗi ngay** — index `uq_onboarding_plans_one_open_per_membership`
chỉ cho **1 plan chưa đóng / membership**; tạo bản DRAFT thứ 2 khi bản cũ đang APPROVED → vi phạm
unique constraint.

Cách đúng:
- **Plan còn DRAFT** → regenerate **tại chỗ**: xoá `PlanTaskSource` + `PlanTask` cũ, sinh lại, tăng
  `OnboardingPlan.revision`. Status **không đổi** (vẫn DRAFT) → trigger INV7 (`BEFORE UPDATE OF
  status`) không hề bị kích hoạt, index cũng không bị đụng. Đơn giản và an toàn hơn hẳn.
- **Plan đã APPROVED trở lên** → **không cho regenerate**, UI ẩn nút, BE trả 409 kèm lý do rõ. Muốn
  đổi nội dung thì sửa tay từng task (đúng rule 11 *"PlanTask là snapshot thực thi"*).

## 13. Eval AI (Day 14) — chỉ cho bước 5

Theo đúng `plan-pm.md` §4.1–4.8, đặt tại `docs/PM/Phase-4/`:
- `eval-golden-dataset.jsonl` — 20 case, lấy TemplateTask thật của FURNISTORE/TOURBOOK (data thật,
  không bịa), ≥ 2 edge case *"không có nguồn"*.
- `tools/eval_plan_content.py` — Faithfulness / Context Recall / Context Precision / Relevancy; chạy
  mỗi case ≥ 3 lần, báo `mean ± std`.
- `tools/eval_judge.py` — LLM-as-Judge rubric 1–5, reference-based, CoT, `temperature=0`,
  **judge = `gpt-4o-mini` (OpenAI)** trong khi sinh bằng **DeepSeek** → khác model, đúng slide.
- Baseline **B0** = copy nguyên `TemplateTask.instruction_template` → so % case AI thắng B0.
- `eval-report.md` — kết quả + failure analysis 5 Whys + improvement log ≥ 3 mục.

## 14. Test — `PM-test/test_plan_generation.py` (mới)

Tái dùng helper sẵn có trong `PM-test/test_onboarding_plans.py` (`_create_project`,
`_create_engineer_membership`):

1. Không có TemplateVersion APPROVED → 422, không tạo plan rác.
2. Generate thành công → số PlanTask == số TemplateTask, **mọi task mandatory đều còn** (rule 10).
3. `display_order` giữ đúng thứ tự template; `due_at` tăng dần.
4. Citation chỉ trỏ tới chunk thuộc đúng project (tạo 2 project, kiểm tra không lẫn).
5. Task không có nguồn → vẫn tạo được + có cờ cảnh báo, **không bịa citation**.
6. Regenerate khi DRAFT → PlanTask cũ bị thay, `revision` +1, status vẫn DRAFT.
7. Regenerate khi APPROVED → 409.
8. Approve → status APPROVED, có `approved_at`; approve lần 2 → 409.
9. **Test INV7 thật**: cố update APPROVED → DRAFT qua ORM → phải raise từ DB trigger.
10. **Test phạm vi category**: plan sinh ra không chứa task/nguồn thuộc `CONVENTION`/`FIRST_TASK` (§3).
11. Bước 5 mock LLM (không gọi mạng thật trong test) — theo đúng cách `tests/` hiện có.

## 15. Thứ tự thực hiện

1. ~~Migration~~ — **không có bước này nữa** (§5: Phase 4 không đụng schema).
2. `plan_generation/` các bước **deterministic** (1,2,3,4,6) + `job_store.py` — chạy end-to-end với
   bước 5 tạm nối thẳng `instruction_template` (**chính là baseline B0**, có luôn mốc so sánh eval).
3. Endpoint generate/polling + DTO → test bằng Swagger.
4. FE `PlanGeneratingView` + `PlanReviewView` + citation → thấy lộ trình thật chạy trên FURNISTORE.
5. Bước 5 thật: `tools.py` + `content_llm.py` + `prompts.py` (DeepSeek).
6. Observability (Langfuse + correlation_id + JSON log).
7. Approve/regenerate/edit + `PM-test/test_plan_generation.py`.
8. Eval Day-14 (golden dataset → script → report).
9. Rebuild Docker, verify UI thật, viết `docs/PM/Phase-4/report-phase4.md` kèm bằng chứng.

## 16. Verification

- `pytest PM-test/ tests/ -q` xanh; `ruff check src/ PM-test/` sạch.
- `git diff src/model/ alembic/` **rỗng** — bằng chứng Phase 4 không đụng schema (§5).
- FE: `npx tsc --noEmit`, `npx eslint`, `npm run build` sạch.
- **Chuẩn bị data**: approve TemplateVersion của FURNISTORE (hiện DRAFT — bằng chứng #10) rồi mới
  generate được.
- Chạy thật: Thành viên → "Tạo Onboarding Plan" → xem 6 bước chạy → Review thấy task gom theo nhóm,
  bấm nguồn mở đúng tài liệu → sửa 1 task → Approve → trạng thái đổi trên trang Thành viên.
- Bằng chứng: SQL đếm PlanTask/PlanTaskSource, trace Langfuse, curl thật — **dọn sạch data test sau
  khi lấy bằng chứng** (bài học 2 lần rò rỉ data ở Phase 3).

## 17. Hoãn — phát triển sau (đã thiết kế sẵn đường đi, chưa làm)

### 17.1. Trích dẫn tới **đúng đoạn** tài liệu (`PlanTaskSource.chunk_id`)

Hiện tại bấm nguồn mở được **đúng file**; muốn nhảy thẳng tới đúng đoạn trong file thì cần thêm cột
`chunk_id`. PM chốt hoãn (14/08) để Phase 4 không phải đụng schema.

Khi làm sau, việc cần đúng 3 bước nhỏ (đã verify là khả thi, không phải sửa kiến trúc):

```python
# 1. migration
op.add_column("plan_task_sources", sa.Column("chunk_id", sa.Integer(), nullable=True))
op.create_foreign_key("fk_plan_task_sources_chunk_id_document_chunks",
                      "plan_task_sources", "document_chunks", ["chunk_id"], ["chunk_id"])
# 2. thêm 1 dòng vào src/model/plan_task_source.py
# 3. bước sinh nội dung GHI thêm chunk_id — dữ liệu này VỐN ĐÃ CÓ SẴN trong ChunkHit.chunk_id
#    (tools.py đã trả về), hiện chỉ đang bỏ đi không lưu
```

Lý do dễ: pipeline **vốn đã tìm kiếm theo từng đoạn** (`bm25_search` trả `ChunkHit.chunk_id`), chỉ
là lúc lưu thì quy về mức file. Bật lên chỉ là thôi bỏ đi giá trị đang có, không phải xây thêm gì.

**Cảnh báo cần biết trước**: `UniqueConstraint(plan_task_id, version_id)` hiện chặn 1 task cite 2
đoạn trong CÙNG 1 file. Muốn cite nhiều đoạn/file thì phải đổi unique thành
`(plan_task_id, version_id, chunk_id)` trong cùng migration đó.

## 18. Ngoài phạm vi Phase 4

- **Access Scope/ACL theo từng kỹ sư** — `plan-pm.md` đã chốt bỏ (chưa có entity). Bước 3 lọc theo
  project + category, **không** lọc theo access scope. Ghi rõ trong report, không giả vờ có.
- **2 nhóm tài liệu hoãn** `CONVENTION`/`FIRST_TASK` (§3) — giữ enum + giữ dữ liệu, chỉ không dùng.
- Backfill embedding cho chunk PROJECT (việc của TV3) → xong thì đổi BM25-only sang hybrid.
- Engineer xem/tick task (TV2 – Phase 5), Blocker (Phase 6), Dashboard (Phase 7).
- Dashboard Grafana/Prometheus, alert, SLO — dùng Langfuse có sẵn là đủ.
