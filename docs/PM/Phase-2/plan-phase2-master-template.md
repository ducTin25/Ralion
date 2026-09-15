# Plan Phase 2 — Master Template (`owner-template`)

> Trạng thái: **CHỜ DUYỆT** — chưa code, chỉ để bạn xem thiết kế trước khi bắt đầu (theo đúng yêu cầu "chưa có code tôi xem đã").
> **v3**: đối chiếu lại toàn bộ với `docs/PM/BO_06_CLAUDE_PROJECT_SOURCE_OF_TRUTH.md` (tài liệu ưu tiên cao nhất — mâu thuẫn với plan cũ thì SoT thắng). Phát hiện **6 điểm plan v2 sai/thiếu thật** so với SoT, đã sửa hết — xem mục 0.1.
> **v3.1** (lúc bắt đầu code): bạn quyết định **bỏ check authorization (`require_active_pm`) khỏi phạm vi Phase 2** — lý do: hệ thống chưa có đăng nhập/Auth thật (TV4 chưa làm), nên chưa có cách nào lấy đúng `user_id` người đang thao tác để check, gán cứng lúc này chỉ là hình thức. Điểm #2 ở bảng mục 0.1 và mục 3.2 dưới đây giữ lại làm tài liệu thiết kế cho sau này, **nhưng không code trong Phase 2** — mọi endpoint ghi dữ liệu (tạo version, sửa/xoá/reorder task, tạo/xoá dependency, duyệt version) tạm thời không kiểm tra quyền, ai gọi cũng được. Sẽ bổ sung lại khi Auth thật (TV4) xong.
> **v3.2** (sau khi xem UI thật, Phase 2b — xem `report-phase2.md` mục 7 để biết chi tiết đầy đủ): (a) **Master Template rút còn 5 category** (`ORIENTATION, ARCHITECTURE, SETUP, ACCESS, CODEBASE`), khớp 1:1 tên với 5 giá trị đầu của `DocumentCategory` — bỏ `CONVENTION`/`FIRST_TASK`/`FIRST_PR` (mở rộng làm sau, giữ nguyên trong enum `TaskCategory` vì Postgres không xoá được enum value và có `PlanTask` demo cũ còn tham chiếu). Đây là **lệch khỏi 7-category đã chốt ở SoT §9** (giống lần bỏ authorization — quyết định trực tiếp của bạn, ưu tiên hơn thiết kế SoT gốc). (b) **Company Core không phải category giả lập** — đọc thẳng `KnowledgeDocument` domain `POLICY` thật (đã seed sẵn), hiển thị dạng 1 card đầu tiên trong cùng lưới category, hoàn toàn read-only. (c) **Duyệt lại version ARCHIVED** không cần nhân bản nữa — `approve_version` cho phép chuyển thẳng `ARCHIVED → APPROVED` tại chỗ.

## 0. Tóm tắt hiểu ý bạn

- **Mọi project đều đã có sẵn 1 template chuẩn ngay từ đầu** — khi Admin tạo project, hệ thống tự materialize 1 Project Template từ Global Master Template (SoT §11.16, §17.2). PM **không có bước "tạo template"** trên UI. Khi PM mở trang "Master Template" của bất kỳ project nào, nội dung đã có sẵn — việc PM làm là **chỉnh sửa nội dung thành các phiên bản (version) khác nhau**, rồi **duyệt 1 phiên bản làm bản đang áp dụng** cho project đó, để Phase 4 dùng sinh Candidate Plan.
- Cần: xem lịch sử version, sửa/tạo task theo nhóm category, tìm kiếm/lọc task, quản lý phụ thuộc giữa các task (dependency) — đúng như bảng phân công gốc: `template_version_...`, `template_task_...`, `task_dependency_...`.
- Đây là **plan-only turn** — không code, chỉ viết doc này để bạn duyệt.

### 0.1 Đối chiếu với Source of Truth — 6 điểm plan trước đó sai/thiếu, đã sửa

