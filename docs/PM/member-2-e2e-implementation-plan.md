# Kế hoạch E2E — Thành viên 2

## Mục tiêu

Xây Engineer Portal tại `/user` cho ba use case: xem Approved Plan và Task Detail,
thực hiện checklist, và báo/theo dõi blocker. Alembic head và phần canonical schema
trong `ARCHITECTURE.md` là nguồn sự thật kỹ thuật.

## Quyết định đã chốt

- Blocker là entity riêng; tạo blocker không chuyển `PlanTask` sang `BLOCKED`.
- MVP không có routing HR/SLA hay `TaskStatusHistory`.
- First Task và First Pull Request đã được loại khỏi phạm vi hiện hành theo quyết
  định ngày 12/08/2026. Giữ schema canonical để không ảnh hưởng module khác, nhưng
  Engineer Portal không hiển thị, tính progress hoặc cho mutation hai nhóm này.
- Dùng demo engineer cố định trong development/test; backend vẫn tự suy ra và kiểm
  tra membership, không tin `membership_id` từ frontend.
- Không triển khai upload blocker attachment trong phạm vi này.

## API dự kiến

- `GET /api/v1/member/projects`
- `GET /api/v1/member/checklist?project_id=`
- `GET /api/v1/member/plan-tasks/{task_id}`
- `PATCH /api/v1/member/plan-tasks/{task_id}/status`
- `GET /api/v1/member/blockers?project_id=`
- `POST /api/v1/member/plan-tasks/{task_id}/blockers`

Task chỉ đi `NOT_STARTED -> IN_PROGRESS -> DONE`. Dependency hoặc blocker chưa
resolved chặn `DONE`; progress chỉ tính task bắt buộc thuộc năm nhóm checklist
hiện hành: Orientation, Access, Setup, Codebase và Convention.

## Branch và milestone

1. `feat/member-foundation`
   - M0: tài liệu chuẩn, test database độc lập, fixture không phụ thuộc seed ID,
     demo identity/seed nhất quán.
   - Commit: `chore: align architecture rules and test baseline`.
2. `feat/member-checklist`
   - M1: project switcher, checklist đọc-only, progress và Task Detail.
   - Commit: `feat(member): add project checklist and task detail`.
   - M2: transition task, dependency/blocker gate và timestamps.
   - Commit: `feat(member): enforce checklist task transitions`.
3. `feat/member-blockers`
   - M3: modal báo blocker, API create/list và trang Blocker của tôi.
   - Commit: `feat(member): add blocker reporting and tracking`.
4. `feat/member-onboarding-core`
   - M4: Playwright E2E, accessibility, light/dark và visual QA cho checklist và
     blocker; rollback First Contribution khỏi scope.
   - Commit QA: `test(member): verify end-to-end onboarding journey`.
   - Commit rollback: `revert(member): remove first contribution scope`.
   - M5: ổn định production cho Engineer Portal: URL state, SSR prefetch, data
     cache/cancellation, typed error, timeout/retry và tách component.
   - Commit runtime: `refactor(member): harden portal navigation and data flow`.
   - Commit verification: `test(member): cover portal resilience and integration`.

Mỗi milestone chỉ commit sau khi test tích lũy pass. Các branch được phát triển
tuần tự; branch sau dựa trên branch trước và không push khi chưa được yêu cầu.

## Quality gates

- Backend: pytest trên PostgreSQL + pgvector test riêng, `alembic upgrade head`,
  `alembic check`, Ruff.
- Frontend: Vitest/Testing Library, ESLint, TypeScript và production build.
- E2E: Playwright chạy với frontend, backend và database thật; kiểm tra project
  switch, Task Detail, transition, blocker, keyboard và theme.
- UI: tuân thủ `DESIGN.md`, không có nút chết, browser dialog hay dữ liệu drawer
  dùng sai đối tượng.

## Trạng thái

- [x] M0 — Foundation
- [x] M1 — Checklist read-only
- [x] M2 — Task transitions
- [x] M3 — Blockers
- [x] M4 — E2E, visual QA và rollback First Contribution
- [x] M5 — URL/data resilience, SSR prefetch và component boundaries

## Checkpoint — 12/08/2026

### Git

- M0 đã được commit trên `feat/member-foundation` tại `8a6e1e8`
  (`chore: align architecture rules and test baseline`).
- Branch đang làm việc là `feat/member-checklist`, được tách trực tiếp từ commit
  M0. Chưa có code M1/M2 hoặc commit tính năng trên branch này.
- `Phan_task_TV2_hoan_chinh.docx` vẫn là file untracked có chủ đích và không được
  đưa vào commit.
- Chưa push branch nào lên remote.

