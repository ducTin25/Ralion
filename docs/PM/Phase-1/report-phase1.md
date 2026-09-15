# Báo cáo hoàn thành Phase 1 — Thành viên & Add Member Wizard

> Theo [plan-phase1-members.md](plan-phase1-members.md). Trạng thái: **HOÀN THÀNH**, đã test và chạy thật cả BE + FE.
> **Cập nhật (redesign giao diện)**: đã thiết kế lại toàn bộ UI Phase 1 theo đúng [RALION_UI_DESIGN_GUIDE.md](../RALION_UI_DESIGN_GUIDE.md) (design tokens, sidebar/topbar shell, icon SVG sprite, component chuẩn) — xem mục 7.
> **Cập nhật (merge `develop` + sửa UI/data)**: đã pull `develop` (thêm field sync + 3 trigger bất biến kiến trúc), sửa code/test cho khớp, dọn data rác, sửa sidebar bị vỡ layout, thêm nút Kích hoạt lại — xem mục 8.
> **Cập nhật (v2 — sửa phạm vi quyền hạn)**: phát hiện + sửa lỗi PM được phép tạo project/thêm thành viên (sai — chỉ Admin làm việc này), thiết kế lại hoàn toàn trang "Thành viên" thành theo dõi Onboarding Plan, thêm phân trang + search + sidebar/topbar thật — xem [plan-phase1-v2-rescope.md](plan-phase1-v2-rescope.md) và mục 10 bên dưới.

## Tóm tắt thay đổi

| Loại | Trước | Sau |
|---|---|---|
| Backend | `project_router.py`, `project_membership_router.py`, `project_service.py`, `project_membership_service.py` — toàn bộ chỉ là **file khung comment** | Code CRUD thật, có test, chạy được qua Docker |
| Frontend | `product-manager/page.tsx` — placeholder tĩnh, không có DTO/API client nào | 3 khối UI thật (danh sách project, danh sách thành viên, thêm thành viên) gọi API thật |
| Model/Migration | — | **Không đổi** — `Project`/`ProjectMembership` đã đúng spec sẵn, không cần migration mới |
| Test | 3 test cũ (`test_health`, 2 test agent) | **+12 test mới**, tổng 15/15 pass |
| Data | 8 user, 6 membership | +6 engineer demo, +1 membership PM (chèn thẳng DB, không sửa seed script/sheet) |

## 1. Quyết định thiết kế quan trọng (để tránh conflict với TV2/TV3/TV4)

### 1.1 Route path: `/pm` là sub-path trên từng endpoint, không phải prefix router
Sau khi trao đổi, chốt: **không** đặt `prefix="/pm/..."` ở cấp `APIRouter` (vì sẽ chặn luôn cả CRUD thô mà Admin/role khác cần dùng chung), mà thêm `/pm` vào **từng path operation cụ thể**:

```python
router = APIRouter(prefix="/projects", tags=["pm-projects"])

@router.post("/pm", ...)      # POST /api/v1/projects/pm
@router.get("/pm", ...)        # GET  /api/v1/projects/pm
@router.get("/pm/{id}", ...)    # GET  /api/v1/projects/pm/{id}
```

Lý do: `Project`/`ProjectMembership` là dữ liệu dùng chung toàn hệ thống, không phải sở hữu riêng PM. Đặt `/pm` ở path operation đánh dấu rõ *"đây là API do module PM code và gọi"*, giúp Thành viên 4 (Admin/RBAC) hoặc Thành viên 2 (Engineer) không vô tình sửa trùng file khi họ cần thao tác khác trên cùng entity — họ sẽ tạo route riêng (`/admin/...`, hoặc gọi lại chính route này) thay vì động vào file `project_router.py`/`project_membership_router.py`.

### 1.2 Ai code `ProjectMembership`?
Tài liệu chia task ghi `ProjectMembership` thuộc Thành viên 4 (Admin/RBAC), nhưng màn hình "Add Member Wizard" lại thuộc giao diện PM (UC-03) và là bước bắt buộc trước khi sinh Candidate Plan. Đã quyết định: **Thành viên 1 (tôi) code CRUD thật cho `ProjectMembership`** — vì PM là người dùng nhiều nhất luồng này (thêm thành viên → sinh plan ngay sau, xem Phase 4). TV4 sau này chỉ cần **gọi lại** API `/project-memberships/pm` có sẵn, hoặc build thêm layer Auth/RBAC **trên** route đã có (dependency injection), không cần viết lại service/router này.

⚠️ **Cần đồng bộ với TV4** trước khi họ bắt đầu code phần Admin — tránh 2 người viết 2 router khác nhau cho cùng 1 entity.

### 1.3 Endpoint mới không có trong danh sách gốc
`GET /project-memberships/pm/by-user/{user_id}` (project mà 1 user tham gia) và `GET /project-memberships/pm?project_id=` (trả kèm email/tên user, join sẵn) — 2 endpoint phát sinh khi code thật, cần thiết để FE không phải gọi API nhiều lần. Không đụng file/route của ai khác.