| # | SoT quy định (trích) | Plan trước đó | Đã sửa thành |
|---|---|---|---|
| 1 | §11.16: "Nếu global template chưa sẵn sàng, hệ thống phải **báo lỗi rõ ràng**; không tạo template rỗng âm thầm" | Tự tạo version 1 DRAFT **rỗng** khi thiếu GLOBAL — **sai ngược hoàn toàn** | Ném lỗi 422 rõ ràng khi tạo project mà chưa có GLOBAL template APPROVED — xem mục 3.1 |
| 2 | §11.19: "Chỉ PM có membership `ACTIVE` trong đúng project mới được sửa template..." | Chưa có bước kiểm tra quyền nào | Thiết kế helper `require_active_pm(db, user_id, project_id)` — mục 3.2 — nhưng **hoãn code sang phase có Auth thật** theo quyết định v3.1 (chưa có đăng nhập nên chưa có `user_id` thật để check) |
| 3 | §24.1: "target của sản phẩm là **một Project Template duy nhất** cho mỗi project" | Chỉ có index chặn 2 bản APPROVED (`uq_onboarding_templates_one_approved_per_project` đã có sẵn) — không chặn 2 bản DRAFT song song | Thêm `UniqueConstraint("project_id")` — chặn tuyệt đối > 1 template/project bất kể status — mục 2 |
| 4 | §11.15: "Hệ thống có **đúng một** Global Master Template" | Chỉ là quy ước vận hành (seed 1 lần), không có gì chặn ở DB | Thêm partial unique index chặn > 1 row `scope=GLOBAL` — mục 2 |
| 5 | §24.1 + §17.2: "Luồng approve version phải có... xử lý cạnh tranh" | Chưa nhắc tới race condition | Thêm `SELECT ... FOR UPDATE` khoá template khi approve — mục 3.3 |
| 6 | §17.2: "Kiểm tra task bắt buộc, `display_order` và dependency **trước khi gửi duyệt**" | Chưa có bước validate trước khi approve | Thêm bước validate (≥1 task, display_order hợp lệ, dependency không cycle/dangling) ngay đầu hàm approve — mục 3.3 |

Các câu hỏi mở ở bản trước (PM tự duyệt? 7 hay 8 category?) — **SoT đã trả lời sẵn**, không cần hỏi lại nữa (xem mục 8).

**Ghi chú riêng**: bạn cũng dán nội dung Q&A "Luồng tiếp nhận repository và kiểm tra độ phủ tài liệu" — đây là thiết kế cho **Phase 3 (Project Knowledge/Documents)**, không thuộc Phase 2. SoT §13 xác nhận `DocumentCategory` **chỉ có 7 giá trị** (OVERVIEW/ARCHITECTURE/SETUP/ACCESS_SECURITY/CODEBASE_GUIDE/CONVENTION/FIRST_TASK) — đúng với code hiện tại, **không cần thêm** `WORKFLOW`/`REFERENCE_PR`/`GENERAL` như bản Google Doc cũ bạn dán (bản đó đã lỗi thời so với SoT, đã cập nhật lại trong memory).

---

## 1. Đối chiếu model đã có (đọc code thật, không đoán)

Cả 4 model đã tồn tại sẵn trong `src/model/`, **chưa có DTO/service/router nào** (đúng như bảng trạng thái backend trong `plan-pm.md`). Field thật:

```python
# onboarding_template.py
OnboardingTemplate:
  template_id PK
  project_id FK→projects (nullable — NULL khi scope=GLOBAL)
  source_template_id FK→onboarding_templates (nullable — template này fork từ đâu)
  scope: GLOBAL | PROJECT
  name, description
  status: DRAFT | APPROVED | NEEDS_REVIEW | ARCHIVED
  created_at, updated_at
  # index: chỉ 1 OnboardingTemplate APPROVED cho mỗi project (scope=PROJECT)

# template_version.py
TemplateVersion:
  version_id PK
  template_id FK→onboarding_templates
  version_no  (unique cùng template_id)
  status: DRAFT | APPROVED | ARCHIVED
  approved_by_user_id, approved_at
  created_at

# template_task.py
TemplateTask:
  template_task_id PK
  version_id FK→template_versions
  category: ORIENTATION | ACCESS | SETUP | CODEBASE | CONVENTION | FIRST_TASK | FIRST_PR   (7 giá trị)
  title_pattern, objective, instruction_template
  display_order  (unique cùng version_id — thứ tự xuyên suốt cả version, không tách riêng theo category)
  mandatory: bool
  estimated_minutes: int
  # KHÔNG có cột status/deleted — không hỗ trợ soft-delete

# task_dependency.py
TaskDependency:
  dependency_id PK
  predecessor_task_id FK→template_tasks
  successor_task_id FK→template_tasks
  # unique (predecessor, successor) — KHÔNG có version_id riêng, phải suy ra qua join template_tasks
```

