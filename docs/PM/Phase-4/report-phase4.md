# Báo cáo Phase 4 — Candidate Plan Generation & Review (UC-06)

> Trạng thái: **ĐÃ CODE XONG, ĐÃ TEST, ĐÃ CHẠY THẬT TRÊN DOCKER**.
> Theo plan đã duyệt: [`plan-phase4-candidate-plan.md`](plan-phase4-candidate-plan.md).
> Ngày hoàn thành: 14/08/2026.

---

## 1. Làm được gì — tóm tắt 1 phút

PM bấm **"Tạo Onboarding Plan"** cho 1 kỹ sư → hệ thống đọc **Master Template đã duyệt** +
**tài liệu dự án** + **Company Core** → AI viết ra lộ trình hoàn chỉnh: mỗi task có **mục tiêu**,
**các bước thực hiện cụ thể**, **kết quả cần đạt** (checklist kiểm chứng được), **trích dẫn tài liệu
nguồn bấm xem được**, và **deadline**. PM xem, sửa tay nếu cần, rồi **Duyệt & phát hành**.

**Chạy thật, số đo thật** (project FURNISTORE, 14/08/2026):

| Chỉ số | Giá trị |
|---|---|
| Thời gian sinh 1 plan | **34,5 giây** (trong đó 34,4s là bước gọi LLM) |
| Task sinh ra | 7/7 (khớp đúng số TemplateTask) |
| Task do AI viết nội dung | **7/7** |
| Trích dẫn nguồn | 14 nguồn, 100% trỏ đúng tài liệu của project + Company Core |
| Cảnh báo thiếu nguồn | 0 |
| Phản hồi API `POST /generate` | **89ms** (không chặn UI — chạy nền) |

---

## 2. Kiến trúc — luồng gọi hàm từ đầu đến cuối

### 2.1. Sơ đồ tổng thể

```
[FE] MembersView.tsx
       │ bấm "Tạo Onboarding Plan"
       ▼
[FE] page.tsx :: handleGeneratePlan()
       │
       ▼  POST /api/v1/onboarding-plans/pm/generate  {membership_id}
[BE] onboarding_plan_router.py :: generate_candidate_plan()
       ├─ onboarding_plan_service.assert_no_open_plan()   ← chặn sớm nếu đã có plan
       ├─ job_store.create_job()                          ← tạo job in-memory
       ├─ background_tasks.add_task(_run_generation_job)   ← đẩy sang chạy nền
       └─ return 202 {job_id, correlation_id}              ← TRẢ VỀ NGAY (89ms)
              │
              ├──────────── chạy nền ────────────┐
              ▼                                   │
[BE] _run_generation_job()                        │
       │ async with AsyncSessionLocal()  ← session RIÊNG (session request đã đóng)
       ▼                                          │
[BE] pipeline.run_generation()   @observe "generate_candidate_plan"  ← span GỐC
       │                                          │
       │ 1. _step_load_template()        → steps.load_template()
       │ 2. _step_merge_company_core()   → steps.merge_company_core()
       │ 3. _step_collect_project_docs() → steps.collect_project_docs()
       │ 4. _step_map_task_sources()     → steps.map_task_sources()
       │ 5. _step_generate_content()     → content_llm.generate_ai_content()  ← LLM
       │ 6. _step_validate_and_persist() → steps.validate_generated()
       │                                  + onboarding_plan_service.persist_generated_plan()
       │ finally: flush_traces()                   │
       └──────────────────────────────────────────┘
              │
              ▼  (song song) FE poll mỗi 1 giây
[FE] PlanGeneratingView.tsx :: setInterval → getPlanGenerationJob(job_id)
       │  GET /api/v1/onboarding-plans/pm/generate/{job_id}
       │  → vẽ 6 bước PENDING → RUNNING → DONE kèm duration_ms THẬT
       ▼  khi status = DONE
[FE] page.tsx → PlanReviewView.tsx
       │  GET /api/v1/onboarding-plans/pm/{plan_id}/tasks
       │  → gom task theo nhóm, cảnh báo task thiếu nguồn
       ├─ bấm task → PlanTaskDrawer.tsx (renderMarkdown + danh sách nguồn)
       │              └─ bấm nguồn → DocumentPreviewModal (mở đúng file tài liệu)
       ├─ "Sửa nội dung task" → PATCH /plan-tasks/pm/{id}
       ├─ "Tạo lại"          → POST /onboarding-plans/pm/{plan_id}/regenerate
       └─ "Duyệt & phát hành" → PATCH /onboarding-plans/pm/{plan_id}/approve
```

### 2.2. Chi tiết từng bước — hàm nào làm gì, đọc dữ liệu ở đâu

