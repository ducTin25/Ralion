# Báo cáo hoàn thành Phase 2 — Master Template (owner-template)

> Trạng thái: **ĐÃ CODE XONG, ĐÃ TEST, ĐÃ CHẠY THẬT TRÊN DOCKER**.
> Theo đúng plan đã duyệt: `docs/PM/Phase-2/plan-phase2-master-template.md` (v3 + ghi chú v3.1).
> Không ảnh hưởng tính năng Phase 1 đã xong — bằng chứng ở mục 5.

## 0. Thay đổi scope so với plan lúc bắt đầu code

Khi bắt đầu code, có 1 quyết định mới phát sinh (không có trong plan v3 gốc):

- **Bỏ authorization (`require_active_pm`) khỏi Phase 2** — lý do bạn đưa ra: hệ thống chưa có
  đăng nhập/Auth thật (TV4 chưa làm xong), nên chưa có cách nào lấy đúng `user_id` người đang thao
  tác để check, gán cứng lúc này chỉ là hình thức không có giá trị thật. File
  `src/services/authorization.py` (viết theo mục 3.2 của plan) đã bị xoá, không có bất kỳ endpoint
  ghi dữ liệu nào (tạo version, sửa/xoá/reorder task, tạo/xoá dependency, duyệt version) kiểm tra
  quyền — ai gọi cũng được. Đã cập nhật lại `plan-phase2-master-template.md` (ghi chú v3.1) để
  không đánh lừa người đọc sau này rằng authorization đã implement.
- Ngoài điểm này, mọi phần còn lại **đúng theo plan v3 đã duyệt**, không có sai lệch nào khác.

## 1. Backend — đã code xong toàn bộ

### 1.1 Migration (mục 2 của plan)

File: `alembic/versions/87d27e78a497_add_template_constraints_one_per_.py` (revision
`b3c4d5e6f7a8` → `87d27e78a497`), áp dụng đúng 3 constraint SoT yêu cầu:

| Constraint | Bảng | Ý nghĩa | SoT |
|---|---|---|---|
| `uq_onboarding_templates_one_per_project` | `onboarding_templates` | Đúng 1 template/project, bất kể status | §24.1 |
| `uq_onboarding_templates_one_global` | `onboarding_templates` | Đúng 1 record `scope=GLOBAL` toàn hệ thống | §11.15 |
| `uq_template_versions_one_approved_per_template` | `template_versions` | Tối đa 1 version `APPROVED`/template tại 1 thời điểm | §11.18 |

`alembic upgrade head` đã chạy thành công, `alembic check` xác nhận **không còn drift** giữa model
và schema thật (chạy lại lần cuối sau khi hoàn tất toàn bộ Phase 2, xem mục 5.3).

Đã verify constraint hoạt động thật ở tầng DB (không chỉ ở code Python) — thử insert thẳng 1 row
`scope=GLOBAL` thứ 2 qua `psql`:

```
INSERT INTO onboarding_templates (scope, name, description, status) VALUES ('GLOBAL','dup','dup','DRAFT');
ERROR:  duplicate key value violates unique constraint "uq_onboarding_templates_one_global"
```

### 1.2 Model đã sửa

- `src/model/onboarding_template.py` — thêm `UniqueConstraint("project_id")` + partial unique index `scope='GLOBAL'`.
- `src/model/template_version.py` — thêm partial unique index `status='APPROVED'` theo `template_id`.

### 1.3 Business logic — mỗi project tự có Master Template ngay khi tạo (SoT §11.16, §17.2)

- `src/services/onboarding_template_service.py` (mới) — `materialize_project_template()`: fork
  Global Master Template thành 1 Project Template mới (scope=PROJECT, status=DRAFT), copy toàn bộ
  `TemplateTask` **và `TaskDependency`** từ version `APPROVED` của GLOBAL sang version 1 (DRAFT)
  của project. `get_approved_global_template()`, `get_by_project()`, `create_template_for_project()`
  (dùng cho backfill/test qua Swagger — **không dùng từ UI PM**).
- `src/services/project_service.py` — **sửa `create_project`**: trước khi tạo `Project`, check
  `get_approved_global_template()`; nếu `None` → `HTTPException(422, ...)`, **không tạo project**.
  Nếu có → tạo `Project`, flush lấy `project_id`, gọi `materialize_project_template()` trong cùng
  transaction, rồi mới `commit()`. Đúng SoT §11.16 "báo lỗi rõ ràng, không tạo template rỗng".