**Điểm quan trọng phát hiện khi đọc code** (ảnh hưởng thiết kế service):
1. `TemplateTask` **không có cột soft-delete** — khác toàn bộ phần còn lại của app. Xoá task chỉ có thể là **hard-delete**, và chỉ an toàn khi version còn `DRAFT` (xem mục 3).
2. `PlanTask.template_task_id` là FK **NOT NULL** tới `template_tasks` — nghĩa là 1 khi `TemplateTask` đã từng được dùng để sinh `PlanTask` (chỉ xảy ra sau khi version đó `APPROVED`, theo đúng rule Phase 4), **không được xoá/sửa `TemplateTask` đó nữa** — khớp đúng với yêu cầu "version đã duyệt phải bất biến" bên dưới.
3. `TemplateVersion` **chưa có ràng buộc "chỉ 1 APPROVED mỗi template"** ở tầng DB (khác `OnboardingTemplate` đã có index này rồi) — cần thêm 1 migration nhỏ (mục 2).
4. `TaskDependency` không có cột `version_id` — muốn biết dependency thuộc version nào phải `JOIN template_tasks`. Cũng không có ràng buộc DB nào ngăn predecessor/successor thuộc 2 version khác nhau — phải validate ở service.

---

## 2. Migration mới cần thêm (3 constraint, không đổi cấu trúc cột nào)

Theo đúng SoT §24.1 ("Mọi migration bổ sung constraint phải có bước kiểm tra/chuẩn hoá dữ liệu cũ trước khi tạo unique index" — hiện `onboarding_templates`/`template_versions` đang **0 row** nên không có rủi ro migration fail, nhưng vẫn nêu rõ để nhớ nếu chạy trên môi trường khác đã có data).

**2.1 — `TemplateVersion`: tối đa 1 `APPROVED` mỗi template** (đúng pattern đã dùng cho `OnboardingPlan`):
```python
Index(
    "uq_template_versions_one_approved_per_template",
    "template_id",
    unique=True,
    postgresql_where=text("status = 'APPROVED'"),
)
```

**2.2 — `OnboardingTemplate`: đúng 1 template mỗi project, bất kể status** (SoT §24.1 — mạnh hơn hẳn constraint hiện có, vốn chỉ chặn khi cả 2 đều `APPROVED`):
```python
UniqueConstraint("project_id")
```
Postgres coi nhiều `NULL` là khác nhau nên không ảnh hưởng các row `scope=GLOBAL` (`project_id=NULL`) — vẫn cho phép nhiều row GLOBAL về mặt kỹ thuật, nên cần thêm 2.3 để chặn nốt.

**2.3 — `OnboardingTemplate`: đúng 1 record `scope=GLOBAL` toàn hệ thống** (SoT §11.15 "đúng một Global Master Template"):
```python
Index(
    "uq_onboarding_templates_one_global",
    text("(scope)"),
    unique=True,
    postgresql_where=text("scope = 'GLOBAL'"),
)
```

→ Cả 3 đều là unique index/constraint thuần DB, không cần trigger, không đổi cột. Gộp chung 1 file migration Alembic mới, review kỹ trước khi `upgrade head`.

Không cần thêm invariant "version status chỉ đi tới" (giống INV7 của `OnboardingPlan`) ở tầng DB bằng trigger — vì chỉ có đúng 1 chỗ ghi dữ liệu này (service), kiểm tra ở tầng service là đủ (mục 3.3).

---

## 3. Mô hình nghiệp vụ & state machine (chốt rõ để tránh hiểu sai khi code)

### 3.1 Vòng đời `OnboardingTemplate` — bất biến quan trọng nhất: **luôn tồn tại sẵn, PM không tạo**