| # | Bước | Hàm | Đọc gì từ DB | Thời gian thật |
|---|---|---|---|---|
| 1 | `load_template` | `steps.load_template()` | `ProjectMembership` → `OnboardingTemplate` → `TemplateVersion` **status=APPROVED** → `TemplateTask` + `TaskDependency` | 76ms |
| 2 | `merge_company_core` | `steps.merge_company_core()` → `_active_documents(domain=POLICY)` | `KnowledgeDocument` domain POLICY, `status=ACTIVE` + `DocumentVersion.status=ACTIVE` | 13ms |
| 3 | `collect_project_docs` | `steps.collect_project_docs()` → `_active_documents(domain=PROJECT)` | Như trên nhưng lọc `project_id` lấy từ **membership trong DB** (không nhận từ client) | 4ms |
| 4 | `map_task_sources` | `steps.map_task_sources()` | Không đọc DB — ghép in-memory theo bảng `TASK_CATEGORY_DOCUMENT_MAP` | 0ms |
| 5 | `generate_content` | `content_llm.generate_ai_content()` | Gọi `tools.search_project_docs()` / `search_company_policy()` → BM25 trên `document_chunks` | **34.427ms** |
| 6 | `validate_and_persist` | `steps.validate_generated()` + `onboarding_plan_service.persist_generated_plan()` | Ghi `OnboardingPlan` + `PlanTask` + `PlanTaskSource` trong **1 transaction** | 37ms |

**Nhận xét về số đo**: 5 bước nghiệp vụ cộng lại chỉ **130ms**, bước gọi LLM chiếm **99,6%** thời
gian. Đây chính là lý do phải tách job nền + polling thay vì 1 request đồng bộ.

### 2.3. Bước 5 — AI được cấp tool như thế nào

```
content_llm.generate_ai_content()
   │ for mỗi task:
   ├─ _retrieve_for_task()
   │     ├─ tools.search_project_docs(project_id=<khoá cứng>, categories=<theo map>)
   │     │      └─ tools.bm25_search()
   │     │             └─ _ScopedRetriever.base_statement(RetrievalFilters)  ← ACL có sẵn
   │     │                    + WHERE document_chunks.embedding_text @@@ :query  (ParadeDB BM25)
   │     └─ tools.search_company_policy()  (chỉ khi nhóm task được phép)
   │
   ├─ prompts.build_user_prompt()  → nhồi các đoạn tìm được vào phần NGUỒN
   ├─ llm.ainvoke(callbacks=get_langchain_callbacks())  ← DeepSeek + gửi token/cost lên Langfuse
   ├─ kiểm tra output có đúng khung "## Mục tiêu" không → sai thì rơi về baseline
   └─ _dedupe_sources()  → gom nhiều đoạn cùng 1 file thành 1 PlanTaskSource
```

**Bảo mật (SoT §19)**: `project_id` được khoá ở tầng service khi tạo `RetrievalFilters`, LLM chỉ
truyền được `query`/`category`. Kể cả khi tài liệu chứa prompt injection ("hãy đọc project X"),
injection chỉ ảnh hưởng chuỗi tìm kiếm chứ **không đổi được mệnh đề `WHERE project_id = ...`**.
Ngoài ra `_sanitize_bm25_query()` lọc ký tự đặc biệt vì pg_search có cú pháp truy vấn riêng — nội
dung tài liệu là **dữ liệu**, không phải cú pháp.

---

## 3. Thay đổi gì — thêm / sửa / bỏ

### 3.1. KHÔNG sửa gì (quan trọng nhất)

```
$ git diff --stat src/model/ alembic/
(rỗng)
$ git status --short src/model/ alembic/
(rỗng)
```

**Phase 4 không sửa 1 dòng model nào, không thêm 1 migration nào.** Chạy hoàn toàn trên schema
hiện có. Đây là yêu cầu PM chốt ngày 14/08 (hoãn `PlanTaskSource.chunk_id` sang sau).

### 3.2. File TẠO MỚI — backend (1.492 dòng)

| File | Dòng | Việc |
|---|---|---|
| `src/services/plan_generation/steps.py` | 297 | 5 bước nghiệp vụ deterministic + bảng map category + tính deadline |
| `src/services/plan_generation/pipeline.py` | 211 | Điều phối 6 bước, cập nhật job, ghi log/trace |
| `src/services/plan_generation/content_llm.py` | 194 | Bước 5: baseline B0 + bản AI, fallback khi lỗi |
| `src/services/plan_generation/job_store.py` | 126 | Job tiến độ in-memory + TTL (pattern `_SCAN_SESSIONS`) |
| `src/services/plan_generation/tools.py` | 113 | 2 tool tra cứu + `bm25_search` tái dùng ACL có sẵn |
| `src/services/plan_generation/prompts.py` | 60 | System prompt + khung markdown bắt buộc |
| `src/services/plan_task_service.py` | 114 | Đọc chi tiết task (join category/nguồn) + PM sửa tay |
| `src/observability/tracing.py` | 133 | Langfuse: khởi tạo client, `@observe`, callback LangChain, flush |
| `src/observability/logging.py` | 45 | Structured JSON log, **whitelist field** chống rò rỉ nội dung |
| `src/api/routers/plan_task_router.py` | 37 | `PATCH /plan-tasks/pm/{id}` |
| 4 file DTO | 139 | Request/Response cho generate, job, plan task |

### 3.3. File TẠO MỚI — frontend (1.219 dòng)