### 1.4 Chưa có đăng nhập → hardcode `CURRENT_PM_USER_ID`
`frontend/src/lib/api.ts` có hằng số `CURRENT_PM_USER_ID = 21` (user `pm.phoneshop@onboarding.dev`, đã gán quản lý cả PHONESHOP và TOURBOOK để test đúng case "1 PM quản lý nhiều project"). Comment rõ trong code: **xoá hằng số này khi có Auth thật (TV4)**, thay bằng user lấy từ session đăng nhập.

## 2. Backend — file đã tạo/sửa

- `src/dto/request/project_request_dto.py`, `src/dto/response/project_response_dto.py` (mới)
- `src/dto/request/project_membership_request_dto.py`, `src/dto/response/project_membership_response_dto.py` (mới — có thêm `ProjectMembershipDetailResponseDTO` join User)
- `src/services/project_service.py`, `src/services/project_membership_service.py` (từ file khung → code CRUD thật, theo đúng pattern `user_service.py` đã có: soft-delete qua `status`, không hard-delete)
- `src/api/routers/project_router.py`, `src/api/routers/project_membership_router.py` (từ file khung → code thật)
- `src/api/routers/__init__.py` (đăng ký 2 router mới vào `api_router`)
- `pytest.ini` (mới — xem mục 4)

## 3. Frontend — file đã tạo/sửa

**Nguyên tắc bắt buộc**: toàn bộ code Phase 1 nằm gọn trong `frontend/src/features/project-management/` — **không** đụng file dùng chung (`globals.css`, `layout.tsx`, `components/ui/` gốc, `package.json` ngoài việc thêm `sass`) để tránh conflict với TV2/TV3/TV4 khi họ code phần của họ. DTO cũng chuyển từ `src/dto/` (thư mục chung ban đầu) vào hẳn trong feature folder.

```
frontend/src/features/project-management/
  dto/requestDTO/{project,projectMembership}.request.ts
  dto/responseDTO/{project,projectMembership,user}.response.ts
  api.ts                                    # lớp gọi API, tách khỏi component
  hooks/useProjectManagement.ts             # state + data fetching cho page
  components/
    PmIconSprite.tsx                        # SVG icon sprite riêng PM (14 icon, xem mục 7)
    PmShell.tsx + .module.scss              # sidebar + topbar, theo mục 4 design guide
    ui/                                      # primitive riêng PM, mỗi cái 1 .module.scss
      PmButton, PmCard, PmPill, PmModal, PmToast, PmField, PmTable (.tsx + .module.scss)
    projects/
      ProjectListView.tsx + .module.scss     # view "Dự án"
      CreateProjectForm.tsx + .module.scss
    members/
      MembersView.tsx + .module.scss         # view "Thành viên"
      ProjectSwitcher.tsx + .module.scss      # dropdown chọn project ở topbar
      AddMemberForm.tsx + .module.scss

frontend/src/lib/api.ts   # CHỈ thêm hằng số endpoint + CURRENT_PM_USER_ID + helper parseJsonOrThrow (file dùng chung, chỉ thêm, không sửa/xoá gì của người khác)
frontend/src/app/product-manager/page.tsx   # route entry point, chỉ ghép PmShell + 2 view
```

Styling dùng **SCSS Modules** (`.module.scss`, mỗi component 1 file riêng, tự động scope class name — không thể đụng CSS của ai khác dù trùng tên class). Thêm `sass` vào `devDependencies`. Không dùng chung `globals.css`/Tailwind cho phần PM để giữ đúng nguyên tắc "code trong thư mục PM thôi".

## 4. Sự cố kỹ thuật gặp phải + cách xử lý

1. **`Event loop is closed` khi chạy nhiều test DB liên tiếp** (Windows + asyncpg + pytest-asyncio) — không phải lỗi endpoint (đã xác nhận từng test pass riêng lẻ). Nguyên nhân: engine SQLAlchemy async tạo 1 lần ở module-level (`src/model/session.py`) nhưng mỗi test mặc định có event loop riêng, connection pool bị lẫn giữa các loop. **Fix**: thêm `pytest.ini` gộp event loop cho toàn bộ session test (`asyncio_default_fixture_loop_scope = session`, `asyncio_default_test_loop_scope = session`) — không sửa code backend.
2. **Lỗi lint `react-hooks/set-state-in-effect`** (rule mới của React 19/Next 16) — cảnh báo gọi hàm setState qua `useCallback` trong `useEffect`. Đây là pattern "fetch data khi mount" hợp lệ theo chính tài liệu React dẫn trong thông báo lỗi; đã disable có chú thích rõ lý do tại đúng 2 dòng, không tắt rule toàn cục.
3. **`npm run format:check` fail trên 28 file** kể cả file chưa từng đụng tới (README.md, package.json, các page cũ...) — xác nhận đây là vấn đề có sẵn của repo (khả năng CRLF/LF), không phải do Phase 1 gây ra. Chỉ chạy `prettier --write` trên đúng các file mới/sửa trong Phase 1, không đụng 28 file kia để tránh diff không liên quan.

## 5. Bằng chứng hoạt động thật