- **GLOBAL scope**: đúng **1 record duy nhất toàn hệ thống** (mẫu chuẩn chung của tổ chức, áp dụng cho tất cả dự án) — seed 1 lần bằng script (giống cách seed user/project demo trước đây), có sẵn 1 `TemplateVersion` APPROVED chứa bộ task chuẩn (7 category). **Không có UI quản lý GLOBAL template trong Phase 2** (PM không sửa GLOBAL trực tiếp) — nếu sau này cần UI cho Admin quản lý GLOBAL, đó là việc khác.
- **PROJECT scope**: đúng 1 record cho mỗi project — **nhưng không phải PM tạo**. Được **tự động tạo kèm ngay khi project được tạo** (mở rộng `project_service.create_project`, hàm PM đã sở hữu/code từ Phase 1 — xem chi tiết kỹ thuật bên dưới), fork từ GLOBAL: copy toàn bộ `TemplateTask` từ version APPROVED hiện tại của GLOBAL sang 1 `TemplateVersion` v1 mới (status ban đầu để `DRAFT` — PM có sẵn nội dung chuẩn để xem/sửa ngay, không phải version rỗng). Vì vậy **khi PM mở trang Master Template của bất kỳ project nào, luôn thấy sẵn nội dung** — không có "trạng thái rỗng chưa có gì" trong luồng bình thường.
- `OnboardingTemplate.status` là cờ tổng hợp: `DRAFT` = chưa có version nào được duyệt cho project này (mới fork xong, đang chờ PM chỉnh/duyệt), `APPROVED` = đang có 1 version live, `ARCHIVED` = project đã archive. Cờ này do service tự đồng bộ mỗi khi version đổi trạng thái — **PM không sửa trực tiếp field này**.
- **Kỹ thuật tạo tự động** (thêm vào `project_service.create_project`, cùng 1 transaction với việc tạo `Project`, để đảm bảo không có project nào "lọt lưới" thiếu template):
  ```python
  async def create_project(db, dto):
      global_template = await onboarding_template_service.get_approved_global_template(db)
      if global_template is None:
          # SoT §11.16: PHẢI báo lỗi rõ ràng, KHÔNG tạo template rỗng âm thầm
          raise HTTPException(422, "Chưa có Global Master Template — không thể tạo project. Liên hệ Admin/Tech Lead seed template chuẩn trước.")

      project = Project(key=..., name=..., created_by_admin_id=...)
      db.add(project)
      await db.flush()  # có project_id nhưng chưa commit

      await onboarding_template_service.materialize_project_template(db, project, global_template)  # fork từ GLOBAL

      await db.commit()
      await db.refresh(project)
      return project
  ```
  **Sửa lại theo đúng SoT §11.16** (bản trước plan này từng viết ngược — tạo version rỗng khi thiếu GLOBAL — đã sửa): nếu chưa có GLOBAL template `APPROVED`, **không tạo được project luôn**, trả lỗi rõ ràng ngay tại bước tạo project — không có khái niệm "project có template rỗng". Do đó **bước seed GLOBAL template phải chạy trước tiên**, trước khi bất kỳ project mới nào được tạo (kể cả ngoài Phase 2 — nếu TV4/Admin tạo project trước khi GLOBAL template tồn tại thì cũng sẽ bị lỗi này, đúng chủ đích SoT).
- **API tạo template thủ công** (`POST /onboarding-templates/pm`) vẫn giữ trong router — nhưng **không phải hành động PM bấm trên UI** nữa. Dùng cho: (a) backfill 4 project demo hiện có (PHONESHOP/TOURBOOK/FURNISTORE/GADGETHUB — tạo từ trước khi Phase 2 tồn tại, hiện chưa có template) qua 1 script chạy 1 lần, (b) test trực tiếp qua Swagger.

### 3.2 Authorization — SoT §11.19 (thiết kế tham khảo, **hoãn code sang Phase có Auth thật** — quyết định v3.1)

> "Chỉ PM có membership `ACTIVE` trong đúng project mới được sửa template, tạo Candidate Plan và approve plan/version của project đó."

Chưa có Auth/JWT thật (TV4 chưa xong) — bạn quyết định **Phase 2 không code check quyền**, vì gán `user_id` cứng lúc chưa có đăng nhập chỉ là hình thức, không có giá trị thật. Giữ lại thiết kế helper dưới đây làm tài liệu tham khảo cho phase sau, khi TV4 gắn Auth thật thì implement lại và áp cho các endpoint ghi dữ liệu ở mục 4:
```python
async def require_active_pm(db: AsyncSession, user_id: int, project_id: int) -> None:
    membership = await db.scalar(
        select(ProjectMembership).where(
            ProjectMembership.user_id == user_id,
            ProjectMembership.project_id == project_id,
            ProjectMembership.project_role == ProjectRole.PM,
            ProjectMembership.status == MembershipStatus.ACTIVE,
        )
    )
    if membership is None:
        raise HTTPException(403, "Bạn không phải PM đang hoạt động của project này")
```
**Không gọi ở Phase 2** — mọi endpoint ghi dữ liệu mục 4 (tạo version, sửa/xoá/reorder task, tạo/xoá dependency, duyệt version) tạm thời không kiểm tra người gọi có phải PM active hay không.

### 3.3 Vòng đời `TemplateVersion`
```
(tạo mới) → DRAFT → [Duyệt] → APPROVED ⇄ [duyệt version khác / duyệt lại] ⇄ ARCHIVED
```
*(Cập nhật v3.2: `ARCHIVED → APPROVED` giờ đi lại được trực tiếp qua "Duyệt lại" — xem cuối mục
này. Chỉ riêng `DRAFT` là một chiều, không có API nào set ngược `APPROVED`/`ARCHIVED` về `DRAFT`.)*
- **Tạo version mới** (`POST /template-versions/pm`): luôn ở `DRAFT`. Có 2 cách bắt đầu nội dung:
  - **Sao chép từ version hiện có** (mặc định, khuyến nghị) — copy toàn bộ `TemplateTask` (+ `TaskDependency` giữa các task đó, remap ID) từ 1 version nguồn (thường là version `APPROVED` hiện tại, hoặc version DRAFT gần nhất) sang version mới.
  - **Tạo trống** — dùng khi PM muốn viết lại từ đầu (hiếm).
