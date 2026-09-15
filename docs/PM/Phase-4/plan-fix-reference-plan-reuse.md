# Plan: Onboarding Plan chuẩn thành plan cấp PROJECT (không gắn kỹ sư) — tạo/sửa/tạo lại ngay tại trang, kỹ sư chỉ nhận bản sao

> Thay thế hoàn toàn bản fix trước (`plan-fix-reference-plan-reuse.md`). Phần đã code hôm nay của
> bản fix đó (clone khi tạo plan cho kỹ sư, trang "Onboarding Plan", endpoint `/reference`) được
> GIỮ và mở rộng — không vứt đi.

## 1. Context — vì sao phải đổi

Bản fix trước chọn "bản chuẩn = plan của kỹ sư ĐẦU TIÊN". Chạy thật thì lộ 2 vấn đề PM chỉ ra:

1. **Không tạo được lộ trình chuẩn ngay tại trang "Onboarding Plan"** — màn hình rỗng chỉ biết đẩy
   PM sang trang Thành viên, vì `OnboardingPlan.membership_id` là **NOT NULL** và bảng **không có
   `project_id`** → mọi plan buộc phải thuộc 1 kỹ sư.
2. **Bản chuẩn bị khoá cứng sau khi duyệt** — `plan_task_service.update_task` (dòng 101) chặn sửa
   khi `plan.status != DRAFT`. Kỹ sư đầu tiên được duyệt plan là PM **mất quyền sửa lộ trình chuẩn
   vĩnh viễn**, trong khi kỹ sư mới vẫn tiếp tục nhận bản đã đóng băng đó.

Mô hình PM muốn (và đúng nghiệp vụ hơn): **lộ trình chuẩn là tài sản của DỰ ÁN, không của ai cả**.
PM tạo/sửa/tạo lại nó ở trang riêng; mỗi kỹ sư khi được cấp plan thì **nhận 1 bản sao** để chạy
tiến độ riêng. Sửa bản chuẩn **không đụng** kỹ sư đã nhận plan — chỉ kỹ sư nhận về sau mới theo bản
mới (toàn vẹn dữ liệu, đúng SoT rule 11).

## 2. Model — đổi schema (PM đã duyệt), 1 migration

```python
# src/model/onboarding_plan.py
project_id:    Mapped[int | None] = mapped_column(ForeignKey("projects.project_id"), nullable=True)
membership_id: Mapped[int | None] = ...  # NOT NULL -> nullable
```

Hai loại plan phân biệt bằng cột nào có giá trị:

| Loại | `project_id` | `membership_id` | Trạng thái | Ai sửa được |
|---|---|---|---|---|
| **Bản chuẩn** (mới) | có | NULL | luôn `DRAFT`, không bao giờ duyệt | PM sửa/tạo lại tự do, mãi mãi |
| **Plan của kỹ sư** (như cũ) | NULL | có | DRAFT → APPROVED → ... | chỉ khi còn DRAFT |

Migration thêm:
- `CHECK (num_nonnulls(project_id, membership_id) = 1)` — ép đúng 1 trong 2, không cho row lai.
- `UNIQUE (project_id) WHERE membership_id IS NULL` — mỗi project đúng 1 bản chuẩn.
- **Không đụng** index cũ `uq_onboarding_plans_one_open_per_membership`: Postgres coi mỗi NULL là
  khác nhau trong unique index, nên nhiều bản chuẩn (membership NULL) không đụng nhau. Đã kiểm
  chứng bằng chính định nghĩa index hiện có.
- Dữ liệu cũ (5 plan: 2 DRAFT demo + 3 ACTIVE seed) đều có `membership_id` → tự thoả CHECK, không
  cần backfill.

## 2b. Ảnh hưởng tới thành viên khác — đã kiểm tra thật, KHÔNG ảnh hưởng ai

Grep toàn repo tìm mọi chỗ đụng `OnboardingPlan`/`onboarding_plans`, kết quả:

| Nơi dùng | Của ai | Có bị ảnh hưởng? | Bằng chứng |
|---|---|---|---|
| `src/services/onboarding_plan_service.py`, `onboarding_plan_router.py`, `plan_task_service.py`, `model/onboarding_plan.py`, DTO, `PM-test/*`, FE module `project-management` | **TV1 (tôi)** | Có — chính là phần đang sửa | — |
| `scripts/seed_dev_data.py` | **dùng chung cả nhóm** | **KHÔNG** | Tạo plan bằng `OnboardingPlan(membership_id=..., template_version_id=..., status=ACTIVE)` — có `membership_id`, `project_id` để trống → **tự thoả CHECK mới**, không phải sửa 1 dòng |
| Trang Engineer `app/onboarding/page.tsx`, `app/tasks/page.tsx` | **TV2** | **KHÔNG** | Cả 2 file đúng 13 dòng, nội dung là *"Placeholder cho các luồng onboarding được nhóm thống nhất sau MVP"*, **0 tham chiếu** tới `OnboardingPlan`/`PlanTask`/`plan_id` |
| Router backend của TV2 | **TV2** | **KHÔNG** | `ls src/api/routers/` — không có router nào của TV2 đọc plan (chỉ có document_chunk/document_version của TV3 + task_dependency của TV1) |
| Trigger INV7 `enforce_onboarding_plan_forward_status` | **teammate (develop)** | **KHÔNG** | Grep `membership_id` trong migration `a1b2c3d4e5f6` → **không có dòng nào**; trigger chỉ đọc/so sánh `OLD.status`/`NEW.status` |
| TV3 (document/RAG), TV4 (auth/admin/HR) | — | **KHÔNG** | Không xuất hiện trong kết quả grep |
| Migration cũ `9fbecdaefe53`, `087bc97c54cf` | lịch sử | **KHÔNG** | Migration đã chạy, không chạy lại; migration mới nối tiếp phía sau |

**Index cũ không bị đụng** — đọc định nghĩa thật trong DB:
```sql
CREATE UNIQUE INDEX uq_onboarding_plans_one_open_per_membership
  ON public.onboarding_plans USING btree (membership_id)
  WHERE (status <> 'ONBOARDING_CLOSED'::plan_status)
```
Không có mệnh đề `NULLS NOT DISTINCT` → Postgres mặc định coi mỗi NULL là **khác nhau**, nên nhiều
bản chuẩn (đều `membership_id = NULL`) không đụng nhau. Ràng buộc "1 plan mở / kỹ sư" vẫn nguyên vẹn.

**Quyết định của PM (14/08)**: làm theo hướng sửa `onboarding_plans`. Lý do PM đưa ra: các thành
viên đang code trên **nhánh riêng**, nên thay đổi schema này chỉ tới tay họ lúc merge — họ thấy
schema mới ngay từ đầu chứ không bị gãy ngang giữa chừng. Không chọn phương án tách bảng riêng vì
sẽ phải viết trùng lặp model/service/DTO mà không giải quyết thêm được vấn đề gì.

**Rủi ro còn lại (nhỏ, đã có cách chặn)**: sau này TV2 code phần Engineer, nếu họ query
`onboarding_plans` mà không lọc thì có thể vô tình lấy cả bản chuẩn. Cách chặn đã tính sẵn:
- Bản chuẩn luôn `membership_id IS NULL` — mọi query của TV2 **bắt buộc** phải lọc theo membership
  (Engineer chỉ xem plan của chính mình) nên tự động loại trừ.
- `list_plans_by_project` dùng INNER JOIN `ProjectMembership` → bản chuẩn tự bị loại, không phải sửa.
- CHECK constraint tự mô tả ý nghĩa 2 loại plan ngay tại DB; thêm comment rõ trong model.
- Ghi mục "Contract cho TV2" trong report: *plan của kỹ sư luôn có `membership_id NOT NULL`; muốn
  chắc chắn thì lọc `WHERE membership_id IS NOT NULL`.*