### 5.1 Test tự động — 15/15 PASS
```
tests/test_agents/test_graph.py::test_agent_basic_flow PASSED
tests/test_agents/test_graph.py::test_agent_state_structure PASSED
tests/test_api/test_project_memberships.py::test_create_membership PASSED
tests/test_api/test_project_memberships.py::test_create_membership_duplicate PASSED
tests/test_api/test_project_memberships.py::test_list_memberships_by_project PASSED
tests/test_api/test_project_memberships.py::test_update_membership_role PASSED
tests/test_api/test_project_memberships.py::test_deactivate_membership PASSED
tests/test_api/test_project_memberships.py::test_list_memberships_by_user PASSED
tests/test_api/test_projects.py::test_create_project PASSED
tests/test_api/test_projects.py::test_create_project_duplicate_key PASSED
tests/test_api/test_projects.py::test_list_projects PASSED
tests/test_api/test_projects.py::test_get_project_not_found PASSED
tests/test_api/test_projects.py::test_update_project PASSED
tests/test_api/test_projects.py::test_archive_project PASSED
tests/test_api/test_routes.py::test_health PASSED
============================= 15 passed in 0.99s ==============================
```
`alembic check` → `No new upgrade operations detected` (đúng dự kiến, không đổi model).

### 5.2 Backend chạy thật trong Docker — curl thật, dữ liệu thật
```
GET /api/v1/project-memberships/pm/by-user/21
→ [{"membership_id":7,...,"project_id":4,"project_role":"PM",...},
    {"membership_id":19,...,"project_id":5,"project_role":"PM",...}]
   (xác nhận PM user 21 quản lý 2 project: PHONESHOP + TOURBOOK)

GET /api/v1/projects/pm/4
→ {"project_id":4,"key":"PHONESHOP","name":"PhoneShop API",...,"status":"ACTIVE",...}

GET /api/v1/project-memberships/pm?project_id=4
→ 4 thành viên: PM PhoneShop API, Engineer PhoneShop API, Tran Thi B, Nguyen Van A
   (kèm sẵn email/display_name, đúng thiết kế join)
```

### 5.3 Frontend chạy thật
- `npx tsc --noEmit` — sạch, 0 lỗi.
- `npm run lint` — sạch, 0 lỗi.
- `npm run build` (production) — **build thành công**, route `/product-manager` được generate như static entry (Turbopack, "Compiled successfully").
- `npm run dev` — start thành công, `GET /product-manager` → **HTTP 200**, HTML trả đúng branding **"Ralion"** + tiêu đề **"Dự án bạn quản lý"** (view mặc định).
- Server chạy tại **http://localhost:3000/product-manager** — mở trình duyệt xem trực tiếp: sidebar có đủ 6 mục (Tổng quan/Master Template/Tài liệu dự án/Support Requests hiện "Sắp có", disabled), bấm "Dự án" xem 2 project PM quản lý (PHONESHOP, TOURBOOK), bấm "Thành viên" → chọn project ở topbar → xem bảng thành viên → bấm "+ Thêm thành viên" mở modal thật (không phải `alert()`).

## 6. Ngoài phạm vi Phase 1 (chưa làm, để phase sau)
- Access Scope/ACL, wizard 3 bước đầy đủ như mockup (đã quyết định hoãn từ plan tổng).
- Auth/RBAC thật — vẫn dùng `CURRENT_PM_USER_ID` hardcode.
- Đồng bộ với TV4 về quyền sở hữu code `ProjectMembership` (mục 1.2) — **cần làm trước khi TV4 bắt đầu phần Admin**.
- 4 mục sidebar còn lại (Tổng quan, Master Template, Tài liệu dự án, Support Requests) — hiện disabled + tag "Sắp có" theo đúng nguyên tắc "không có nút chết" trong design guide (chỉ enable khi phase tương ứng code xong).

## 7. Redesign giao diện theo RALION_UI_DESIGN_GUIDE.md

Sau khi có bản UI đầu tiên (Tailwind ad-hoc), đã thiết kế lại toàn bộ theo đúng tài liệu chuẩn tại `docs/PM/RALION_UI_DESIGN_GUIDE.md` (rút ra từ mockup tham khảo), áp dụng đúng token — không bịa giá trị mới:

- **Design tokens**: màu (`--pm-accent #2657D9`, semantic success/warning/critical...), bo góc chỉ 3 mức (5/6/8px), spacing, shadow, easing — copy nguyên từ guide, đặt tên có tiền tố `--pm-` và scope trong class `.pmShell` (không đặt ở `:root` để không rò ra ngoài trang PM).
- **Font**: `-apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif` — đúng `--font-ui` trong guide, không dùng Geist (vốn chưa thật sự được cấu hình trong repo).
- **Icon**: SVG sprite riêng (`PmIconSprite.tsx`, 15 icon: logo/folder/users/grid/book/doc/life/plus/arrow/chevron-down/x/check2/sun/moon/close-ring/alert) — không dùng emoji hay icon font, đúng mục 6 guide.
- **Shell**: sidebar 224px cố định trái + topbar 54px, theo đúng mục 4 guide. Sidebar hiện đủ 6 mục như bản tham khảo (Tổng quan, Dự án, Master Template, Tài liệu dự án, Thành viên, Support Requests) — 2 mục Phase 1 làm (Dự án, Thành viên) bấm được, 4 mục còn lại disabled + tag "Sắp có" (không phải nút chết, không giả vờ hoạt động).
- **Component chuẩn**: Button (primary/ghost/danger/sm), Card + PageHead, Pill (trạng thái, màu semantic) + Tag (nhãn trung tính), Table (thead nền riêng), Modal (thay `alert()`/form nội tuyến — "Thêm thành viên" và "Tạo project" giờ là modal thật, đóng bằng Esc hoặc bấm nền, không dùng dialog gốc trình duyệt), Toast (xác nhận sau khi lưu, tự biến mất ~2.6s).
- **Theme**: mặc định light, có nút toggle dark ở topbar (đổi `data-theme` trên `.pmShell`, không phụ thuộc OS).
- **Cách ly khỏi phần code khác**: toàn bộ nằm trong `features/project-management/`, dùng SCSS Modules (tự scope, không thể trùng class với ai) — không đụng `globals.css`/`layout.tsx`/`components/ui` gốc.