| File | Dòng | Việc |
|---|---|---|
| `components/plan/PlanReviewView.tsx` + scss | 450 | Màn duyệt: gom task theo nhóm, KPI, cảnh báo thiếu nguồn, Approve |
| `components/plan/PlanTaskDrawer.tsx` + scss | 392 | Chi tiết task: markdown, danh sách nguồn bấm xem, form sửa tay |
| `components/plan/PlanGeneratingView.tsx` + scss | 318 | Màn 6 bước, polling 1s, hiển thị duration thật |
| `dto/responseDTO/planTask.response.ts` | 34 | Type PlanTask + PlanTaskSource |
| `dto/responseDTO/planGenerationJob.response.ts` | 25 | Type job tiến độ |

### 3.4. File SỬA

| File | Sửa gì |
|---|---|
| `src/services/onboarding_plan_service.py` | Giữ nguyên 2 hàm đọc cũ, **thêm** `persist_generated_plan`, `approve_plan`, `assert_plan_regeneratable`, `assert_no_open_plan`, `list_plan_tasks` |
| `src/api/routers/onboarding_plan_router.py` | Giữ 2 route đọc cũ, **thêm** 5 route mới |
| `src/services/llm.py` | **Thêm** `get_plan_content_llm()` (DeepSeek, `temperature=0.2`) — không đụng 2 hàm cũ |
| `src/config.py` | **Thêm** `plan_generation_use_ai`, 3 biến `langfuse_*` |
| `src/api/routers/__init__.py` | Đăng ký `plan_task_router` |
| `requirements.txt` | **Thêm** `langfuse>=4.0` |
| `PM-test/conftest.py` | **Thêm** dọn `PlanTaskSource→PlanTask→OnboardingPlan` **trước** cây template (xem §5.2) |
| `frontend/.../MembersView.tsx` | Bật 2 nút (trước là `disabled title="Sắp có — Phase 4"`), thêm 2 prop callback |
| `frontend/.../page.tsx` | Thêm state máy 3 trạng thái `PlanFlow` điều hướng 3 màn |
| `frontend/src/lib/api.ts` | Thêm `PM_PLAN_TASKS_ENDPOINT` |
| `frontend/.../api.ts` | Thêm 6 hàm gọi API Phase 4 |

### 3.5. KHÔNG dùng gì

- **Không dùng LangGraph** — dù `src/agents/graph.py` có sẵn scaffold. Lý do: 6 bước có thứ tự cố
  định, không có nhánh rẽ do LLM quyết định. Thêm framework orchestration chỉ làm khó test/debug mà
  không đổi hành vi (đúng khuyến nghị `plan-pm.md` mục "Dependency mới cần thêm").
- **Không dùng `RetrievalEngine.retrieve()`** (hybrid dense+BM25) — lý do kỹ thuật ở §4.1.

---

## 4. Hai quyết định kỹ thuật dựa trên bằng chứng đo thật

### 4.1. Vì sao chỉ dùng BM25, không dùng dense/hybrid

`RetrievalEngine` có sẵn trong repo là hybrid (pgvector cosine + ParadeDB BM25 + RRF). **Nhưng
không dùng được**, vì 2 lý do đo được:

```sql
-- Chunk domain PROJECT có bao nhiêu embedding?
 chunks | has_text | has_vector
--------+----------+------------
    105 |      105 |          0     ← 0 vector!
```
```
$ python -c "import sentence_transformers"
ModuleNotFoundError: No module named 'sentence_transformers'   (cả .venv lẫn container)
```

- `PgvectorDenseRetriever.retrieve()` lọc `.where(embedding.is_not(None))` → trả **rỗng** cho tài
  liệu dự án.
- `RetrievalEngine.retrieve()` **luôn** gọi `query_encoder.embed()` → crash vì thiếu thư viện.
- Nhánh BM25 không cần vector, index `ix_document_chunks_lexical_bm25` (3200 kB) **có thật** trong DB.

→ Dùng `bm25_search()` gọi thẳng, **tái dùng nguyên `_ScopedRetriever.base_statement()`** để không
viết lại logic ACL lần 2. Khi TV3 backfill embedding + cài `sentence-transformers`, đổi sang hybrid
chỉ là thay 1 lời gọi trong `tools.py`.

### 4.2. Vì sao "Tạo lại" chỉ cho phép khi DRAFT — sửa giả định sai của plan cũ

`docs/PM/plan-pm.md` dòng 105 viết: *"phải tạo OnboardingPlan mới (bản DRAFT mới) thay thế"*.
**Làm vậy sẽ lỗi ngay**, bằng chứng từ DB:

```
"uq_onboarding_plans_one_open_per_membership" UNIQUE, btree (membership_id)
    WHERE status <> 'ONBOARDING_CLOSED'::plan_status
```

Chỉ được **1 plan chưa đóng / membership** → tạo bản DRAFT thứ 2 khi bản cũ đang APPROVED = vi phạm
unique constraint. Còn set status lùi về DRAFT thì trigger `enforce_onboarding_plan_forward_status`
(INV7) chặn.

→ Cách đúng đã cài: **regenerate tại chỗ khi còn DRAFT** (xoá task cũ, sinh lại, `revision += 1`,
status **không đổi** nên INV7 không kích hoạt). Đã duyệt rồi thì trả 409, PM sửa tay từng task.