- **Sửa task** (`PATCH/DELETE template-tasks`): **chỉ cho phép khi version đang `DRAFT`**. Version `APPROVED`/`ARCHIVED` là bất biến — muốn sửa phải tạo version mới (đúng lý do: các task trong version `APPROVED` có thể đã bị `PlanTask` tham chiếu, sửa/xoá sẽ vi phạm FK hoặc làm sai lệch Plan đã phát hành).
- **Duyệt version** (`PATCH /template-versions/pm/{id}/approve`) — 1 transaction, đúng SoT §17.2 ("khoá dữ liệu liên quan, archive version cũ rồi approve version mới") + §24.1 ("xử lý cạnh tranh"):
  1. **Validate trước khi duyệt** (SoT §17.2 "kiểm tra task bắt buộc, display_order và dependency trước khi gửi duyệt"): version phải có ≥ 1 task; `display_order` không trùng/không nhảy cóc bất thường; toàn bộ `TaskDependency` của version không cycle, không tham chiếu task ngoài version. Fail bất kỳ điều nào → 422, không cho duyệt.
  2. **Khoá cạnh tranh**: `SELECT ... FOR UPDATE` trên row `OnboardingTemplate` (hoặc trên các `TemplateVersion` cùng `template_id`) trước khi đổi status — tránh 2 request duyệt 2 version khác nhau của cùng template gần như đồng thời cùng lọt qua check "chưa có version nào APPROVED" rồi cả 2 cùng set APPROVED (unique index ở mục 2.1 sẽ chặn ở tầng DB nếu lọt qua, nhưng khoá ở service để trả lỗi 409 rõ ràng thay vì để DB ném lỗi khó hiểu).
  3. Version đích chuyển `DRAFT` → `APPROVED`.
  4. Nếu template đang có version khác `APPROVED` → chuyển version đó sang `ARCHIVED`.
  5. Cập nhật `OnboardingTemplate.status = APPROVED`.
  - Ai duyệt: **PM tự duyệt bản của mình** (self-serve, đúng SoT §17.2 "chỉ PM đúng project được approve" — không có vai trò reviewer riêng). Field `approved_by_user_id`/`approved_at` vẫn ghi nhận đúng ai bấm duyệt lúc nào, phục vụ audit.
  - **[v3.2] Duyệt lại version ARCHIVED**: bước 1 (điều kiện vào) nới từ "chỉ nhận `DRAFT`" thành "nhận `DRAFT` hoặc `ARCHIVED`" — cho phép chuyển thẳng 1 version đã lưu trữ quay lại `APPROVED` **tại chỗ, không tạo version mới**, dùng chung đúng API/logic này (chỉ khác điều kiện đầu vào). Đây là quyết định đơn giản hoá của bạn, thay cho thiết kế "nhân bản rồi duyệt bản sao" ban đầu. Muốn **sửa nội dung** một version cũ (không chỉ dùng lại y nguyên) thì vẫn phải "Nhân bản" (`clone_from_version_id`) như cũ.
  - Bug tìm thấy khi viết test cho luồng này: `SELECT FOR UPDATE` + archive-cũ-rồi-approve-mới nếu không `flush()` giữa 2 bước sẽ bị SQLAlchemy đảo thứ tự UPDATE theo primary key (không theo thứ tự gán trong code), có thể đụng unique constraint giữa chừng khi version đang duyệt có PK nhỏ hơn version đang bị archive. Đã sửa bằng `await db.flush()` ngay sau khi archive version cũ.