### Gate M0 đã xác nhận

- Backend test stack độc lập: Ruff pass, Alembic upgrade/check pass và `20 passed`.
- Frontend: Vitest `1 passed`, ESLint pass, TypeScript pass và Next.js production
  build pass.
- Seed canonical đã chạy lại hai lần để kiểm tra idempotency. Demo engineer
  `engineer.phoneshop@onboarding.dev` có hai membership active, tên hiển thị
  `Nguyễn Văn A`; blocker demo gắn với task chưa hoàn thành.
- `npm run format:check` hiện báo baseline debt trên 57 file có sẵn. Không format
  hàng loạt ngoài phạm vi; từ M1 chỉ kiểm tra/format file mới hoặc file được sửa.

### Context kỹ thuật cần giữ khi tiếp tục

- Backend là FastAPI + SQLAlchemy async + Alembic; PostgreSQL/pgvector và Alembic
  head là schema canonical. Không tạo migration cho M1/M2 nếu model hiện tại đủ.
- Thêm router/service/DTO member riêng và include router tại
  `src/api/routers/__init__.py`.
- Identity tạm lấy từ `Settings.demo_member_email`; API member phải từ chối cơ chế
  demo khi `APP_ENV=production`, đồng thời luôn xác minh user active, membership
  active, role `ENGINEER` và project active ở server.
- Model liên quan đã có đủ: `ProjectMembership`, `OnboardingPlan`, `PlanTask`,
  `TemplateTask`, `TaskDependency`, `PlanTaskSource`, `DocumentVersion`,
  `KnowledgeDocument` và `Blocker`.
- Dependency lưu giữa các `TemplateTask`; khi kiểm tra một `PlanTask`, cần ánh xạ
  predecessor sang task cùng plan. Tài liệu tham khảo chỉ trả version/document
  active. Progress chỉ tính task `mandatory`.
- Trạng thái plan được phép hiển thị checklist: `APPROVED`, `ACTIVE`,
  `PROJECT_READY`, `ONBOARDING_CLOSED`; `DRAFT` không được coi là plan đã phát hành.
- M2 chỉ cho phép `NOT_STARTED -> IN_PROGRESS -> DONE`; request cùng trạng thái là
  idempotent, không cho đi lùi từ `DONE`. `DONE` bị chặn nếu dependency chưa xong
  hoặc có blocker chưa `RESOLVED`. Ghi `started_at`/`completed_at` trong transaction
  và khóa row khi cập nhật.
- Frontend `/user` hiện chỉ là placeholder. Tạo feature riêng dưới
  `frontend/src/features/member-onboarding`, tuân thủ `DESIGN.md` và wireframe đã
  cung cấp. Các mục chưa làm phải hiển thị locked/coming-soon rõ ràng, không để
  nút chết.

### Điểm tiếp tục chính xác

1. Viết fixture/factory tạo engineer, hai project/membership, approved/active plan,
   task, dependency, source và blocker; mở rộng cleanup theo đúng thứ tự FK.
2. Viết test contract cho bốn endpoint M1/M2, gồm cross-project access, demo auth
   bị tắt ở production, progress mandatory-only, source active-only, transition
   hợp lệ/idempotent và hai gate dependency/blocker.
3. Implement `member_router`, `member_service` và DTO request/response để các test
   pass; chạy isolated backend gate.
4. Implement project picker, member shell, checklist/progress và task drawer tại
   `/user`, sau đó nút Bắt đầu/Đánh dấu DONE; thêm Vitest component/API tests.
5. Chạy test tích lũy và commit M1, M2 riêng theo danh sách milestone ở trên.

### Cập nhật sau checkpoint

- M1 đã hoàn thành trên `feat/member-checklist`: API member tự xác minh demo
  identity/membership, project picker, Engineer shell, progress mandatory-only,
  checklist theo category và Task Detail drawer.
- Gate M1: backend Ruff + Alembic upgrade/check + `30 passed`; frontend Vitest
  `2 passed`, ESLint, TypeScript, Prettier cho feature mới và production build
  đều pass.
- Sau M1, contract transition M2 và test dependency/blocker đã có ở backend; M2
  tiếp tục nối action vào drawer và bổ sung test UI mutation.
- M2 đã nối action Bắt đầu/DONE, trạng thái lưu/lỗi, refresh progress và toast vào
  Task Detail drawer. Backend khóa row và thực thi transition idempotent cùng
  dependency/blocker gate.
- Gate M2: frontend Vitest `3 passed`, ESLint, TypeScript, Prettier feature và
  production build pass; smoke API seed thật xác nhận 2 project, 7 category và
  đúng task detail cho `Nguyễn Văn A`.