Đã verify lại: `tsc --noEmit` sạch, `lint` sạch, `next build` production thành công, `pytest` 15/15 vẫn pass (backend không đổi), dev server chạy thật trả HTTP 200 đúng nội dung mới.

## 8. Merge `develop` + sửa data/UI theo phản hồi

### 8.1 Merge nhánh `develop` — thêm sync field + 3 trigger bất biến kiến trúc
Teammate merge migration `a1b2c3d4e5f6` vào `develop`: thêm `Project.sync_status`/`Project.last_synced_at`, và **3 database trigger** ép buộc bất biến (không thể lách qua code, Postgres tự chặn):
- **INV1**: user có `system_role` (ADMIN/HR) không được có `ProjectMembership`, và ngược lại.
- **INV2**: mỗi `KnowledgeDocument` phải có đúng 1 `DocumentVersion.status=ACTIVE` (liên quan Phase 3, chưa làm).
- **INV7**: `OnboardingPlan.status` chỉ đi tới, không lùi (liên quan Phase 4/5, chưa làm).

Đã `git merge origin/develop` (fast-forward sạch, không conflict — develop không đụng file Phase 1), `alembic upgrade head` áp migration, xác nhận đủ 5 trigger + 2 cột mới trong DB.

### 8.2 Sự cố phát sinh từ INV1 + cách sửa
Test cũ dùng `user_id=19` (admin, có `system_role`) để tạo membership — vi phạm INV1 ngay khi trigger có hiệu lực. Router ban đầu chỉ bắt `IntegrityError`, nhưng lỗi từ trigger là `DBAPIError` (loại khác) → không bắt được → **crash không rollback, làm hỏng session cho mọi test chạy sau đó trong cùng phiên** (lộ ra dưới dạng lỗi `sqlalchemy.exc.DBAPIError` lan sang các test khác vốn không liên quan). Đã sửa:
- `project_membership_router.py`: bắt thêm `DBAPIError`, rollback + trả 409 với message rõ ràng lấy từ chính message trigger raise ra (`str(exc.orig)`), thay vì để lỗi 500 không rõ nguyên nhân.
- Test: không dùng user có `system_role` làm membership nữa — mỗi test tự tạo 1 user mới (`system_role=None`) qua API thật, có test riêng `test_create_membership_rejects_system_role_user` xác nhận API trả đúng 409 khi cố tình vi phạm INV1.
- Cập nhật `ProjectResponseDTO` (BE + FE) thêm `sync_status`/`last_synced_at` — DTO cũ thiếu 2 field mới này (bug thật, không chỉ là docs lỗi thời).
- Cập nhật cả 2 doc plan (`plan-pm.md`, `Phase-1/plan-phase1-members.md`) ghi rõ 3 invariant trên và ảnh hưởng tới Phase 3/4 sau này.

### 8.3 Dọn dữ liệu rác do test không có cleanup
Phát hiện qua pgAdmin: 47 project rác `TEST*` (từ các lần chạy `pytest` trước đó — tests không có DB riêng, chạy thẳng lên DB thật, không tự dọn). Đã:
- Xoá thủ công 1 lần toàn bộ rác cũ (kiểm tra FK trước khi xoá).
- Thêm `tests/test_api/conftest.py` — fixture `test_data` **hard-delete thật** (không phải soft-delete như app) mọi project/membership/user test tự tạo, theo đúng thứ tự tránh vi phạm FK (membership → project/user). Xác nhận: chạy lại toàn bộ test 2 lần liên tiếp, DB **không còn dư 1 row rác nào**.

### 8.4 Giải thích 2 điểm bạn hỏi
- **"Nút vô hiệu hoá bấm vô mất thành viên?"** — Không, đây luôn là xoá mềm (đổi `status` sang `INACTIVE`), thành viên **vẫn hiện trong danh sách** với pill trạng thái đổi màu — đúng như đã thấy trong ảnh bạn gửi (hàng "PM PhoneShop API" vẫn còn, chỉ đổi pill sang INACTIVE). Bổ sung thêm: giờ có nút **"Kích hoạt lại"** cho hàng INACTIVE (gọi `PATCH .../pm/{id}` đổi `status=ACTIVE`), hoàn thiện vòng đời khoá/mở khoá thành viên.
- **`primary_pm_membership_id` (7, 9, 11...) không khớp `CURRENT_PM_USER_ID=21`?** — Không phải lỗi, 2 giá trị này khác bản chất: `primary_pm_membership_id` là **membership_id** (khoá của bảng `project_memberships`), còn `21` là **user_id** (khoá của bảng `users`). Ví dụ project PHONESHOP có `primary_pm_membership_id=7` — tra `project_memberships.membership_id=7` ra đúng `user_id=21` (PM PhoneShop API), tức 2 giá trị đang tham chiếu đúng, chỉ là 2 loại khoá khác nhau nên số khác nhau là chuyện bình thường.