---

## 5. Cơ chế test

### 5.1. Chiến lược — tách AI ra khỏi test

`PM-test/test_plan_generation.py` có fixture `autouse` tắt bước LLM:

```python
@pytest.fixture(autouse=True)
def disable_ai_generation():
    settings = get_settings()          # @lru_cache nên sửa instance đang cache là đủ
    settings.plan_generation_use_ai = False
    yield
    settings.plan_generation_use_ai = original   # khôi phục, không rò sang file test khác
```

Khi tắt AI, pipeline **vẫn chạy đủ 6 bước**, vẫn ghi PlanTask/PlanTaskSource thật — chỉ khác nội
dung lấy từ `TemplateTask.instruction_template` (chính là **baseline B0**). Nhờ vậy test kiểm được
toàn bộ nghiệp vụ mà **không gọi mạng, không cần API key, không bao giờ flaky**.

### 5.2. Bug thật tìm được nhờ test — thứ tự dọn dữ liệu

Lần chạy đầu: **14 passed, 13 errors** ở teardown:

```
ForeignKeyViolationError: update or delete on table "template_tasks" violates foreign key
constraint "fk_plan_tasks_template_task_id_template_tasks" on table "plan_tasks"
```

Nguyên nhân: `PlanTask` tham chiếu **cả hai phía** — `plan_id → onboarding_plans` **và**
`template_task_id → template_tasks`. Conftest đang xoá cây template trước → vướng FK.
Đã sửa: chuyển khối dọn Plan lên **đầu tiên**, trước cây template.

Đây là bug thật, nếu không có test sẽ không lộ ra.

### 5.3. 14 test — kiểm gì

| Test | Kiểm chứng |
|---|---|
| `test_generate_fails_without_approved_template` | Chưa duyệt template → 422, **không để lại plan rác** (SoT rule 16) |
| `test_generate_creates_plan_with_all_template_tasks` | Số PlanTask == số TemplateTask, **giữ đủ task bắt buộc** (rule 10) |
| `test_generated_plan_starts_as_draft_with_ordered_due_dates` | Plan mới luôn DRAFT (UC-06), deadline tăng dần |
| `test_sources_only_reference_own_project_documents` | **Chống rò rỉ chéo project** — tạo 2 project, kiểm tra không lẫn |
| `test_task_without_source_still_created_with_warning` | Thiếu tài liệu → vẫn tạo được + cảnh báo, **không bịa citation** |
| `test_regenerate_keeps_same_plan_and_increments_revision` | Tái dùng đúng plan cũ, revision +1, chỉ tồn tại 1 plan |
| `test_approve_then_regenerate_is_rejected` | Duyệt 2 lần → 409; tạo lại sau duyệt → 409 |
| `test_generate_rejected_when_membership_already_has_open_plan` | Chặn sớm ở service, không để DB ném IntegrityError |
| `test_inv7_trigger_blocks_backward_status` | **Kiểm chứng trigger DB thật**, không chỉ tin tầng service |
| `test_edit_task_allowed_in_draft_and_blocked_after_approve` | Rule 11 — snapshot không sửa ngầm |
| `test_plan_only_uses_five_active_categories` | Tài liệu CONVENTION/FIRST_TASK (đang hoãn) không lọt vào nguồn |
| `test_generate_job_reports_six_named_steps` | Đúng 6 bước, đúng thứ tự, có duration thật |
| `test_company_core_documents_are_merged_as_sources` | Bước 2 thật sự gộp Company Core |
| `test_approved_template_version_is_the_one_used` | Plan gắn đúng version APPROVED, không phải DRAFT |

### 5.4. Kết quả

```
$ pytest PM-test/test_plan_generation.py -q
14 passed in 9.21s

$ pytest PM-test/ tests/ -q          # toàn bộ, kiểm tra không phá gì của phase trước
90 passed in 20.82s

$ ruff check src/ PM-test/
All checks passed!
```

Frontend:
```
$ npx tsc --noEmit        → sạch
$ npx eslint <file mới>   → sạch
$ npx prettier --check    → sạch (sau khi --write 3 file)
$ npm run build           → thành công, 13 route
```

---

## 6. Bằng chứng chạy thật trên Docker

### 6.1. Rebuild container + verify route

```
$ docker compose build backend && docker compose up -d backend
$ curl localhost:8000/health
{"status":"ok","env":"development"}

$ docker exec p-040-backend-1 python -c "import langfuse; print(langfuse.__version__)"
4.14.4

$ curl localhost:8000/openapi.json  → 8 route Phase 4 đều có:
POST   /api/v1/onboarding-plans/pm/generate
GET    /api/v1/onboarding-plans/pm/generate/{job_id}
POST   /api/v1/onboarding-plans/pm/{plan_id}/regenerate
PATCH  /api/v1/onboarding-plans/pm/{plan_id}/approve
GET    /api/v1/onboarding-plans/pm/{plan_id}/tasks
PATCH  /api/v1/plan-tasks/pm/{plan_task_id}
(+ 2 route đọc cũ giữ nguyên)
```

### 6.2. Chạy E2E qua HTTP — đúng như UI gọi