- Browser plugin không tìm thấy browser khả dụng trong phiên 12/08/2026; visual QA
  được thực hiện bằng Playwright Chromium của project.
- M3 hoàn thành trên `feat/member-blockers`: GET/POST blocker có authorization
  theo membership, form báo blocker, badge đếm và trang “Blocker của tôi”. Tạo
  blocker không đổi `PlanTask.status`; MVP không trả routing/SLA/attachment.
- Gate M3: backend Ruff + Alembic upgrade/check + `34 passed`; frontend Vitest
  `4 passed`, ESLint, TypeScript, Prettier feature và production build pass.
- Hạ tầng E2E cô lập vẫn được giữ: PostgreSQL/pgvector + FastAPI seed thật +
  Next.js, Playwright Chromium và script PowerShell tự khởi tạo/dọn container.
- Journey E2E hiện bao phủ project picker, checklist/progress, Task Detail, tạo và
  theo dõi blocker, transition task, đóng drawer bằng Escape, dark mode và project
  switch; không còn bước First Task/First PR.
- Ngày 12/08/2026, First Contribution được rollback khỏi Engineer Portal theo yêu
  cầu sản phẩm. API First PR, menu/view, DTO/hook liên quan và test riêng bị xóa;
  checklist/progress cũng loại `FIRST_TASK` và `FIRST_PR`.
- Gate sau rollback: backend Ruff + Alembic upgrade/check + `36 passed`; frontend
  Vitest `4 passed`, Playwright `1 passed`, ESLint, TypeScript, Prettier và
  production build đều pass.
- Branch hiện tại là `feat/member-onboarding-core`; rollback đã pass toàn bộ gate.
  Chưa push branch. File `Phan_task_TV2_hoan_chinh.docx` vẫn untracked có chủ đích
  và không được stage.

## Checkpoint — 13/08/2026

### M5 đã hoàn thành

- `project`, `view` và `task` là URL state tại `/user`; project/view/task navigation
  dùng link thật, hỗ trợ deep-link, browser Back/Forward và mở tab mới. Đóng drawer
  chuẩn hóa URL bằng `replace`.
- Theme lưu tại `localStorage` và tôn trọng system preference khi chưa có lựa chọn.
- Data layer dùng TanStack Query với query key riêng theo project/task, cache 60
  giây, garbage collection 5 phút, request dedup, `AbortSignal`, timeout 12 giây và
  retry giới hạn cho 408/429/5xx. Mutation không retry tự động.
- Mutation cập nhật cache từ response API; chỉ invalidate checklist nền sau DONE để
  đồng bộ task phụ thuộc. Project ID được đóng gói cùng mutation để response đến
  muộn không thể ghi nhầm cache sau khi người dùng chuyển project.
- `ApiError` giữ HTTP status/detail; UI tách lỗi load/action theo projects,
  checklist, task và blocker, đồng thời phân biệt 401/403/404.
- `/user` là dynamic server route, prefetch projects/checklist/blockers/task song
  song từ URL rồi hydrate client cache. `INTERNAL_API_URL` được dùng cho kết nối
  backend nội bộ khi SSR.
- `MemberPortal` chỉ còn vai trò orchestration; sidebar, topbar, checklist, blockers,
  project picker và feedback đã tách component. Workspace có `key=projectId` nên
  search/notice/modal không rò sang project mới.

### Bằng chứng gate M5

- Frontend: ESLint pass, TypeScript pass, Prettier pass, Vitest `14 passed`, Next
  production build pass và `/user` được xác nhận server-rendered động.
- Backend cô lập: Ruff pass, Alembic upgrade/check pass, pytest `29 passed` trên
  ParadeDB/PostgreSQL test database.
- Playwright: `1 passed` với backend/database seed thật; journey xác nhận URL state,
  browser Back đóng drawer, theme còn sau reload, mutation, blocker và đổi project.
- Test hồi quy riêng bao phủ response project cũ bị abort, deep-link không waterfall,
  cache khi chuyển lại project, HTTP error/timeout và mutation hoàn tất sau khi đã
  chuyển project.

### Git và phạm vi review

- Chỉ branch tích hợp `feat/member-onboarding-core` có upstream
  `origin/feat/member-onboarding-core`; ba branch milestone trước vẫn là local
  history và không cần merge/push riêng.
- Các thay đổi Docker/Alembic test ở M5 chỉ đồng bộ test gate với migrations mới đã
  được merge từ `develop` (ParadeDB `pg_search`/`pg_cron` và extension-owned
  objects); không thay đổi contract sản phẩm của Thành viên 2.
- M5 được tách thành runtime và verification/integration để reviewer có thể đọc
  kiến trúc trước, sau đó kiểm tra bằng chứng test.