### 3.4 `TemplateTask`
- Nhóm theo `category` (7 giá trị enum thật — xem mục 1; **không phải 8 nhóm** như bảng mô tả cũ trong `plan-pm.md`/mockup gốc có "Company Core" — giá trị đó không map được vào enum hiện tại, bỏ qua, dùng đúng 7 category làm chuẩn).
- `title_pattern`/`objective`/`instruction_template` là **nội dung khung PM tự viết tay** (không có AI ở Phase 2 — AI chỉ xuất hiện ở bước 5 pipeline Phase 4 "điền nội dung task", đọc đúng các field này làm input rồi cá nhân hoá theo tài liệu dự án thật). Phase 2 không gọi LLM, không cần eval kiểu Day 14 — thuần CRUD.
- `display_order`: 1 dãy số liên tục cho **cả version** (không lặp lại theo từng category) — UI vẫn hiển thị nhóm theo category cho dễ nhìn, nhưng sắp xếp/kéo-thả cập nhật `display_order` toàn cục.
- Xoá: **hard-delete thật**, chỉ cho phép khi version `DRAFT` (đã nói ở mục 3.3).

### 3.5 `TaskDependency`
- Ý nghĩa: `successor` không nên bắt đầu trước khi `predecessor` xong — dữ liệu này Phase 4 bước 6 ("kiểm tra dependency/ACL") sẽ đọc lại khi sinh Plan.
- Validate khi tạo (service, không có ở DB):
  - `predecessor_task_id` và `successor_task_id` phải cùng `version_id` (join kiểm tra).
  - Không tự phụ thuộc chính nó.
  - Không tạo chu trình (cycle) — version thường chỉ vài chục task nên DFS kiểm tra trực tiếp là đủ, không cần thuật toán phức tạp.
- UI: gắn ngay trong form sửa/tạo task — 1 ô "Phụ thuộc vào task nào" (multi-select trong cùng version, loại trừ chính nó) — **không làm** giao diện graph riêng (ngoài phạm vi MVP).

---

## 4. Backend — DTO / Service / Router (đúng convention `/pm` sub-path đã chốt)

```
src/dto/request/
  onboarding_template_request_dto.py   # CreateOnboardingTemplateRequestDTO
  template_version_request_dto.py       # CreateTemplateVersionRequestDTO
  template_task_request_dto.py           # CreateTemplateTaskRequestDTO, UpdateTemplateTaskRequestDTO, ReorderTemplateTaskRequestDTO
  task_dependency_request_dto.py          # CreateTaskDependencyRequestDTO

src/dto/response/
  onboarding_template_response_dto.py
  template_version_response_dto.py
  template_task_response_dto.py
  task_dependency_response_dto.py

src/services/
  onboarding_template_service.py
  template_version_service.py
  template_task_service.py
  task_dependency_service.py

src/api/routers/
  onboarding_template_router.py   # prefix="/onboarding-templates"
  template_version_router.py       # prefix="/template-versions"
  template_task_router.py           # prefix="/template-tasks"
  task_dependency_router.py          # prefix="/task-dependencies"
```

### Endpoint chi tiết

| Method | Path | Việc |
|---|---|---|
| POST | `/onboarding-templates/pm` | **Không dùng từ UI PM** — nội bộ gọi từ `project_service.create_project` (mục 3.1), chỉ giữ endpoint để backfill project cũ/test qua Swagger. Body: `project_id`, tự fork từ GLOBAL nếu có |
| GET | `/onboarding-templates/pm/by-project/{project_id}` | Lấy template của 1 project — 404 nếu project chưa có |
| GET | `/onboarding-templates/pm/{template_id}` | Chi tiết 1 template |
| POST | `/template-versions/pm` | Tạo version mới, DRAFT (body: `template_id`, `clone_from_version_id` optional) |
| GET | `/template-versions/pm/by-template/{template_id}` | Lịch sử version (mới nhất trước) |
| GET | `/template-versions/pm/{version_id}` | Chi tiết 1 version |
| PATCH | `/template-versions/pm/{version_id}/approve` | Duyệt version (transaction mục 3.3) |
| POST | `/template-tasks/pm` | Tạo task (chặn nếu version không `DRAFT`) |
| GET | `/template-tasks/pm/by-version/{version_id}` | List task theo version, sort `display_order` |
| PATCH | `/template-tasks/pm/{template_task_id}` | Sửa task (chặn nếu version không `DRAFT`) |
| DELETE | `/template-tasks/pm/{template_task_id}` | Hard-delete (chặn nếu version không `DRAFT`) |
| PATCH | `/template-tasks/pm/reorder` | Cập nhật `display_order` hàng loạt (body: `version_id`, list `template_task_id` theo thứ tự mới) |
| POST | `/task-dependencies/pm` | Tạo dependency (validate mục 3.5) |
| GET | `/task-dependencies/pm/by-version/{version_id}` | List dependency của 1 version (join qua `template_tasks`) |
| DELETE | `/task-dependencies/pm/{dependency_id}` | Xoá 1 dependency |

Field response DTO lấy trực tiếp từ model (đúng pattern `from_entity()` đã dùng ở Phase 1), convert enum → string literal.