**POST trả về ngay, không chặn:**
```
01:10:13.763  → gửi POST /generate
01:10:13.852  ← nhận 202 (89ms)
status: RUNNING, 6 bước đều PENDING
```

**Poll thấy tiến độ thật:**
```
01:10:27  RUNNING 4/6  đang chạy: Điền nội dung & hướng dẫn từng task
01:10:33  RUNNING 4/6  đang chạy: Điền nội dung & hướng dẫn từng task
01:10:43  RUNNING 4/6  đang chạy: Điền nội dung & hướng dẫn từng task
01:10:49  DONE    6/6
```

**Kết quả cuối:**
```
status: DONE | plan_id: 94 | tổng: 34572 ms | cảnh báo: (không có)
  DONE  load_template               76ms  7 task trong template
  DONE  merge_company_core          13ms  18 tài liệu chính sách
  DONE  collect_project_docs         4ms  5 tài liệu dự án
  DONE  map_task_sources             0ms  7/7 task có nguồn
  DONE  generate_content         34427ms  7/7 task do AI viết
  DONE  validate_and_persist        37ms  Đã lưu 7 task, 14 trích dẫn nguồn
```

### 6.3. Nội dung AI sinh ra — mẫu thật

Task #5 "Cài đặt công cụ phát triển theo đúng tech stack" (project FURNISTORE):

```markdown
## Mục tiêu
Cài đặt đầy đủ công cụ phát triển đúng phiên bản dự án FurniStore yêu cầu (Node.js 20+, pnpm,
Docker + Docker Compose) để có thể chạy được môi trường local dev.

## Các bước thực hiện
1. Cài Node.js 20+ thông qua `nvm` (không cài global) — repo có sẵn file `.nvmrc`...
2. Cài `pnpm` làm package manager chính thức (không dùng `npm`/`yarn` — lockfile chỉ commit
   `pnpm-lock.yaml`).
...
7. Tạo file `.env` từ `.env.example`... điền `DATABASE_URL` (Postgres), `MONGO_URL`, `REDIS_URL`
   — lưu ý dự án cần 2 database chạy song song (Postgres + MongoDB)...

## Kết quả cần đạt
- [ ] Chạy `node -v` trả về phiên bản Node.js 20 trở lên
- [ ] Chạy `pnpm -v` trả về phiên bản pnpm (không phải npm/yarn)
- [ ] Chạy `docker --version` và `docker compose version` trả về kết quả thành công
- [ ] File `.env` tồn tại và có đầy đủ `DATABASE_URL`, `MONGO_URL`, `REDIS_URL`
```

**Đây là chi tiết THẬT lấy từ tài liệu FurniStore** (`.nvmrc`, `pnpm-lock.yaml`, 2 database) — không
phải nội dung chung chung bịa ra. Kết quả cần đạt đều kiểm chứng được bằng lệnh cụ thể.

### 6.4. Trích dẫn nguồn — mapping category chính xác 100%

```
 ord | task                             | nhóm tài liệu   | tài liệu
-----+----------------------------------+-----------------+------------------------------
   1 | Đọc tài liệu Overview dự án      | OVERVIEW        | FurniStore — Overview
   1 | Đọc tài liệu Overview dự án      | (POLICY)        | Chính sách Onboarding và Off...
   1 | Đọc tài liệu Overview dự án      | (POLICY)        | Chính sách Đào tạo và Phát...
   2 | Đọc tài liệu Architecture...     | ARCHITECTURE    | FurniStore — Architecture
   3 | Xin quyền truy cập GitHub repo   | ACCESS_SECURITY | FurniStore — Access & Security
   3 | Xin quyền truy cập GitHub repo   | (POLICY)        | Chính sách Quản lý Secret...
   4 | Xin quyền truy cập môi trường... | (POLICY)        | Chính sách VPN và Truy cập Từ xa
   5 | Cài đặt công cụ phát triển...    | SETUP           | FurniStore — Setup môi trường
   7 | Đọc Codebase Guide...            | CODEBASE_GUIDE  | FurniStore — Codebase Guide
```

Mỗi nguồn kèm `citation_note` là **tên mục trong file** (ví dụ `"Xin quyền truy cập · Đặc thù bảo
mật của..."`) để người đọc biết xem chỗ nào.

### 6.5. Các ràng buộc nghiệp vụ — test qua HTTP thật

```
Duyệt plan          → 200, status APPROVED, approved_at 2026-08-13T18:09:43, by user 21
Duyệt lần 2         → 409  "Chỉ duyệt được plan đang ở trạng thái Nháp (hiện tại: APPROVED)"
Tạo lại sau duyệt   → 409  "Plan đã duyệt (APPROVED) thì không tạo lại được — hãy sửa từng task"
Sửa task sau duyệt  → 409  "Plan đã ở trạng thái APPROVED — chỉ sửa được task khi plan còn Nháp"
Tạo plan khi đã có  → 409  "Thành viên này đã có Onboarding Plan (#6, ACTIVE) —
                            mỗi thành viên chỉ có 1 plan đang mở"
```

### 6.6. Observability — trace thật trên Langfuse