### 8.5 Sửa giao diện xấu (sidebar vỡ layout)
Ảnh bạn gửi cho thấy nhãn "Master Template"/"Tài liệu dự án" bị wrap xuống dòng đè lên tag "SẮP CÓ". Nguyên nhân: label và tag cùng nằm trong 1 hàng flex nhưng label không có `flex`/`overflow` rules, chữ dài tự động xuống dòng đẩy tag lệch. Đã sửa: label giờ nằm trong `<span>` riêng (`flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap`), tag/icon cố định `flex:none` — nhãn dài giờ cắt gọn 1 dòng (`...`) thay vì vỡ layout. Tăng sidebar từ 224px → 240px để đa số nhãn vẫn hiện đủ chữ.

### 8.6 Bằng chứng sau khi sửa
- `pytest tests/ -v` → **16/16 pass** (thêm 1 test mới cho INV1).
- DB sau khi chạy test 2 lần liên tiếp: `SELECT count(*) FROM projects WHERE key LIKE 'TEST%'` → **0**, tương tự cho user rác → **0**.
- `curl .../projects/pm/4` → response có đủ `sync_status`/`last_synced_at`.
- `curl -X PATCH .../project-memberships/pm/7 -d '{"status":"ACTIVE"}'` → kích hoạt lại thành công membership PM chính của PHONESHOP (đã bị khoá lúc bạn test thử trước đó).
- `tsc --noEmit`, `lint`, `next build` — sạch cả 3.
- Docker backend rebuild lại, dev server frontend restart sạch — cả 2 chạy thật, HTTP 200.

## 9. Nâng cấp thêm giao diện (theo phản hồi "còn xấu, làm đẹp nhất")

Áp dụng nguyên tắc thiết kế dashboard: **"surface the summary before the detail"** (bảng dữ liệu thô không đủ, phải cho thấy tổng quan trước) + **encode state bằng hình chứ không chỉ chữ** (avatar/pill thay vì text đơn thuần) — tôn trọng đúng token màu/font đã có trong `RALION_UI_DESIGN_GUIDE.md` (không đổi sang bộ màu khác, chỉ nâng chất lượng thực thi):

- **`PmAvatar`** (`components/ui/PmAvatar.tsx` + `avatarColor.ts`): avatar vuông màu cố định theo hash(seed) — cùng 1 project/user luôn ra đúng 1 màu trong bảng màu 7 màu (ưu tiên xanh Ralion + các màu phụ), không cần ảnh thật. Áp cho từng dòng trong bảng "Dự án" (avatar theo `key`) và "Thành viên" (avatar theo `email`).
- **`PmKpiRow`** (`components/ui/PmCard.tsx`): hàng thẻ KPI đầu mỗi trang — "Dự án" hiện Tổng project/Đang hoạt động/Đã lưu trữ; "Thành viên" hiện Tổng thành viên/Đang hoạt động/PM/Engineer. Giải quyết đúng cảm giác "trống nhiều" — trước đây trang chỉ có 1 bảng text thẳng vào nội dung, giờ có lớp tổng quan trước khi vào chi tiết.
- Bảng "Dự án" thêm cột **Trạng thái đồng bộ** (hiện `sync_status` — field mới từ `develop`, trước đây có trong DB nhưng không hiện ở UI).

Verify lại sau khi thêm: `tsc --noEmit` sạch, `lint` sạch, `pytest` 16/16 pass, backend rebuild Docker lại (`docker compose up -d --build`), dev server frontend restart sạch — `curl http://localhost:8000/health` → `{"status":"ok"}`, `curl http://localhost:3000/product-manager` → HTTP 200.

## 10. v2 — Sửa phạm vi quyền hạn + thiết kế lại "Thành viên" thành theo dõi Onboarding Plan

Theo [plan-phase1-v2-rescope.md](plan-phase1-v2-rescope.md) (đã duyệt). Đây là đợt sửa **quan trọng nhất** của Phase 1: 2 tính năng đã code trước đó (Tạo project, Thêm thành viên) **sai phạm vi quyền hạn** — cả 2 việc này thuộc về Admin (TV4), không phải PM. Đã gỡ khỏi giao diện PM và thiết kế lại hoàn toàn mục đích trang "Thành viên".

### 10.1 Bug data đã sửa: 1 project có 2 PM