---

## 5. Frontend — cấu trúc file & luồng UI

```
frontend/src/features/project-management/
  dto/requestDTO/{template,templateVersion,templateTask,taskDependency}.request.ts
  dto/responseDTO/{template,templateVersion,templateTask,taskDependency}.response.ts
  api.ts   # thêm các hàm gọi endpoint mục 4 (giữ 1 file như convention hiện tại)
  components/template/
    TemplateView.tsx + .module.scss        # màn hình chính "Master Template"
    VersionTabs.tsx + .module.scss           # dải chọn version (pill theo version_no + status pill)
    TaskFormModal.tsx + .module.scss          # form tạo/sửa task (bao gồm chọn dependency)
  components/ui/
    PmTextarea.tsx   # MỚI — Field nhiều dòng, cùng style PmInput/PmSelect (chưa có, cần cho objective/instruction_template)
```

### Luồng UI

1. **Sidebar "Master Template"** (`template` nav key — hiện đang `enabled: false`) → bật lên khi Phase 2 xong.
2. **Không có trạng thái rỗng/nút "tạo template"** — theo đúng bất invariant mục 3.1, mọi project **đã tồn tại được** (tức là đã tạo thành công) thì chắc chắn có template kèm theo, vì tạo project mà thiếu GLOBAL template sẽ bị chặn lỗi ngay từ bước tạo project (không có project nào lọt lưới thiếu template). PM vào thẳng màn hình chính bên dưới, không có trạng thái rỗng nào cần xử lý ở FE.
3. **Màn hình chính** (luôn có sẵn):
   - `PmPageHead` (icon `book`, title "Master Template", subtitle = tên/khoá project đang chọn).
   - `PmKpiRow`: Tổng task / Bắt buộc / Tuỳ chọn / Tổng thời gian ước tính (phút→giờ) — 4 màu variant khác nhau như đã làm ở Phase 1.
   - `VersionTabs`: các version dạng pill ngang (v1, v2...), mỗi pill có `PmPill` trạng thái (Nháp/Đang áp dụng/Đã lưu trữ); bấm để xem task của version đó.
   - Trong `PmCard`: `filterRow` gồm `PmSearchInput` (tìm theo `title_pattern`/`objective`) + `PmSelect` lọc theo `category` + `PmSelect`/checkbox lọc "chỉ bắt buộc" — 3 control cùng hàng (cần chỉnh CSS `filterRow` rộng hơn so với Phase 1, vốn chỉ có 2 control).
   - Bảng/list task **nhóm theo 7 category** (accordion hoặc heading + list con), mỗi dòng: `title_pattern`, `PmTag` mandatory, `estimated_minutes`, nút Sửa/Xoá (chỉ hiện nếu version đang xem là `DRAFT`).
   - Nút "Thêm task" (chỉ hiện khi version `DRAFT`) → `TaskFormModal`.
   - Thanh hành động cuối: "Tạo phiên bản mới" (luôn bấm được) + "Duyệt phiên bản này" (chỉ hiện khi đang xem version `DRAFT`).
   - `PmPageFooter` cuối trang, đúng pattern đã có.
4. **`TaskFormModal`**: `PmField` cho từng field (`category` select, `title_pattern` input, `objective`/`instruction_template` — dùng `PmTextarea` mới, `mandatory` checkbox, `estimated_minutes` input số, `display_order` — auto-append cuối danh sách, không cho sửa tay trong form tạo mới để tránh trùng số; sửa thứ tự làm riêng bằng kéo-thả/nút lên-xuống trong bảng chính), và 1 multi-select "Phụ thuộc vào" (chọn từ các task khác cùng version).

---

## 6. Thứ tự làm (full-stack theo từng phần nhỏ, giống style Phase 1)

**Thứ tự bắt buộc phải đi trước** (khác bản trước — vì giờ tạo project sẽ lỗi nếu thiếu GLOBAL, nên seed phải xong sớm nhất, trước cả migration test):