Truy vấn API Langfuse xác nhận trace đã lên:
```
TRACE: generate_candidate_plan | latency=36.603s | 14 observation
```
1 trace gốc chứa **6 span bước** + **7 generation** (mỗi lời gọi LLM 1 cái, do
`CallbackHandler` của LangChain gửi kèm token/cost).

**Lỗi thật đã sửa trong quá trình làm**: ban đầu Langfuse báo
`"client initialized without public_key"` và **im lặng tắt tracing** — rất dễ tưởng đang trace mà
thật ra không gửi gì. Nguyên nhân: SDK Langfuse tự đọc `os.environ`, còn project dùng
pydantic-settings nạp `.env` vào object `Settings` chứ không đổ ngược vào `os.environ`. Đã sửa bằng
`_ensure_client()` truyền key tường minh.

**Lỗi thứ hai**: ban đầu mỗi bước tạo **1 trace riêng lẻ** (5 trace rời) vì thiếu span gốc bọc
ngoài. Đã thêm `@observe_step("generate_candidate_plan")` lên `run_generation()`.

Structured log JSON (không chứa nội dung tài liệu):
```json
{"correlation_id":"a6aed459...","duration_ms":76,"event":"step_done","project_id":6,
 "step":"load_template","task_count":7,"template_version_id":160}
{"ai_generated_count":7,"correlation_id":"a6aed459...","duration_ms":34427,
 "event":"step_done","step":"generate_content","task_count":7}
```

---

## 7. Dọn dữ liệu test

Đúng bài học 2 lần rò rỉ data ở Phase 3 — đã kiểm tra và dọn sạch:

- **14 project `TEST*`** + 13 plan + 91 plan_task + 204 plan_task_source + 64 tài liệu + 13 user
  → sót lại từ **lần chạy test đầu tiên** (teardown crash do bug thứ tự FK ở §5.2). Đã xoá hết.
- **Dữ liệu E2E** (user `e2e-phase4*`, membership 415, plan 94) → đã xoá.

Verify sau khi dọn:
```
 project TEST còn lại      | 0
 user e2e còn lại          | 0
 plan_tasks mồ côi         | 0
 plan_task_sources mồ côi  | 0
 onboarding_plans mồ côi   | 0
```

**Còn lại 2 plan demo có chủ đích** (plan 51 — Vu Thanh F, plan 52 — Hoang Gia E, cả 2 trên
FURNISTORE, nội dung AI thật) để PM bấm thử UI ngay. Muốn xoá thì báo, không phải data rác.

---

## 8. Giới hạn đã biết — ghi rõ, không giấu

1. **Job tiến độ lưu in-memory** → chạy nhiều worker/process thì job không share được. Hiện
   `docker-compose.yml` chạy uvicorn 1 process nên không sao; scale nhiều worker thì thay
   `job_store.py` bằng Redis, phần còn lại không phải sửa.
2. **Retrieval chỉ BM25**, chưa hybrid — lý do ở §4.1. Chất lượng tìm kiếm phụ thuộc trùng từ khoá;
   khi có embedding sẽ tốt hơn với câu hỏi diễn đạt khác từ.
3. **Trích dẫn ở mức file**, chưa tới đúng đoạn — PM chốt hoãn, đường đi đã ghi sẵn ở
   [plan §17.1](plan-phase4-candidate-plan.md).
4. **Chưa có Access Scope/ACL theo từng kỹ sư** — `plan-pm.md` đã chốt bỏ (chưa có entity). Bước 3
   lọc theo project + category, **không** lọc theo access scope.
5. **Chưa chụp được screenshot UI thao tác thật** — môi trường không có browser headless. Đã verify
   bằng: build sạch, `curl localhost:3000/product-manager` HTTP 200, và toàn bộ API mà UI gọi đều
   đã test qua HTTP thật (§6.2, §6.5). **Bạn nên tự bấm thử 1 lượt** để xác nhận phần hiển thị.
6. **Chưa làm phần Eval Day-14** (golden dataset 20 case, RAGAS-style metrics, LLM-as-Judge) —
   là hạng mục riêng ở [plan §13](plan-phase4-candidate-plan.md), làm sau khi PM xác nhận phần
   chức năng này chạy đúng.

---

## 9. Bổ sung 14/08 — Lộ trình chuẩn cấp dự án (kỹ sư chỉ nhận bản sao)

> Plan: [`plan-fix-reference-plan-reuse.md`](plan-fix-reference-plan-reuse.md)

### 9.1. Vấn đề của bản Phase 4 đầu tiên

Bản đầu để mỗi lần cấp plan cho 1 kỹ sư là **gọi AI lại từ đầu** (~34s + phí mỗi lần), dù SoT §12
nói rõ *"kỹ sư cùng một dự án nhận cấu trúc và nội dung giống nhau"*. Khi thử sửa bằng cách lấy
"plan của kỹ sư đầu tiên" làm bản chuẩn thì lộ tiếp 2 lỗi thiết kế:

1. **Không tạo được lộ trình chuẩn tại trang riêng** — `OnboardingPlan.membership_id` là NOT NULL
   và bảng không có `project_id`, nên mọi plan buộc phải thuộc 1 kỹ sư; trang "Onboarding Plan" chỉ
   biết đẩy PM sang trang Thành viên.