Xác nhận qua query thật (SQL trong mục 1 của plan v2): TOURBOOK có 2 membership `PM` cùng lúc (`pm.phoneshop` bị tôi tự thêm nhầm ở Phase 1 gốc để demo, cộng với `pm.tourbook` — PM gốc đúng). Vi phạm luật nghiệp vụ "1 project = đúng 1 PM, nhiều Engineer". Đã hard-delete membership sai (`DELETE FROM project_memberships WHERE membership_id = 19`), xác nhận lại cả 3 project (PHONESHOP/TOURBOOK/FURNISTORE) đều đúng 1 PM.

### 10.2 Gỡ bỏ 2 tính năng sai quyền hạn khỏi giao diện PM

| Tính năng | Trước | Sau |
|---|---|---|
| "Tạo project" | Nút + modal trong `ProjectListView` | **Đã xoá** — trang "Dự án" giờ chỉ xem + chọn |
| "Thêm thành viên" | Nút + modal trong `MembersView` | **Đã xoá** — trang "Thành viên" giờ chỉ xem |
| "Khoá"/"Kích hoạt lại" thành viên | 2 nút hành động mỗi dòng | **Đã xoá** — đây cũng là việc quản lý người, thuộc Admin |

Quyết định (theo mục 2 plan v2, đã xác nhận mặc định vì user nói "tiến hành code đi"): **giữ nguyên toàn bộ API backend** (`POST /projects/pm`, `POST/PATCH/DELETE /project-memberships/pm/...`) — đây là hạ tầng CRUD dùng chung, Admin (TV4) sẽ tái sử dụng sau. Chỉ gỡ lời gọi các API này khỏi giao diện/luồng thao tác của PM. File đã xoá vì không còn dùng: `CreateProjectForm.tsx`+`.module.scss`, `AddMemberForm.tsx`+`.module.scss`, và 2 DTO request tương ứng (`project.request.ts`, `projectMembership.request.ts`) — không còn nơi nào import.

### 10.3 Trang "Thành viên" đổi mục đích hoàn toàn: theo dõi Onboarding Plan

Không còn là màn hình thêm/xoá người — giờ PM dùng trang này để xem **Engineer nào đã có Onboarding Plan, Engineer nào chưa**:

- Danh sách lọc còn **đúng role ENGINEER** (PM của chính project không hiện trong danh sách này nữa — không có gì để "theo dõi" ở chính mình).
- Cột mới **"Onboarding Plan"**: chưa có Plan → pill xám "Chưa có Plan"; đã có Plan → pill theo đúng status thật (`DRAFT`→"Nháp", `APPROVED`→"Đã duyệt", `ACTIVE`→"Đang thực hiện", `PROJECT_READY`/`ONBOARDING_CLOSED`→"Sẵn sàng bàn giao"/"Hoàn tất", màu semantic neutral/progress/success đúng theo 3 nhóm này).
- Action cuối dòng: **"Tạo Onboarding Plan"** (chưa có Plan) hoặc **"Xem tiến độ"** (đã có Plan) — cả 2 đang **disabled + tooltip "Sắp có"**, đúng nguyên tắc "không nút chết" của design guide (nút vẫn hiện đúng ngữ cảnh, không giả vờ hoạt động) vì luồng tạo Plan thật (chọn TemplateVersion đã duyệt) thuộc Phase 4, luồng xem milestone thuộc Phase 5 — cả 2 chưa code trong Phase 1.
- Thêm bộ lọc theo trạng thái Plan (dropdown: Tất cả / Chưa có Plan / Nháp / Đã duyệt / Đang thực hiện / Sẵn sàng bàn giao / Hoàn tất) + ô search tên/email.
- Thành viên bị Admin khoá (`status=INACTIVE`) vẫn hiện trong danh sách (chỉ xem, không thao tác) kèm tag nhỏ "Đã khoá" cạnh tên — theo đúng gợi ý ở mục 3.1 plan v2 ("có thể vẫn hiện nhỏ dạng tag phụ").

**Backend cần thêm** (nhỏ, không phải build hết Phase 4): route **read-only** kiểm tra Plan đã tồn tại chưa —

```python
GET /onboarding-plans/pm/by-project/{project_id}  → list[OnboardingPlanResponseDTO]  (bulk, FE tự map theo membership_id)
GET /onboarding-plans/pm/by-membership/{membership_id} → OnboardingPlanResponseDTO | 404
```

File mới: `src/dto/response/onboarding_plan_response_dto.py`, `src/services/onboarding_plan_service.py`, `src/api/routers/onboarding_plan_router.py` — đăng ký vào `api_router` trong `src/api/routers/__init__.py`. Không có route tạo/sửa Plan (đúng phạm vi Phase 1 v2, luồng tạo thật là Phase 4).

### 10.4 Trang "Dự án" — bỏ tạo mới, thêm search + phân trang

Chỉ còn xem danh sách project PM đang phụ trách (đọc từ `GET /project-memberships/pm/by-user/{id}` lọc `project_role=PM`, join `GET /projects/pm/{id}`), không còn hành động tạo/sửa/xoá nào khác (đúng câu trả lời mặc định cho câu hỏi mở ở mục 4.3 plan v2: "chỉ xem + chọn").

### 10.5 UI polish theo mục 5, 8, 9 của plan v2