1. Migration: cả 3 constraint mục 2 (`uq_template_versions_one_approved_per_template`, `UniqueConstraint(project_id)`, `uq_onboarding_templates_one_global`), verify `alembic check`/`upgrade head`.
2. BE — seed script tạo **1 GLOBAL template** (nếu môi trường chưa có) với 1 `TemplateVersion` APPROVED + bộ task mẫu theo 7 category — **phải chạy xong trước** vì từ bước 3 trở đi, tạo project mới sẽ lỗi nếu thiếu bước này (đúng SoT §11.16).
3. BE — `OnboardingTemplate` + `TemplateVersion`: DTO/service/router, gồm `materialize_project_template` (fork từ GLOBAL) + **sửa `project_service.create_project`** gọi hàm này, trả lỗi 422 nếu thiếu GLOBAL (mục 3.1). Test: tạo project mới → tự có template kèm theo (test chính); tạo project khi **chưa seed GLOBAL** → nhận đúng lỗi 422 (test riêng, xác nhận đúng SoT §11.16, không phải tạo template rỗng); tạo version mới (sao chép/trống); duyệt version — test validate trước duyệt (mục 3.3 bước 1) lẫn guard "chặn nếu version không DRAFT". Không test authorization — bỏ khỏi Phase 2 theo quyết định v3.1.
4. BE — **backfill 1 lần** cho 4 project demo hiện có (PHONESHOP/TOURBOOK/FURNISTORE/GADGETHUB, tạo trước khi Phase 2 tồn tại — không đi qua `create_project` mới nên chưa có template) — chạy `materialize_project_template` cho từng project qua script, xác nhận cả 4 đều có template sau đó.
5. BE — `TemplateTask`: CRUD + reorder, test guard "chỉ sửa/xoá khi DRAFT", test hard-delete xoá thật khỏi DB, test reorder validate đủ/đúng tập task_id (SoT §11.22).
6. BE — `TaskDependency`: create/list/delete, test validate cùng-version + không tự tham chiếu + phát hiện cycle.
7. FE — DTO + `api.ts` cho cả 4 nhóm endpoint.
8. FE — `PmTextarea` (component nền tảng còn thiếu).
9. FE — `TemplateView` + `VersionTabs` + `TaskFormModal`, bật nav "Master Template" (không có nút/màn hình "tạo template").
10. Verify toàn bộ: `pytest`, `tsc`, `eslint`, `prettier`, `next build`, chạy tay qua Swagger + UI thật (mở project bất kỳ, xác nhận thấy template ngay không cần tạo) — viết báo cáo `docs/PM/Phase-2/report-phase2.md` kèm bằng chứng (log test, curl output) — **đúng như bạn yêu cầu, làm sau khi bạn duyệt plan này**.

---

## 7. Ngoài phạm vi Phase 2 (ghi rõ, không code)

- UI quản lý GLOBAL template (Admin-level) — chỉ seed bằng script.
- Đồng bộ ngược nếu Admin archive project (Phase 2 giả định service Phase 1 đã lo việc archive project, Phase 2 chỉ phản ứng khi cần — không code thêm logic 2 chiều phức tạp trong lần này, chỉ note lại nếu phát sinh bug thật khi test).
- Giao diện dependency dạng graph/sơ đồ — dùng multi-select đơn giản như mục 3.5.
- Bất kỳ nội dung nào liên quan Phase 3 (repository scan, Coverage Report, KnowledgeDocument) — đã tách riêng, xem ghi chú đầu file.

---

## 8. Các điểm trước đây hỏi mở — nay đã có câu trả lời chắc chắn từ SoT (không cần hỏi lại)

1. **Tự động tạo template khi tạo project**: đúng theo SoT §11.16/§17.2 — `project_service.create_project` tự fork từ GLOBAL, không có nút "tạo template" ở PM UI. Khác 1 điểm so với bản hỏi trước: nếu thiếu GLOBAL thì **lỗi rõ ràng**, không fallback rỗng.
2. **Backfill 4 project demo hiện có**: vẫn cần (SoT không nói gì khác về việc này — đây là việc kỹ thuật xử lý data cũ, không phải quyết định nghiệp vụ).
3. **Duyệt version**: đúng SoT §17.2 — "chỉ PM đúng project được approve" — tự duyệt (self-serve), không có reviewer riêng.
4. **8 nhóm → 7 category**: đúng SoT §9 (hành trình onboarding chuẩn khớp 1:1 với 7 `TaskCategory`) — dùng 7 category, bỏ "Company Core".
5. **Mới bổ sung theo SoT, không phải suy đoán**: 2 constraint mới (mục 2.2/2.3), validate trước duyệt + xử lý cạnh tranh (mục 3.3) — quy định rõ trong SoT, không phải lựa chọn của tôi. Riêng authorization (mục 3.2) SoT có quy định (§11.19) nhưng **bạn quyết định hoãn** sang phase có Auth thật (xem ghi chú v3.1 đầu file) — đây là quyết định của bạn, không phải plan tự bỏ.

→ Không còn điểm nào cần hỏi thêm. Bạn duyệt bản v3 này là tôi bắt đầu code theo đúng thứ tự mục 6.