## 3. Backend

### 3.1. `steps.py` — tách phần nạp template khỏi membership
```python
async def load_template_for_project(db, project_id) -> GenerationContext   # MỚI, dùng cho bản chuẩn
async def load_template(db, membership_id) -> GenerationContext            # gọi lại hàm trên
```
`GenerationContext.membership` đổi thành `ProjectMembership | None`. `membership is None` chính là
tín hiệu "đang sinh bản chuẩn" — không cần thêm cờ.

### 3.2. `onboarding_plan_service.py`
- `find_reference_plan(db, project_id)` — **đổi chữ ký**: bỏ `template_version_id`, tìm theo
  `project_id IS NOT NULL AND membership_id IS NULL`. Đơn giản và cố định hơn hẳn cách cũ (sắp theo
  `created_at` rồi lấy cái đầu).
- `get_reference_plan_for_project` — rút gọn còn 1 dòng gọi hàm trên.
- `persist_generated_plan` — suy ra loại plan từ `context.membership`:
  - `None` → ghi `project_id=..., membership_id=None`; nếu đã có bản chuẩn thì **ghi đè tại chỗ**
    (xoá task cũ, `revision += 1`) để không đụng UNIQUE(project_id).
  - có → như cũ.
- `assert_no_open_plan` giữ nguyên (chỉ áp cho plan kỹ sư).
- `approve_plan` — **thêm chặn**: bản chuẩn (`membership_id is None`) không có khái niệm duyệt → 409.

### 3.3. `pipeline.py` — bỏ nhánh AI khỏi luồng tạo plan kỹ sư
Sau khi có bản chuẩn cấp project, luồng rõ ràng hẳn:

| Luồng | Bước 5 làm gì |
|---|---|
| Sinh/tạo lại **bản chuẩn** (`project_id`) | Gọi AI (`generate_ai_content`) — chỗ DUY NHẤT còn gọi LLM |
| Cấp plan cho **kỹ sư** (`membership_id`) | Luôn `load_reference_content()` — sao chép, không bao giờ gọi AI |

Chưa có bản chuẩn mà cấp plan cho kỹ sư → **422 rõ ràng**: *"Dự án chưa có lộ trình chuẩn — vào
trang Onboarding Plan tạo trước"*. Không âm thầm gọi AI (đúng tinh thần SoT rule 16).

`job_store.create_job()` đổi sang nhận `membership_id=None, project_id=None` (1 trong 2).

### 3.4. Router — 1 endpoint mới
```
POST /onboarding-plans/pm/reference/generate   {project_id}   → 202 job
```
Dùng chung cho cả "tạo lần đầu" lẫn "tạo lại" — có bản chuẩn rồi thì ghi đè tại chỗ. Không cần 2
endpoint vì hành vi giống hệt nhau ở tầng dưới.

`GET /pm/reference?project_id=` giữ nguyên (đã code hôm nay).

## 4. Frontend

### 4.1. `ReferencePlanView.tsx` — thành trang tự chủ
- **Chưa có bản chuẩn** → nút **"Tạo lộ trình chuẩn bằng AI"** ngay tại chỗ (bỏ nút "Sang trang
  Thành viên"). Bấm → render `PlanGeneratingView` **ngay trong trang này** (tái dùng nguyên, đã có
  polling 6 bước) → xong thì hiện plan.
- **Đã có** → hiện plan + nút **"Tạo lại bằng AI"** (PM đã chốt cho phép) với modal xác nhận cảnh
  báo sẽ ghi đè nội dung đang có.
- Banner giữ nguyên ý: sửa ở đây chỉ ảnh hưởng kỹ sư nhận plan **về sau**.

### 4.2. `PlanReviewView.tsx` — thêm 1 prop
`showApproveButton?: boolean` (mặc định `true`). Bản chuẩn truyền `false` — không có nút "Duyệt &
phát hành" vì bản chuẩn không có trạng thái duyệt. Nút "Tạo lại" cũng do trang cha quyết định qua
prop `onRegenerate` thay vì tự gọi API regenerate của plan kỹ sư.

