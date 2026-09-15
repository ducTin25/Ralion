# Report: Sửa lỗi hạn task sai giờ + modal chọn giờ bắt đầu + sửa giờ trước duyệt (đã code xong)

> Trạng thái: **ĐÃ CODE + ĐÃ TEST + ĐÃ VERIFY LIVE**, chưa commit. Theo plan đã duyệt (2 vòng chốt
> qua trao đổi trực tiếp — không có file plan riêng, quyết định nằm trong hội thoại).

## 1. Bug gốc — đã xác nhận và sửa

**Lỗi 1 (gốc rễ chính)**: `compute_due_dates()` (`src/services/plan_generation/steps.py`) thiếu
đúng 1 dòng `current += timedelta(minutes=minutes)` — khiến biến `current` đứng yên suốt cả ngày
làm việc, nên MỌI task chưa tràn 480 phút/ngày nhận **cùng đúng 1 giờ hạn** = giờ sinh plan. Vì hạn
trùng thời điểm hiện tại, `is_overdue` báo "Trễ hẹn" ngay khi vừa tạo.

**Lỗi 2 (độc lập, cộng dồn thêm)**: `due_at` lưu dạng UTC không-offset, nhưng frontend
`new Date(value)` + `Intl.DateTimeFormat` không truyền `timeZone` khiến số giờ UTC hiển thị y
nguyên thay vì cộng thêm 7 tiếng (giờ Việt Nam) — đúng con số PM thấy: "02:47" thay vì 09:47 thật.

## 2. Đã làm gì

| # | Việc | File chính |
|---|---|---|
| 1 | Fix `compute_due_dates` — thêm dòng advance còn thiếu | `plan_generation/steps.py` |
| 2 | Modal chọn giờ bắt đầu khi bấm "Sinh plan", mặc định = giờ đề xuất (giờ hiện tại nếu trong giờ hành chính, hoặc 09:00 ngày làm việc kế tiếp) | `GenerateStartTimeModal.tsx` (mới) |
| 3 | Thread `start_at` xuyên suốt: DTO → router → job → pipeline → `compute_due_dates(start=...)` | `onboarding_plan_router.py`, `pipeline.py`, `onboarding_plan_service.py` |
| 4 | Mỗi task hiện được cả `start_at` (suy từ `due_at` task trước, không thêm cột DB) lẫn `due_at` | `plan_task_service.py`, `pm_progress_service.py` + 2 response DTO |
| 5 | Sửa hiển thị giờ đúng giờ Việt Nam (3 component PM), tách thành module dùng chung có test riêng | `lib/formatDateTime.ts` (mới) |
| 6 | PM sửa được `due_at` từng task khi plan còn DRAFT — tái dùng đúng API cũ | `plan_task_request_dto.py`, `plan_task_service.py`, `PlanTaskDrawer.tsx` |

## 3. Lỗi PHÁT SINH trong lúc code — tìm thấy nhờ chính test mới viết

Viết test integration trước, code sau đúng thứ tự thì không phát hiện được — nhưng ở đây viết xong
liền chạy test ngay lập tức nên bắt được **2 lỗi thật do chính tôi gây ra**, không phải lỗi có sẵn:

1. **`start_at` hiển thị dùng nhầm `OnboardingPlan.created_at`** (giờ DB tạo dòng) thay vì giờ PM
   chọn ở modal — 2 giá trị hoàn toàn khác nhau. Test
   `test_generate_with_chosen_start_at_schedules_tasks_from_that_moment` bắt được ngay (assert thất
   bại: nhận về giờ hiện tại thay vì giờ đã chọn). Đã sửa: suy `start_at` của task đầu tiên từ
   `due_at` của chính nó trừ `estimated_minutes`, không phụ thuộc timestamp nào khác của DB.
2. **Method sai trong test** (`client.post` thay vì `client.patch` cho endpoint approve) — bug ở
   test, không phải code. Đã sửa test.

Cả 2 đều được tìm ra bằng cách CHẠY test thật ngay sau khi viết, không phải chỉ đọc lại code.

## 4. Bằng chứng — test

```
ruff check src tests PM-test                          -> All checks passed
pytest PM-test/ tests/                                 -> 325 passed (8 phút 5)
frontend: npx tsc --noEmit                              -> sạch
frontend: npx eslint (file đã sửa)                       -> sạch (1 lỗi CÓ SẴN từ trước, không phải do lần sửa này — xác nhận bằng git diff, nằm ngoài mọi đoạn tôi đổi)
frontend: npx vitest run                                 -> 67 passed (58 cũ + 9 test mới)
```

Test mới: **11 backend** (5 `compute_due_dates` + 6 integration API) + **25 frontend**
(`formatDateTime.test.ts`, gồm cả 9 ca biên giờ hành chính/cuối tuần/qua tháng).

## 5. Bằng chứng — mutation testing (test có THẬT SỰ bắt lỗi không)

Cố tình phá lại đúng bug gốc, xem test có đỏ không:

| Vùng | Mutation | Kết quả |
|---|---|---|
| `compute_due_dates` | Bỏ dòng `current += timedelta(minutes=minutes)` (đúng bug gốc) | 3/5 test đỏ ngay |
| `start_at` (task 1) | Trả `due_at` thay vì `due_at - estimated_minutes` | 2/2 test đỏ |
| FE: `parseBackendDateTime` | Bỏ ép "Z" (đúng bug gốc lệch múi giờ) | test đỏ |
| FE: `vietnamLocalInputToBackendString` | Đổi dấu cộng/trừ 7 tiếng | test đỏ |
| FE: giờ hành chính | Sai biên `>=`/`<`, quên loại cuối tuần, vòng lặp nhảy ngày hỏng | 4/4 test đỏ |

Toàn bộ mutation đều bị bắt. Source đã được khôi phục nguyên vẹn sau mỗi lần — xác nhận bằng
`grep`/`git status` sau mỗi vòng.

## 6. Bằng chứng — chạy THẬT trên hệ thống đang sống (không chỉ test giả lập)

Rebuild Docker (`docker compose up -d --build backend`) → `/health` 200 → gọi thẳng API thật
(`POST /onboarding-plans/pm/generate` với `start_at: "2026-08-24T02:00:00"`, tức 09:00 giờ VN Thứ
Hai) trên project test cô lập `TEST14EB09EC` (1 kỹ sư test, chưa có plan) — không đụng dữ liệu
GADGETHUB/PHONESHOP/FURNISTORE của team.

Kết quả đọc trực tiếp từ **API + raw SQL** (khớp nhau tuyệt đối):

```
# 1  start=2026-08-24T02:00:00  due=2026-08-24T03:00:00  Tìm hiểu chính sách công ty
# 2  start=2026-08-24T03:00:00  due=2026-08-24T03:30:00  Đọc tài liệu Overview dự án
# 3  start=2026-08-24T03:30:00  due=2026-08-24T04:15:00  Đọc tài liệu Architecture...
# 4  start=2026-08-24T04:15:00  due=2026-08-24T04:35:00  Xin quyền truy cập GitHub repo
# 5  start=2026-08-24T04:35:00  due=2026-08-24T05:35:00  Xin quyền truy cập môi trường...
# 6  start=2026-08-24T05:35:00  due=2026-08-24T07:05:00  Cài đặt công cụ phát triển...
# 7  start=2026-08-24T07:05:00  due=2026-08-24T09:05:00  Chạy được service ở local...
# 8  start=2026-08-24T09:05:00  due=2026-08-25T09:40:00  Đọc Codebase Guide...
```

Xác nhận đúng mọi yêu cầu ban đầu:
- Task 1 bắt đầu **đúng** giờ đã gửi qua `start_at`, không phải giờ server.
- **8/8 task có giờ hạn khác nhau, tăng dần** — hết hẳn bug "cùng 1 giờ, trễ hẹn ngay khi vừa sinh".
- `start_at` của mỗi task = `due_at` của task liền trước — đúng chuỗi nối tiếp không hở/không đè.
- Task 8 tự động nhảy sang ngày làm việc kế tiếp khi vượt 480 phút/ngày (Thứ Ba 25/08, không rơi
  vào cuối tuần).

Plan test #2294 được để lại nguyên trong project `TEST14EB09EC` (dự án dành riêng cho test, không
phải dữ liệu thật của team) làm bằng chứng — xoá được bất cứ lúc nào nếu không cần giữ.

## 7. Việc KHÔNG làm được / giới hạn cần biết

- **`npm run build` (Next.js production build) không chạy được** — lỗi `EPERM` khoá file Windows do
  1 tiến trình `node`/dev-server khác đang chạy giữ file trong `.next/`. Không tự ý kill tiến trình
  lạ (có thể là dev server của bạn). Bù lại bằng `tsc --noEmit` (kiểm type đầy đủ) + `eslint` (kiểm
  cấu trúc React/Next) đều sạch — 2 công cụ này bắt được phần lớn lỗi mà `next build` thêm bắt được,
  nhưng không phải 100%. Nếu muốn chắc chắn tuyệt đối, cần đóng dev server đang chạy rồi tự chạy lại
  `npm run build`.
- Chưa test bằng mắt trên UI thật (modal chọn giờ, ô sửa `due_at` trong PlanTaskDrawer) — chỉ có
  bằng chứng qua API/DB trực tiếp + test tự động. Cần bạn tự mở app xác nhận UX (đặc biệt input
  `type="datetime-local"` hiển thị/format khác nhau theo trình duyệt).

## 8. Cách kiểm chứng lại

```bash
# Backend
.venv/Scripts/python.exe -m ruff check src tests PM-test
.venv/Scripts/python.exe -m pytest PM-test/test_plan_generation.py -q -k "start_at or due_dates or edit_task_due"

# Frontend
cd frontend && npx tsc --noEmit && npx vitest run src/features/project-management/lib/__tests__/formatDateTime.test.ts

# Docker + API thật
docker compose up -d --build backend
curl -X POST http://localhost:8000/api/v1/onboarding-plans/pm/generate \
  -H "Content-Type: application/json" \
  -d '{"membership_id": <id kỹ sư chưa có plan>, "start_at": "2026-08-24T02:00:00"}'
```