- **Giảm khoảng cách 2 bên**: `.content` padding `24px`→`20px`, `.contentInner` bỏ `max-width:1100px` cố định → `1400px` (đỡ trống trên màn hình rộng, vẫn không tràn nội dung).
- **KPI card có icon**: `PmKpiRow` (`components/ui/PmCard.tsx`) giờ nhận thêm field `icon` bắt buộc mỗi item — vòng tròn icon accent bên trái mỗi số liệu (vd `folder` cho Tổng project, `check2` cho Đang hoạt động, `users`/`check-circle` cho các KPI Thành viên). Thêm 3 icon mới vào `PmIconSprite.tsx`: `search`, `bell`, `check-circle`.
- **Trạng thái có chú thích**: mỗi bảng có 1 dòng caption nhỏ dưới bảng giải thích nghĩa pill (vd "ACTIVE = project đang onboarding · ARCHIVED = đã lưu trữ...").
- **Search + filter**: thêm ô search thật trong topbar (icon `search`), lọc client-side theo `key`/`name` (Dự án) hoặc `display_name`/`email` (Thành viên) — đủ dùng vì danh sách 1 PM quản lý không nhiều, chưa cần server-side search.
- **Sidebar footer lấy đúng data thật** (bug đã xác nhận: trước đây hardcode cứng chữ "PM PhoneShop API" bất kể `CURRENT_PM_USER_ID` là ai): `PmShell` giờ gọi `GET /api/v1/users/{CURRENT_PM_USER_ID}` khi mount, hiện avatar màu + **họ tên thật + email thật** (không chỉ tên — theo yêu cầu bổ sung sau khi xem bản đầu chỉ có tên). Trong lúc tải: hiện skeleton mờ (pulse animation), không hiện tên sai/tên cũ.
- **Topbar đầy đủ hơn**: breadcrumb có icon đi kèm (khớp icon của mục đang xem, lấy trực tiếp từ `NAV_ITEMS`), thêm ô search thật, thêm icon chuông thông báo (disabled + tooltip "Sắp có" — chưa có hệ thống notification, không giả vờ hoạt động), tăng chiều cao `54px`→`58px`, thêm `box-shadow` nhẹ để tách biệt content khi cuộn.
- **Phân trang**: component dùng chung mới `PmTableFooter` (`components/ui/PmTableFooter.tsx`+`.module.scss`) — nhận `total/page/pageSize/onPageChange`, page size cố định 10, hiện "Hiển thị X–Y trong Z kết quả" + nút Trước/Sau disabled đúng ở 2 đầu danh sách. Áp dụng cho cả bảng Dự án và bảng Thành viên.

**Đã cân nhắc rồi bỏ**: bản đầu có thêm khối "Dự án đang xem" trong sidebar để lấp khoảng trống dọc giữa menu và footer — sau khi xem thực tế, bạn phản hồi thấy thừa nên đã **gỡ bỏ hẳn** (component, prop `activeProject`, CSS liên quan), giữ sidebar gọn theo đúng ý.

### 10.6 Dữ liệu demo: PM quản lý 2 project hợp lệ

Sau khi xoá membership PM sai ở TOURBOOK (mục 10.1), `pm.phoneshop` (user 21 — chính là tài khoản demo của bạn, `display_name` seed sẵn là "Trần Anh Thư") chỉ còn quản lý 1 project. Theo yêu cầu bổ sung ("tôi muốn PM này có 2 project"), đã tạo **project thứ 2 hợp lệ** thay vì sửa lại data cũ (đúng khuyến nghị ở mục 1 plan v2 — "muốn demo PM quản lý nhiều project thì dùng project mới, không sửa project đã có PM đúng"):

- Project mới `GADGETHUB` ("GadgetHub Marketplace", `project_id=136`), tạo qua đúng service `project_service.create_project` với `created_by_admin_id=19` (admin thật) — mô phỏng đúng hành động Admin sẽ làm khi có UI thật (TV4 chưa build).
- Gán `pm.phoneshop` (user 21) làm PM của `GADGETHUB` qua `project_membership_service.create_membership` — **không** đụng tới project nào đã có PM đúng.
- Thêm 2 Engineer demo (`g.dao@onboarding.dev`, `h.bui@onboarding.dev`) vào `GADGETHUB` để trang "Thành viên" có dữ liệu xem thử.
- Verify lại: `pm.phoneshop` giờ quản lý đúng 2 project (PHONESHOP, GADGETHUB), **cả 4 project trong hệ thống đều đúng 1 PM/project** (query `GROUP BY ... HAVING COUNT(*)=1` xác nhận cả `TOURBOOK/FURNISTORE/GADGETHUB/PHONESHOP`).

### 10.7 Test mới — `tests/test_api/test_onboarding_plans.py`

4 test mới cho 2 route read-only (chưa có API tạo Plan/TemplateVersion vì thuộc Phase 2/4, nên test tự insert thẳng qua ORM để dựng data, có fixture `plan_data` riêng dọn dẹp đúng thứ tự FK — phụ thuộc `test_data` sẵn có để teardown chạy trước theo LIFO):