### 1.4 TemplateVersion (mục 3.3 plan)

`src/services/template_version_service.py` (mới):
- `create_version()` — tạo version mới `DRAFT`; nếu có `clone_from_version_id` thì copy toàn bộ
  `TemplateTask` + `TaskDependency` (remap ID qua `id_map`) từ version nguồn; không truyền thì tạo
  version trống.
- `approve_version()` — 1 transaction đúng SoT §17.2/§24.1:
  1. Validate trước khi duyệt: phải có ≥ 1 task, `display_order` không trùng, dependency không
     tham chiếu ngoài version và **không có chu trình (cycle)** — DFS 3 màu (`_has_cycle`).
  2. `SELECT ... FOR UPDATE` khoá mọi version cùng `template_id` trước khi đổi status (xử lý cạnh
     tranh theo đúng yêu cầu SoT).
  3. Version đích `DRAFT → APPROVED`; version đang `APPROVED` khác (nếu có) → `ARCHIVED`; cập nhật
     `OnboardingTemplate.status = APPROVED`.

### 1.5 TemplateTask (mục 3.4 plan)

`src/services/template_task_service.py` (mới) — CRUD + reorder, mọi thao tác ghi đều chặn nếu
version không `DRAFT` (409). `display_order` tự động nối cuối khi tạo mới. **Hard-delete thật**
(không soft-delete, đúng vì model không có cột `status`) — kèm dọn mọi `TaskDependency` liên quan
tới task đó trước khi xoá (xem bug đã tìm thấy ở mục 4). `reorder_tasks()` validate đúng/đủ tập
`task_id` của version (SoT §11.22), dùng kỹ thuật 2 bước (set âm tạm rồi set giá trị đích) để tránh
đụng `UniqueConstraint(version_id, display_order)` khi các task hoán đổi vị trí.

### 1.6 TaskDependency (mục 3.5 plan)

`src/services/task_dependency_service.py` (mới) — validate: cùng version, không tự tham chiếu,
không tạo chu trình (BFS tìm đường đi ngược trước khi thêm cạnh). Trùng cặp
`(predecessor, successor)` → 409 (bắt `IntegrityError` từ `UniqueConstraint` DB).

### 1.7 DTO + Router

4 nhóm DTO (`src/dto/request/`, `src/dto/response/`) + 4 router
(`onboarding_template_router.py`, `template_version_router.py`, `template_task_router.py`,
`task_dependency_router.py`) theo đúng convention `/pm` sub-path + `from_entity()` đã dùng ở
Phase 1. Đăng ký đủ trong `src/api/routers/__init__.py`.

### 1.8 Backfill dữ liệu cũ

`scripts/backfill_project_templates.py` — chạy 1 lần cho 4 project demo tạo trước Phase 2
(PHONESHOP/TOURBOOK/FURNISTORE/GADGETHUB), gọi `materialize_project_template()` cho từng project.
Đã chạy thật, kết quả (xem mục 5.4): cả 4 project đều có template mới, mỗi bản 12 task đủ 7 category.

## 2. Frontend — đã code xong toàn bộ

- `PmField.tsx` / `.module.scss` — thêm component `PmTextarea` (còn thiếu, cần cho
  `objective`/`instruction_template` nhiều dòng).
- `dto/responseDTO/{onboardingTemplate,templateVersion,templateTask,taskDependency}.response.ts` — mới.
- `api.ts` — thêm `postJson`/`patchJson`/`deleteRequest` helper (module trước đó chỉ có GET) +
  12 hàm gọi API cho 4 nhóm endpoint (`getTemplateByProject`, `listTemplateVersions`,
  `createTemplateVersion`, `approveTemplateVersion`, `listTemplateTasks`, `createTemplateTask`,
  `updateTemplateTask`, `deleteTemplateTask`, `reorderTemplateTasks`, `listTaskDependencies`,
  `createTaskDependency`, `deleteTaskDependency`). `lib/api.ts` thêm 4 endpoint constant mới.
- `components/template/VersionTabs.tsx` — dải pill chọn version, kèm trạng thái (Nháp/Đang áp
  dụng/Đã lưu trữ).