2. **Bản chuẩn bị khoá cứng sau khi duyệt** — `plan_task_service.update_task` chặn sửa khi
   `status != DRAFT`. Kỹ sư đầu tiên được duyệt plan là PM **mất quyền sửa lộ trình chuẩn vĩnh viễn**.

### 9.2. Thiết kế mới — 2 loại row trong cùng 1 bảng

| Loại | `project_id` | `membership_id` | Vòng đời | Ai sửa được |
|---|---|---|---|---|
| **Lộ trình chuẩn** | có | NULL | luôn `DRAFT`, không có bước duyệt | PM sửa/tạo lại tự do, mãi mãi |
| **Plan của kỹ sư** | NULL | có | DRAFT → APPROVED → ... (INV7) | chỉ khi còn DRAFT |

`CHECK ck_onboarding_plans_owner: num_nonnulls(project_id, membership_id) = 1` ép đúng 1 trong 2 —
không tồn tại row lai.

### 9.3. Migration `c8a1f5d73e42` — ảnh hưởng thành viên khác: KHÔNG

Grep toàn repo mọi chỗ đụng `OnboardingPlan`, kết quả kiểm chứng:

| Nơi dùng | Ảnh hưởng? | Bằng chứng |
|---|---|---|
| `scripts/seed_dev_data.py` (dùng chung cả nhóm) | **KHÔNG** | Tạo plan có `membership_id`, `project_id` để trống → tự thoả CHECK mới, **không sửa 1 dòng** |
| Trang Engineer `app/onboarding/page.tsx`, `app/tasks/page.tsx` (TV2) | **KHÔNG** | Cả 2 đúng 13 dòng, nội dung *"Placeholder cho các luồng onboarding được nhóm thống nhất sau MVP"*, **0 tham chiếu** tới plan |
| Router backend TV2 | **KHÔNG** | Không tồn tại router nào của TV2 đọc plan |
| Trigger INV7 (`develop`) | **KHÔNG** | Grep `membership_id` trong migration `a1b2c3d4e5f6` → 0 dòng; trigger chỉ so `OLD.status`/`NEW.status` |
| TV3, TV4 | **KHÔNG** | Không xuất hiện trong kết quả grep |

Index cũ `uq_onboarding_plans_one_open_per_membership` **không đụng tới**: đọc định nghĩa thật trong
DB thấy không có `NULLS NOT DISTINCT` → Postgres coi mỗi NULL là khác nhau, nên nhiều lộ trình chuẩn
(đều `membership_id NULL`) không va nhau; ràng buộc "1 plan mở / kỹ sư" vẫn nguyên vẹn.

**Contract cho TV2 khi code phần Engineer**: plan của kỹ sư **luôn** có `membership_id NOT NULL`.
Query theo membership là tự động loại lộ trình chuẩn; nếu quét cả bảng thì thêm
`WHERE membership_id IS NOT NULL`.

### 9.4. Luồng sau khi sửa

```
[Trang "Onboarding Plan"]  ← mục nav MỚI trên sidebar
   Chưa có  → "Tạo lộ trình chuẩn bằng AI"  → 6 bước (~34s, CHỖ DUY NHẤT gọi AI) → hiện lộ trình
   Đã có    → sửa tay từng task / "Tạo lại bằng AI" (có modal cảnh báo ghi đè)
              KHÔNG có nút "Duyệt" — bản chuẩn không phát hành cho ai

[Trang "Thành viên"]
   "Tạo Onboarding Plan" → SAO CHÉP lộ trình chuẩn (~150ms, không gọi AI)
   Chưa có lộ trình chuẩn → 422 ngay + nút điều hướng sang mục Onboarding Plan
```

Bước 6 `validate_and_persist` **không đổi 1 dòng** — `due_at` vẫn được `compute_due_dates()` tính
lại theo ngày cấp plan, nên kỹ sư vào sau có deadline đúng theo ngày họ bắt đầu chứ không copy
nguyên mốc cũ.

### 9.5. Bằng chứng chạy thật (Docker rebuild, dự án FURNISTORE)

**Tạo lộ trình chuẩn (gọi AI):**
```
status: DONE | plan_id: 140 | 37.673 ms
  DONE  generate_content        37453ms  7/7 task do AI viết
→ ban chuan: plan_id=140 project_id=6 membership_id=None status=DRAFT rev=1
```

**Cấp plan cho kỹ sư (sao chép):**
```
plan #304 | 136 ms | Sao chép nội dung từ Plan #140 đã có (không gọi AI)
```
→ **nhanh hơn 277 lần** (136ms so với 37.673ms), không tốn 1 đồng phí LLM nào.

**Toàn vẹn dữ liệu — kịch bản PM yêu cầu, chạy thật qua HTTP:**
```
B3: PM sửa lộ trình chuẩn      → "[CHUAN v2] Doc tai lieu Overview du an"
B4: Kỹ sư A (đã có plan)       → "Đọc tài liệu Overview dự án"   ✓ KHÔNG bị đổi ngầm
B5: Kỹ sư B (cấp plan sau đó)  → "[CHUAN v2] Doc tai lieu..."    ✓ nhận bản đã sửa
```