- `test_get_plan_by_membership_not_found` — membership chưa có Plan → 404.
- `test_get_plan_by_membership_found` — có Plan → 200, đúng field.
- `test_list_plans_by_project_only_returns_members_with_plan` — membership chưa có Plan **không xuất hiện** trong response (FE tự suy luận "chưa có Plan" từ việc thiếu mặt, đúng thiết kế route).
- `test_list_plans_by_project_empty_when_no_plans` — project chưa ai có Plan → trả `[]`.

Test cũ cho `POST /projects/pm` và `POST /project-memberships/pm` (`test_projects.py`, `test_project_memberships.py`) **giữ nguyên, không xoá** — vì test thẳng vào API backend (vẫn còn, chỉ gỡ khỏi FE PM), không phải test hành vi PM UI.

### 10.8 Bằng chứng hoạt động thật

**Test tự động — 20/20 PASS:**
```
tests/test_agents/test_graph.py::test_agent_basic_flow PASSED
tests/test_agents/test_graph.py::test_agent_state_structure PASSED
tests/test_api/test_onboarding_plans.py::test_get_plan_by_membership_not_found PASSED
tests/test_api/test_onboarding_plans.py::test_get_plan_by_membership_found PASSED
tests/test_api/test_onboarding_plans.py::test_list_plans_by_project_only_returns_members_with_plan PASSED
tests/test_api/test_onboarding_plans.py::test_list_plans_by_project_empty_when_no_plans PASSED
tests/test_api/test_project_memberships.py::test_create_membership PASSED
tests/test_api/test_project_memberships.py::test_create_membership_duplicate PASSED
tests/test_api/test_project_memberships.py::test_create_membership_rejects_system_role_user PASSED
tests/test_api/test_project_memberships.py::test_list_memberships_by_project PASSED
tests/test_api/test_project_memberships.py::test_update_membership_role PASSED
tests/test_api/test_project_memberships.py::test_deactivate_membership PASSED
tests/test_api/test_project_memberships.py::test_list_memberships_by_user PASSED
tests/test_api/test_projects.py::test_create_project PASSED
tests/test_api/test_projects.py::test_create_project_duplicate_key PASSED
tests/test_api/test_projects.py::test_list_projects PASSED
tests/test_api/test_projects.py::test_get_project_not_found PASSED
tests/test_api/test_projects.py::test_update_project PASSED
tests/test_api/test_projects.py::test_archive_project PASSED
tests/test_api/test_routes.py::test_health PASSED
============================= 20 passed in 1.53s ==============================
```
Xác nhận sau khi chạy: `SELECT ... WHERE key LIKE 'TEST%'` → 0 project rác, 0 user rác, 0 template rác — fixture `plan_data`/`test_data` dọn sạch đúng thứ tự FK.

**Backend chạy thật trong Docker (rebuild lại `docker compose up -d --build backend` để nhận code mới) — curl thật:**
```
GET /api/v1/users/21
→ {"user_id":21,"email":"pm.phoneshop@onboarding.dev","display_name":"Trần Anh Thư","system_role":null,"status":"ACTIVE",...}
   (đúng data thật sẽ hiện ở sidebar footer — không còn hardcode)

GET /api/v1/project-memberships/pm/by-user/21
→ [{"project_id":4,"project_role":"PM",...}, {"project_id":136,"project_role":"PM",...}]
   (xác nhận PM quản lý đúng 2 project: PHONESHOP + GADGETHUB, không phải TOURBOOK bị chiếm nhầm nữa)

GET /api/v1/onboarding-plans/pm/by-project/4
→ [{"plan_id":4,"membership_id":8,"status":"ACTIVE",...}]
   (đúng 1 Engineer của PHONESHOP đã có Plan sẵn từ data seed gốc — dùng để demo pill "Đang thực hiện")

GET /api/v1/onboarding-plans/pm/by-membership/999999
→ HTTP 404
```

**Frontend:**
- `npx tsc --noEmit` — sạch, 0 lỗi.
- `npx eslint` trên toàn bộ file đã sửa — sạch, 0 lỗi (kể cả sau khi refactor 3 chỗ `useEffect` reset state theo pattern react.dev khuyến nghị — điều chỉnh state ngay trong render thay vì effect, thay vì disable rule).
- `npx prettier --check`/`--write` trên đúng các file đã sửa trong đợt này — sạch.
- `npx next build` (production) — **build thành công**, route `/product-manager` vẫn generate tĩnh.
- `curl http://localhost:3000/product-manager` → **HTTP 200** (dev server đang chạy sẵn).

### 10.9 Ngoài phạm vi v2 (chưa làm, để phase sau)
- Luồng tạo Onboarding Plan thật (chọn TemplateVersion đã duyệt, sinh Plan) — Phase 4, nút "Tạo Onboarding Plan" hiện disabled đúng theo kế hoạch.
- Màn hình "Xem tiến độ" (milestone/checklist chi tiết 1 Plan) — Phase 5, nút hiện disabled đúng theo kế hoạch.
- Server-side search/pagination thật (hiện client-side, đủ dùng cho quy mô demo hiện tại — 1 PM quản lý vài project).
- Trang Admin thật để tạo project/gán PM/thêm Engineer qua UI (hiện đang mô phỏng bằng script trực tiếp vào service — thuộc phạm vi TV4).