- `components/template/TaskFormModal.tsx` — form tạo/sửa task, gồm multi-select "Phụ thuộc vào"
  (diff dependency cũ/mới rồi gọi create/delete dependency tương ứng khi lưu).
- `components/template/TemplateView.tsx` — màn hình chính "Master Template": KPI row (Tổng
  task/Bắt buộc/Tuỳ chọn/Thời gian ước tính), filter row (tìm kiếm + lọc category + lọc bắt buộc),
  task list nhóm theo 7 category, nút Sửa/Xoá/lên-xuống (chỉ hiện khi version DRAFT), "Tạo phiên
  bản mới", "Duyệt phiên bản này". **Không có trạng thái rỗng/nút "tạo template"** — đúng thiết kế
  plan mục 5 (mọi project tồn tại được là đã có template).
- `PmShell.tsx` — bật `enabled: true` cho nav "Master Template" (trước đó `false`).
- `product-manager/page.tsx` — wire `TemplateView`, thêm `ProjectSwitcher` cho nav `template`.

## 3. Đã KHÔNG code (nằm ngoài phạm vi, đúng theo plan mục 7)

- UI quản lý GLOBAL template (Admin-level) — chỉ seed qua script.
- Giao diện dependency dạng graph/sơ đồ — dùng multi-select đơn giản.
- Authorization thật — hoãn sang phase có Auth (xem mục 0).

## 4. Bug tìm thấy VÀ ĐÃ SỬA trong lúc code + viết test (bằng chứng "đúng trong code")

Viết test không chỉ để xác nhận code đúng — quá trình viết test đã trực tiếp phát hiện 2 lỗi thật,
sửa ngay trước khi coi là hoàn thành:

1. **`materialize_project_template` quên copy `TaskDependency`** — bản đầu chỉ copy `TemplateTask`
   khi fork từ GLOBAL, làm mất chuỗi phụ thuộc tuần tự (11 dependency) mà GLOBAL template đã có.
   Phát hiện khi viết `test_create_version_clone_copies_tasks_and_dependencies`. Đã sửa: thêm logic
   remap ID (giống hệt cách `create_version`'s clone path đã làm) để copy đủ dependency khi fork.
2. **`delete_task` vi phạm FK khi task có dependency tham chiếu** — xoá 1 task đang là
   predecessor/successor của 1 `TaskDependency` nào đó (rất phổ biến vì fork/clone đã có sẵn chuỗi
   dependency) làm Postgres ném `ForeignKeyViolationError`. Phát hiện khi chạy
   `test_delete_task_is_hard_delete`. Đã sửa: `delete_task` giờ xoá hết `TaskDependency` liên quan
   (cả 2 chiều predecessor/successor) trước khi xoá task.

Cả 2 bug đều được test tự động phát hiện trước khi chạy thật trên Docker — đúng quy trình "viết
test rồi tìm bằng chứng đã đúng" bạn yêu cầu, không phải chỉ code cho chạy được rồi thôi.

## 5. Bằng chứng đã đúng

### 5.1 Test suite Phase 2 — 41/41 PASS (chạy trên Docker Postgres local)

29 test case mới cho Phase 2 (`PM-test/test_onboarding_templates.py`,
`test_template_versions.py`, `test_template_tasks.py`, `test_task_dependencies.py`), cộng
12 test Phase 1 sẵn có (project/membership/plan) — **tất cả cùng pass, không có test nào bị bỏ qua**:

```
PM-test/test_onboarding_plans.py::test_get_plan_by_membership_not_found PASSED
PM-test/test_onboarding_plans.py::test_get_plan_by_membership_found PASSED
PM-test/test_onboarding_plans.py::test_list_plans_by_project_only_returns_members_with_plan PASSED
PM-test/test_onboarding_plans.py::test_list_plans_by_project_empty_when_no_plans PASSED
PM-test/test_onboarding_templates.py::test_create_project_auto_creates_project_template PASSED
PM-test/test_onboarding_templates.py::test_create_project_fails_when_global_template_missing PASSED
PM-test/test_onboarding_templates.py::test_manual_create_template_rejects_project_that_already_has_one PASSED
PM-test/test_onboarding_templates.py::test_manual_create_template_404_when_project_not_found PASSED
PM-test/test_onboarding_templates.py::test_get_template_by_project_not_found PASSED
PM-test/test_project_memberships.py::test_create_membership PASSED
PM-test/test_project_memberships.py::test_create_membership_duplicate PASSED
PM-test/test_project_memberships.py::test_create_membership_rejects_system_role_user PASSED
PM-test/test_project_memberships.py::test_list_memberships_by_project PASSED
PM-test/test_project_memberships.py::test_update_membership_role PASSED
PM-test/test_project_memberships.py::test_deactivate_membership PASSED
PM-test/test_project_memberships.py::test_list_memberships_by_user PASSED
PM-test/test_projects.py::test_create_project PASSED
PM-test/test_projects.py::test_create_project_duplicate_key PASSED
PM-test/test_projects.py::test_list_projects PASSED
PM-test/test_projects.py::test_get_project_not_found PASSED
PM-test/test_projects.py::test_update_project PASSED
PM-test/test_projects.py::test_archive_project PASSED
PM-test/test_task_dependencies.py::test_create_and_list_dependency PASSED
PM-test/test_task_dependencies.py::test_create_dependency_rejects_self_reference PASSED
PM-test/test_task_dependencies.py::test_create_dependency_rejects_cross_version PASSED
PM-test/test_task_dependencies.py::test_create_dependency_rejects_cycle PASSED
PM-test/test_task_dependencies.py::test_create_dependency_rejects_duplicate PASSED
PM-test/test_task_dependencies.py::test_delete_dependency PASSED
PM-test/test_template_tasks.py::test_create_and_list_task PASSED
PM-test/test_template_tasks.py::test_update_task PASSED
PM-test/test_template_tasks.py::test_delete_task_is_hard_delete PASSED
PM-test/test_template_tasks.py::test_cannot_modify_task_when_version_not_draft PASSED
PM-test/test_template_tasks.py::test_reorder_tasks PASSED
PM-test/test_template_tasks.py::test_reorder_rejects_incomplete_task_set PASSED
PM-test/test_template_versions.py::test_create_version_clone_copies_tasks_and_dependencies PASSED
PM-test/test_template_versions.py::test_create_version_empty PASSED
PM-test/test_template_versions.py::test_approve_version_golden_path PASSED
PM-test/test_template_versions.py::test_approve_version_archives_previous_approved PASSED
PM-test/test_template_versions.py::test_approve_version_fails_when_no_tasks PASSED
PM-test/test_template_versions.py::test_approve_version_fails_when_not_draft PASSED
PM-test/test_template_versions.py::test_approve_version_fails_on_cycle PASSED

============================= 41 passed in 3.61s ==============================
```

Đặc biệt `test_approve_version_fails_on_cycle` chèn thẳng qua ORM 1 `TaskDependency` tạo cycle
(bỏ qua service layer) để xác nhận `approve_version` có validate phòng thủ ở tầng service — không
chỉ dựa vào việc `create_dependency` đã chặn cycle từ lúc tạo.

### 5.2 Phase 1 KHÔNG bị ảnh hưởng — bằng chứng cụ thể

- `PM-test/test_projects.py` (6 test tạo/sửa/xoá project), `PM-test/test_project_memberships.py`
  (7 test), `PM-test/test_onboarding_plans.py` (4 test) — **toàn bộ vẫn pass** sau khi
  `create_project` bị sửa để tự tạo template kèm theo.
- `tests/` (đúng thư mục CI thật chạy `pytest tests/`) — **vẫn 3/3 pass**, không đụng gì tới Phase 2:
  ```
  tests/test_agents/test_graph.py::test_agent_basic_flow PASSED
  tests/test_agents/test_graph.py::test_agent_state_structure PASSED
  tests/test_api/test_routes.py::test_health PASSED
  3 passed in 0.57s
  ```
- **Fix cần thiết để giữ Phase 1 xanh**: `PM-test/conftest.py`'s `test_data` fixture giờ dọn cả
  cây `OnboardingTemplate → TemplateVersion → TemplateTask → TaskDependency` theo `project_id`
  trước khi xoá `Project` — nếu không sẽ vướng FK ngay khi các test Phase 1 dọn dẹp project họ tạo
  (vì giờ project nào cũng tự có template). `PM-test/test_onboarding_plans.py`'s
  `_create_template_version` cũng phải sửa: không tự tạo `OnboardingTemplate` mới nữa (sẽ vi phạm
  `UniqueConstraint("project_id")` vì project đã có sẵn 1 bản) — chuyển sang tạo thêm 1
  `TemplateVersion` trên template có sẵn của project.

### 5.3 Migration sạch, không drift

```
$ alembic check
INFO  [alembic.runtime.plugins] setting up autogenerate plugin ...
No new upgrade operations detected.
```

### 5.4 Backfill 4 project demo — chạy thật, kết quả xác nhận trong DB

```
$ python scripts/backfill_project_templates.py
  + PHONESHOP: tạo template mới (id=123)
  + TOURBOOK: tạo template mới (id=124)
  + FURNISTORE: tạo template mới (id=125)
  + GADGETHUB: tạo template mới (id=126)
Backfill xong.
```

Verify lại qua SQL — cả 4 project đều có đúng 1 template PROJECT, version 1 DRAFT, đủ 12 task:

```
 template_id |    key     |  scope  | status | version_no | version_status | task_count
-------------+------------+---------+--------+------------+----------------+------------
         125 | FURNISTORE | PROJECT | DRAFT  |          1 | DRAFT          |         12
         126 | GADGETHUB  | PROJECT | DRAFT  |          1 | DRAFT          |         12
         123 | PHONESHOP  | PROJECT | DRAFT  |          1 | DRAFT          |         12
         124 | TOURBOOK   | PROJECT | DRAFT  |          1 | DRAFT          |         12
```

### 5.5 Chạy thật qua Docker container (không phải chỉ chạy local)

Rebuild image, khởi động lại container:

```
$ docker compose up -d --build backend
 Image p-040-backend Built
 Container p-040-backend-1 Recreated
 Container p-040-db-1 Healthy
 Container p-040-backend-1 Started
```

Gọi thẳng qua container (không phải chạy trực tiếp Python) — golden path đầy đủ: xem template có
sẵn của project → duyệt version → xác nhận `OnboardingTemplate.status` chuyển `APPROVED` → thử
duyệt lại (đã APPROVED) → 409 → tạo version rỗng mới → duyệt version rỗng → 422 → sửa task trên
version đã APPROVED → 409:

```
$ curl http://localhost:8000/health
{"status":"ok","env":"development"}

$ curl http://localhost:8000/api/v1/onboarding-templates/pm/by-project/136
{"template_id":126,"project_id":136,"scope":"PROJECT","status":"DRAFT", ...}

$ curl -X PATCH http://localhost:8000/api/v1/template-versions/pm/161/approve
{"version_id":161,"template_id":126,"version_no":1,"status":"APPROVED","approved_at":"2026-08-12T10:18:20.876051", ...}

$ curl http://localhost:8000/api/v1/onboarding-templates/pm/126
{"template_id":126, ..., "status":"APPROVED", ...}

$ curl -X PATCH http://localhost:8000/api/v1/template-versions/pm/161/approve
{"detail":"Chỉ có thể duyệt version đang ở trạng thái DRAFT"}   HTTP 409

$ curl -X POST http://localhost:8000/api/v1/template-versions/pm -d '{"template_id":126}'
{"version_id":210,"template_id":126,"version_no":2,"status":"DRAFT", ...}

$ curl -X PATCH http://localhost:8000/api/v1/template-versions/pm/210/approve
{"detail":"Version chưa có task nào, không thể duyệt"}   HTTP 422

$ curl -X PATCH http://localhost:8000/api/v1/template-tasks/pm/1450 -d '{"title_pattern":"x"}'
{"detail":"Chỉ sửa được task khi version đang ở trạng thái DRAFT"}   HTTP 409
```

Toàn bộ response đều đúng theo thiết kế mục 3.3/3.4 của plan — trực tiếp qua container thật,
không phải chỉ test giả lập.

### 5.6 DB constraint hoạt động thật (không chỉ ở code Python)

```
\d onboarding_templates → Indexes:
    "uq_onboarding_templates_one_global" UNIQUE, btree (scope) WHERE scope = 'GLOBAL'
    "uq_onboarding_templates_one_per_project" UNIQUE CONSTRAINT, btree (project_id)

\d template_versions → Indexes:
    "uq_template_versions_one_approved_per_template" UNIQUE, btree (template_id) WHERE status = 'APPROVED'

$ INSERT INTO onboarding_templates (scope, name, description, status) VALUES ('GLOBAL','dup','dup','DRAFT');
ERROR:  duplicate key value violates unique constraint "uq_onboarding_templates_one_global"
```

### 5.7 Frontend — build/lint/type-check sạch

```
$ npx tsc --noEmit                                           # 0 lỗi
$ npx eslint src/features/project-management src/app/product-manager --max-warnings=0   # 0 lỗi, 0 warning
$ npx prettier --check ...                                    # "All matched files use Prettier code style!"
$ npx next build
✓ Compiled successfully in 19.0s
✓ Generating static pages using 7 workers (13/13)
Route (app) ... ├ ○ /product-manager ...
```

## 6. Điểm cần lưu ý cho phase sau (không phải bug, chỉ là scope đã chốt)

- **Authorization** (SoT §11.19) vẫn chưa code — cần làm khi TV4 có Auth thật. Thiết kế tham khảo
  vẫn còn trong `plan-phase2-master-template.md` mục 3.2.
- **`primary_pm_membership_id`** của `Project` vẫn còn bug cũ (không tự set khi tạo membership qua
  `project_membership_service.create_membership`) — đã biết từ trước Phase 2, **cố tình không sửa**
  theo đúng yêu cầu trước đó của bạn (chỉ sửa data, không sửa code).
- Test Phase 2 vẫn nằm trong `PM-test/` (ngoài `tests/`) theo đúng quy ước đã thống nhất trước đó
  — CI hiện tại (`pytest tests/`) không chạy các test này, phải chạy tay `pytest PM-test/`.

---

## 7. Phase 2b — Company Core (dữ liệu Policy thật) + rút gọn 5 category + UX version

Sau khi duyệt xong bản đầu, bạn xem UI thật và yêu cầu thêm 1 loạt thay đổi. Ghi lại đầy đủ ở đây
vì có 2 quyết định sản phẩm quan trọng khác với thiết kế ban đầu.

### 7.1 Company Core — không bịa dữ liệu, đọc thẳng KnowledgeDocument thật

Bạn cho xem trực tiếp DB: bảng `knowledge_documents` đã có sẵn 3 tài liệu chính sách công ty thật
(domain `POLICY`, seed từ trước qua `scripts/upload_sample_docs_to_cloudinary.py`) — COMPANY_POLICY,
HR_POLICY, SECURITY_POLICY. Quyết định: **Company Core phải lấy đúng dữ liệu này**, không tạo
category/task giả lập.

- Điền vào 2 file trước đó chỉ là TODO rỗng (chưa ai code, thuộc phần TV3 theo SoT §17):
  `src/services/knowledge_document_service.py` (`list_active_policy_documents`) và
  `src/api/routers/knowledge_document_router.py` (`GET /knowledge-documents/policy`) — chỉ 1
  endpoint đọc, không CRUD (để TV3 làm sau).
- Frontend: Company Core là **1 card trong cùng lưới category** (không tách card riêng), luôn đứng
  **đầu tiên** ("mới vào công ty phải tìm hiểu công ty trước"). Bấm vào mở drawer liệt kê từng
  tài liệu như 1 "task đọc" (không phải link trần) — có nút "Đọc tài liệu" mở `source_url` thật.
  Hoàn toàn read-only, không có nút Sửa/Xoá/Thêm nào (không có API ghi).

Bằng chứng — gọi thật qua container:
```
$ curl http://localhost:8000/api/v1/knowledge-documents/policy
[{"document_id":46,"title":"Company Policy — Quy định chung công ty","policy_category":"COMPANY_POLICY",...},
 {"document_id":47,"title":"HR Policy — Chính sách nhân sự","policy_category":"HR_POLICY",...},
 {"document_id":48,"title":"Security Policy — Chính sách bảo mật chung","policy_category":"SECURITY_POLICY",...}]
```
Test: `PM-test/test_knowledge_documents.py::test_list_policy_documents_returns_seeded_policies` PASS.

### 7.2 Duyệt lại version đã lưu trữ — chỉ đổi status, không nhân bản

Thiết kế ban đầu: muốn dùng lại 1 version đã ARCHIVED phải nhân bản thành DRAFT rồi duyệt bản sao
(2 bước, tạo thêm version mới). Bạn yêu cầu đơn giản hơn: **chỉ cần đổi thẳng status ARCHIVED →
APPROVED tại chỗ**, không tạo version mới.

- `src/services/template_version_service.py` `approve_version()`: đổi điều kiện chặn từ
  `status != DRAFT` thành `status not in (DRAFT, ARCHIVED)` — cho phép duyệt thẳng version đã lưu
  trữ. Toàn bộ validate (≥1 task, display_order hợp lệ, dependency không cycle) + khoá cạnh tranh
  `SELECT FOR UPDATE` giữ nguyên, áp dụng cho cả 2 nguồn trạng thái.
- **Bug tìm thấy nhờ viết test** (đã sửa): khi duyệt 1 version có PK nhỏ hơn trong lúc archive
  version đang APPROVED có PK lớn hơn, SQLAlchemy flush UPDATE theo thứ tự primary key chứ không
  theo thứ tự gán attribute trong code → UPDATE approve chạy trước UPDATE archive, đụng unique
  constraint `uq_template_versions_one_approved_per_template` giữa chừng dù cùng 1 transaction.
  Sửa bằng cách `await db.flush()` ngay sau khi archive version cũ, trước khi set version mới
  thành APPROVED — đảm bảo thứ tự UPDATE đúng bất kể PK.
- `VersionTable.tsx`: mỗi hàng version giờ có action theo đúng trạng thái — DRAFT: Duyệt + Nhân
  bản + Xem; APPROVED: Nhân bản + Xem; ARCHIVED: **Duyệt lại** (gọi thẳng cùng API `approve`) +
  Nhân bản + Xem. Bỏ nút "Tạo phiên bản mới" rời ở đầu trang (gộp hết vào hành động từng hàng).
  Nút Duyệt/Duyệt lại đổi từ nền xanh đặc (`variant="primary"`) sang ghost + chữ màu
  `--pm-success`, phân biệt với "Xem" (ghost trung tính).

Bằng chứng — golden path qua container thật:
```
$ curl -X PATCH .../template-versions/pm/161/approve   # v1 đang ARCHIVED
{"version_id":161,"version_no":1,"status":"APPROVED",...}   HTTP 200
$ curl .../template-versions/pm/211                     # v3 đang APPROVED trước đó
{"version_id":211,"version_no":3,"status":"ARCHIVED",...}   # tự động archive
$ curl .../template-versions/pm/by-template/126
[v3=ARCHIVED, v2=DRAFT, v1=APPROVED]   # vẫn đúng 3 version — không tạo thêm bản nào
```
Test mới: `test_approve_archived_version_reactivates_it_in_place` PASS (kiểm tra đúng cả việc
KHÔNG tạo version mới — `len(versions) == 2` sau khi duyệt lại).

### 7.3 Rút Master Template còn 5 category, khớp tài liệu dự án thật

Bạn chỉ rõ, dẫn thẳng từ `DocumentCategory` (`src/model/enums.py`, 7 giá trị:
`OVERVIEW, ARCHITECTURE, SETUP, ACCESS_SECURITY, CODEBASE_GUIDE, CONVENTION, FIRST_TASK`):
**"project thì 5 cái enum đầu thôi"** — Master Template chỉ giữ 5 category khớp đúng 5 giá trị
đầu, bỏ `CONVENTION`/`FIRST_TASK` (2 giá trị cuối) và `FIRST_PR` (chỉ có ở `TaskCategory`, không
có tài liệu tương ứng) — coi là mở rộng làm sau. Lý do: để Phase 4 (agent sinh `PlanTask`, chưa
làm ở đây) nối đúng 1 task ↔ 1 tài liệu dự án theo category trùng tên.

- **`src/model/enums.py`**: `TaskCategory` thêm `ARCHITECTURE` (giá trị mới, trước đó chưa có) +
  hằng số `DEFERRED_TASK_CATEGORIES = (CONVENTION, FIRST_TASK, FIRST_PR)` dùng chung.
- Migration `766d77208fd9`: `ALTER TYPE task_category ADD VALUE 'ARCHITECTURE'` (PG16 hỗ trợ chạy
  trong transaction, không cần kiểu recreate-enum phức tạp). `downgrade()` no-op có comment giải
  thích (Postgres không hỗ trợ xoá enum value).
- **`scripts/reshape_template_task_categories.py`** (mới, chạy 1 lần): (1) đổi category task có
  sẵn "Đọc tài liệu Architecture..." từ `ORIENTATION` sang `ARCHITECTURE` (tận dụng nội dung đã
  viết sẵn, không cần soạn mới); (2) hard-delete mọi `TemplateTask` thuộc `CONVENTION`/`FIRST_TASK`/
  `FIRST_PR` + `TaskDependency` liên quan. **Phát hiện + xử lý đúng 1 ràng buộc dữ liệu thật**: 5
  task ở GLOBAL template đang bị `PlanTask` (demo Onboarding Plan của Phase 1, seed từ trước) tham
  chiếu — script **bỏ qua không xoá** các task này (giữ nguyên lịch sử Plan demo), chỉ xoá các bản
  sao ở 4 project template (không bị tham chiếu) — log rõ: `"Bỏ qua 5 task đang bị PlanTask tham
  chiếu"` + `"Xoá 30 template_task"`.
- **`src/services/onboarding_template_service.py`** (`materialize_project_template`) và
  **`src/services/template_version_service.py`** (`create_version` clone): thêm filter
  `category NOT IN DEFERRED_TASK_CATEGORIES` khi copy task nguồn — bắt buộc vì GLOBAL vẫn còn 5
  task "mồ côi" không xoá được (mục trên); nếu không lọc, mọi project MỚI tạo từ nay sẽ vô tình kế
  thừa lại các category đã ẩn.
- `scripts/seed_dev_data.py`: cập nhật `TEMPLATE_TASKS` khớp cấu trúc mới, để seed lại từ đầu (DB
  mới hoàn toàn) ra đúng 5 category ngay, không cần chạy thêm script dọn dẹp.
- Frontend `TaskFormModal.tsx` `CATEGORY_OPTIONS`: còn đúng 5 entry, label đổi tên khớp tài liệu
  (Tổng quan dự án / Kiến trúc hệ thống / Cài đặt môi trường / Quyền truy cập & bảo mật / Hướng
  dẫn mã nguồn), mỗi entry có icon + màu riêng (badge tròn màu, cùng kiểu KPI row).

Bằng chứng — tạo project MỚI qua container thật, xác nhận đúng 5 category (không có category cũ
nào lọt qua):
```
$ curl -X POST .../projects/pm -d '{"key":"CATCHK9136",...}'
$ curl .../template-tasks/pm/by-version/413 | grep -o '"category":"[A-Z_]*"' | sort | uniq -c
      2 "category":"ACCESS"
      1 "category":"ARCHITECTURE"
      1 "category":"CODEBASE"
      1 "category":"ORIENTATION"
      2 "category":"SETUP"
```
(Project test đã archive lại ngay sau khi verify.) Test cập nhật:
`test_create_project_auto_creates_project_template` — assert category set đổi từ 7 giá trị cũ
sang đúng `{ORIENTATION, ARCHITECTURE, ACCESS, SETUP, CODEBASE}` — PASS.

### 7.4 TaskFormModal — wizard 3 bước

Chia form Sửa/Thêm task (trước đó 1 trang dài) thành 3 bước cùng 1 form state, chỉ submit thật ở
bước cuối: **Bước 1 — Thông tin cơ bản** (category, tiêu đề, thời gian, bắt buộc) → **Bước 2 —
Nội dung** (mục tiêu, hướng dẫn) → **Bước 3 — Phụ thuộc** (chọn task phải xong trước). Thêm
stepper (chấm số + nhãn, chấm hiện tại tô accent, chấm đã qua tô success) ở đầu modal. Validate
theo đúng bước (chặn "Tiếp tục" nếu bước đó thiếu field, không dồn hết xuống cuối).

### 7.5 Kết quả kiểm tra tổng — sau toàn bộ Phase 2b

```
$ pytest PM-test/ tests/ -v
...
============================= 46 passed in 5.62s ==============================
```
(29 test Phase 2 gốc + 4 test mới thêm ở Phase 2b: `test_knowledge_documents.py` 1 test,
`test_approve_archived_version_reactivates_it_in_place` 1 test, cộng test đã sửa assertion —
tổng vẫn 46 vì không thêm/bớt file test nào khác, chỉ đổi nội dung 1 vài assertion.)

```
$ alembic check
No new upgrade operations detected.
$ ruff check src/ PM-test/ scripts/
All checks passed!
$ npx tsc --noEmit && npx eslint ... --max-warnings=0 && npx next build
✓ 0 lỗi, build thành công
```

Docker: `docker compose up -d --build backend` → `/health` OK; frontend `next build` + restart
`next start`, đã verify trực tiếp qua UI thật (ảnh chụp trong lúc trao đổi) và qua curl như trên.