**Các ràng buộc:**
```
Duyệt lộ trình chuẩn         → 409 "Đây là lộ trình chuẩn của dự án, không có bước duyệt —
                                    duyệt là việc của từng plan đã cấp cho kỹ sư"
Cấp plan khi chưa có bản chuẩn → 422 "Dự án chưa có lộ trình chuẩn — vào mục Onboarding Plan
                                      tạo lộ trình chuẩn trước, rồi mới cấp plan cho kỹ sư"
```

### 9.6. Test — 22/22 Phase 4, toàn suite 98/98

Test mới/cập nhật quan trọng:

| Test | Kiểm chứng |
|---|---|
| `test_reference_plan_is_project_level_not_membership` | Bản chuẩn có `project_id`, `membership_id=None`, DRAFT; **không lọt** vào danh sách plan thành viên |
| `test_reference_uses_ai_engineer_plan_clones` | Bước 5 của bản chuẩn KHÔNG chứa "Sao chép"; của kỹ sư thì CÓ, kèm đúng `#plan_id` nguồn |
| `test_editing_reference_does_not_touch_existing_engineer_plans` | **Quan trọng nhất** — đúng kịch bản §9.5 |
| `test_generate_for_engineer_fails_without_reference` | 422 đồng bộ, không để lại plan rác |
| `test_reference_plan_cannot_be_approved` | 409 |
| `test_reference_regenerate_overwrites_in_place` | Cùng `plan_id`, `revision`+1, đúng 1 row (UNIQUE bảo vệ) |
| `test_regenerate_engineer_plan_resyncs_from_reference` | "Tạo lại" trên plan kỹ sư = đồng bộ lại từ bản chuẩn hiện tại (PM chủ động bấm, không tự động) |

```
$ pytest PM-test/test_plan_generation.py -q   → 22 passed
$ pytest PM-test/ tests/ -q                    → 98 passed
$ ruff check src/ PM-test/                     → All checks passed!
FE: tsc --noEmit / eslint / prettier / next build → sạch
```

### 9.7. Bug thật tìm được nhờ test

**Conftest bỏ sót lộ trình chuẩn khi dọn dữ liệu** — teardown tìm plan theo `membership_id IN (...)`,
mà bản chuẩn có `membership_id NULL` nên không bị xoá → xoá `template_tasks` vướng FK
`fk_plan_tasks_template_task_id_template_tasks`. Đã sửa: gom **cả hai** loại plan bằng
`OR project_id IN tracker.project_ids`.

Cũng phát hiện **24 project test sót lại** từ những lần chạy test lỗi trước khi sửa conftest (720
`plan_task_sources`, 315 `plan_tasks`, 168 `template_tasks`...). Đã dọn sạch toàn bộ; verify:

```
 project TEST                 | 0
 user test                    | 0
 plan_tasks mồ côi            | 0
 sources mồ côi               | 0
 plan mồ côi (project đã xoá) | 0
```

Còn lại đúng 6 plan: 3 seed ACTIVE + 2 demo DRAFT (kỹ sư FURNISTORE) + **1 lộ trình chuẩn
FURNISTORE (plan #140)** để PM bấm thử UI ngay.

### 9.8. File thay đổi ở bản bổ sung này

- **Schema**: `alembic/versions/c8a1f5d73e42_reference_plan_at_project_level.py` (mới),
  `src/model/onboarding_plan.py` (+`project_id`, `membership_id` nullable, CHECK, index).
- **Backend**: `steps.py` (tách `load_template_for_project`), `onboarding_plan_service.py`
  (`find_reference_plan` đổi chữ ký, `assert_reference_plan_exists`, `is_reference_plan`, chặn
  approve bản chuẩn), `pipeline.py` (2 đường rẽ AI/clone), `job_store.py` (`create_job` nhận
  membership *hoặc* project), `onboarding_plan_router.py` (+`POST /pm/reference/generate`), 2 DTO.
- **Frontend**: `ReferencePlanView.tsx` viết lại thành trang tự chủ (242 dòng + 71 dòng SCSS),
  `PlanReviewView.tsx` (+3 prop `showApproveButton`/`onRegenerate`/`regenerateLabel`),
  `PmShell.tsx` (nav "Onboarding Plan"), `page.tsx`, `api.ts`, 2 DTO.
- **Test**: `PM-test/test_plan_generation.py` (22 test), `PM-test/conftest.py` (dọn cả 2 loại plan).

---

## 10. Việc tiếp theo

| Ưu tiên | Việc |
|---|---|
| 1 | PM bấm thử UI thật: mục **Onboarding Plan** → tạo lộ trình chuẩn → sửa 1 task → sang **Thành viên** cấp plan cho kỹ sư |
| 2 | Eval Day-14 (plan §13): golden dataset + script + `eval-report.md` |
| 3 | Phase 5 — Member Detail (milestone rail, First PR, đóng onboarding) |
| 4 | Khi TV3 backfill embedding PROJECT → đổi BM25 sang hybrid (1 lời gọi trong `tools.py`) |