### 4.3. `MembersView` / `page.tsx`
Giữ nguyên nút "Tạo Onboarding Plan". Chỉ thêm: bắt lỗi 422 "chưa có lộ trình chuẩn" → hiện thông
báo kèm nút chuyển sang tab Onboarding Plan.

### 4.4. `api.ts`
`startReferencePlanGeneration(projectId)` — POST endpoint mới, trả job để poll bằng
`getPlanGenerationJob` sẵn có.

## 5. Test — sửa `PM-test/test_plan_generation.py`

Fixture `ready_project` thêm bước tạo bản chuẩn trước (vì giờ là điều kiện bắt buộc để cấp plan
kỹ sư). Test cần cập nhật/thêm:

1. `test_reference_plan_has_no_membership` — bản chuẩn có `project_id`, `membership_id=None`,
   status DRAFT.
2. `test_reference_plan_uses_ai` / `test_engineer_plan_always_clones` — bước 5 của bản chuẩn KHÔNG
   chứa "Sao chép"; của kỹ sư thì CÓ.
3. `test_generate_for_engineer_fails_without_reference` — chưa có bản chuẩn → 422, không tạo plan rác.
4. `test_reference_regenerate_overwrites_in_place` — tạo lại → cùng `plan_id`, `revision += 1`, task cũ bị thay.
5. `test_editing_reference_does_not_touch_existing_engineer_plans` — **test quan trọng nhất**: cấp
   plan cho kỹ sư A → sửa bản chuẩn → plan A KHÔNG đổi → cấp plan kỹ sư B → B nhận bản đã sửa.
6. `test_reference_plan_cannot_be_approved` — approve bản chuẩn → 409.
7. `test_one_reference_per_project` — tạo bản chuẩn 2 lần → vẫn đúng 1 row (UNIQUE bảo vệ).
8. Giữ nguyên các test cũ về INV7, unique index, sửa task sau duyệt, mapping nguồn, 6 bước.

## 6. Verification

- `pytest PM-test/ tests/ -q` xanh; `ruff check` sạch; `alembic upgrade head` + `alembic check`
  không phát sinh drift mới (ngoài 2 object cũ của `develop` đã ghi nhận từ Phase 3).
- FE `tsc/eslint/prettier/build` sạch.
- Chạy thật trên FURNISTORE (đã có sẵn tài liệu + template APPROVED):
  1. Vào tab **Onboarding Plan** → bấm "Tạo lộ trình chuẩn bằng AI" → xem 6 bước chạy (~30s) → hiện lộ trình.
  2. Sửa 1 task trên bản chuẩn.
  3. Sang **Thành viên** → cấp plan cho 1 kỹ sư → phải xong **dưới 1 giây** và nội dung khớp bản chuẩn (đã sửa).
  4. Sửa tiếp bản chuẩn → kiểm tra plan kỹ sư vừa cấp **không đổi**; cấp cho kỹ sư khác → nhận bản mới nhất.
- Dọn sạch data test sau khi lấy bằng chứng (đúng bài học Phase 3), verify 0 orphan.
- Cập nhật `docs/PM/Phase-4/report-phase4.md` + thay `plan-fix-reference-plan-reuse.md` bằng bản này.

## 7. Ngoài phạm vi

- Không thêm nút "đồng bộ ngược" đẩy thay đổi xuống plan kỹ sư đã cấp — PM đã chốt giữ snapshot tuyệt đối.
- Không đổi logic Approve/Regenerate/sửa tay của **plan kỹ sư** — giữ nguyên Phase 4.
- Bản chuẩn bám theo TemplateVersion tại thời điểm sinh; khi PM duyệt TemplateVersion mới thì bấm
  "Tạo lại bằng AI" để cập nhật (không tự động đồng bộ).
