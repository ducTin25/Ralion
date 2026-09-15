# Plan v2 — Sửa phạm vi Phase 1 theo phản hồi

> Trạng thái: **ĐÃ CODE XONG**. Xem báo cáo đầy đủ (bằng chứng test/curl/build) tại [report-phase1.md](report-phase1.md) mục 10.

## 0. Tóm tắt hiểu ý bạn (để bạn kiểm tra tôi hiểu đúng chưa)

1. **Layout đang trống quá** — khoảng cách 2 bên content quá rộng, cần thu hẹp lại.
2. **Trạng thái trên mỗi dòng bảng chưa được giải thích** — cần chú thích rõ nghĩa từng pill (ACTIVE/INACTIVE/ARCHIVED/sync_status...).
3. **KPI card thiếu icon** — 4 thẻ số liệu (Tổng project, Đang hoạt động...) đang chỉ có chữ, cần icon từ thư viện icon đã có.
4. **Phát hiện bug data thật**: 1 project chỉ nên có **đúng 1 PM**, nhiều Engineer — nhưng DB hiện có TOURBOOK bị **2 PM** cùng lúc (lỗi do tôi tự thêm demo data sai trước đó, đã xác nhận qua query — xem mục 1).
5. **Sai phạm vi quyền hạn nghiêm trọng nhất**: **PM không được tạo project** — chỉ **Admin** mới tạo project và gán PM vào. Phải **xoá bỏ** chức năng "Tạo project" khỏi giao diện PM (tôi đã lỡ code, cần gỡ).
6. **"Thêm thành viên" cũng sai phạm vi** — thành viên (cả PM lẫn Engineer) do **Admin** thêm vào project, không phải PM. PM **không tự thêm được ai** vào project. Phải bỏ nút "Thêm thành viên" và toàn bộ modal đó.
7. **Trang "Thành viên" cần đổi mục đích hoàn toàn**: không phải để PM *thêm* người, mà để PM **theo dõi trạng thái Onboarding Plan** của từng Engineer đã có sẵn trong project (do Admin thêm vào từ trước):
   - Mỗi dòng Engineer: có Plan hay chưa.
   - Có bộ lọc theo trạng thái (có Plan / chưa có Plan / theo status Plan).
   - Nếu **chưa có Plan** → action cuối dòng: **"Tạo Onboarding Plan"** (chọn 1 TemplateVersion do PM tạo ở Phase 2 để sinh Plan — đây chính là luồng Phase 4).
   - Nếu **đã có Plan** → action: **"Xem tiến độ"** (milestone/checklist — đây chính là Phase 5).
8. **Cần search + filter** trên các trang danh sách (Dự án, Thành viên), không chỉ bảng trơn.
9. **Icon thư viện dùng nhất quán** — search icon, filter icon... không chỉ text.
10. Modal (nếu còn giữ modal nào) cần header/footer thiết kế đẹp hơn.

---

## 1. Bug data đã xác nhận (query thật)

```sql
SELECT p.key, u.email, m.project_role, m.status FROM project_memberships m
JOIN projects p ON p.project_id=m.project_id JOIN users u ON u.user_id=m.user_id
WHERE m.project_role='PM' ORDER BY p.key;
```
```
FURNISTORE  | pm.furnistore@onboarding.dev | PM | ACTIVE
PHONESHOP   | pm.phoneshop@onboarding.dev  | PM | ACTIVE
TOURBOOK    | pm.phoneshop@onboarding.dev  | PM | ACTIVE   <- lỗi, thêm nhầm
TOURBOOK    | pm.tourbook@onboarding.dev   | PM | ACTIVE   <- PM gốc đúng
```
**Nguồn gốc lỗi**: lúc đầu Phase 1 tôi tự thêm `pm.phoneshop` làm PM thứ 2 của TOURBOOK để demo "1 PM quản lý nhiều project" (đúng ý minh hoạ), nhưng quên rằng làm vậy khiến TOURBOOK có 2 PM cùng lúc (sai luật "1 project = 1 PM"). Đây là 2 khái niệm khác nhau: *1 PM có thể phụ trách nhiều project* (đúng) ≠ *1 project có thể có nhiều PM* (sai).

**Fix đề xuất**: xoá (hard-delete, vì đây là data demo tự thêm sai, không phải action nghiệp vụ thật) membership `pm.phoneshop` trên TOURBOOK. Giữ nguyên PM gốc đúng của từng project. Nếu vẫn muốn demo "PM quản lý nhiều project", dùng project khác (project mới do Admin tạo sau) thay vì sửa data đã seed sẵn.

---

## 2. Phân định lại quyền hạn (quan trọng nhất, ảnh hưởng toàn bộ Phase 1)

| Hành động | Ai làm | Trạng thái hiện tại (SAI) | Sửa lại |
|---|---|---|---|
| Tạo `Project` | **Admin** (TV4) | PM tạo được (nút "Tạo project") | **Xoá khỏi giao diện PM** |
| Gán PM đầu tiên vào project | **Admin** | — (chưa làm) | Thuộc phạm vi TV4, không phải PM |
| Thêm Engineer vào project | **Admin** | PM thêm được (modal "Thêm thành viên") | **Xoá khỏi giao diện PM** |
| Xem danh sách Engineer trong project mình quản lý | **PM** | Đang trộn chung với "thêm/xoá" | Giữ lại, chỉ **xem** |
| Tạo Onboarding Plan cho 1 Engineer | **PM** | Chưa có | **Thêm mới** (thay thế hoàn toàn cho "Thêm thành viên") |
| Theo dõi tiến độ Onboarding Plan | **PM** | Chưa có | **Thêm mới** (Phase 5, để nút placeholder ở Phase 1 v2 này) |
| Khoá/kích hoạt lại membership | Admin (không phải PM) | PM làm được (nút "Khoá"/"Kích hoạt lại") | **Cân nhắc bỏ luôn** — đây cũng là hành động quản lý người, không phải quản lý onboarding. Xem mục 4.3 |

→ Xác nhận lại đúng ý bạn: **API backend `POST /projects/pm`, `POST /project-memberships/pm`, `PATCH /project-memberships/pm/{id}`, `DELETE /project-memberships/pm/{id}` vẫn giữ nguyên trong code** (không xoá endpoint — vẫn có ích cho Admin/TV4 tái dùng sau, hoặc dùng để seed/test), **chỉ gỡ bỏ khỏi giao diện + luồng thao tác của PM** (không gọi các API này từ trang PM nữa, trừ GET để xem danh sách). Nếu bạn muốn xoá thẳng cả API/hàm backend luôn (không chỉ ẩn ở FE), báo lại — tôi hiểu câu "nếu lỡ viết hàm xóa đi" theo nghĩa xoá ở tầng PM UI trước, giữ backend vì API CRUD Project/Membership là hạ tầng chung, hợp lý để Admin dùng lại chứ không phải code chỉ riêng PM sài rồi bỏ.

---

## 3. Thiết kế lại trang "Thành viên" (đổi tên gợi ý: **"Onboarding theo thành viên"**)

### 3.1 Nội dung
- Danh sách **chỉ Engineer** (role=ENGINEER) của project đang chọn — lấy từ `GET /project-memberships/pm?project_id=` (đã có sẵn), lọc `project_role=ENGINEER` phía client hoặc thêm query param phía BE.
- Mỗi dòng: avatar + tên + email (giữ nguyên) + cột mới **"Onboarding Plan"**:
  - Chưa có plan → pill `neutral` "Chưa có Plan" + action **"Tạo Onboarding Plan"**.
  - Đã có plan → pill theo status thật (`DRAFT`/`APPROVED`/`ACTIVE`/`PROJECT_READY`/`ONBOARDING_CLOSED`, đúng màu semantic đã định nghĩa) + action **"Xem tiến độ"**.
- **Bỏ hẳn**: nút "Thêm thành viên", nút "Khoá"/"Kích hoạt lại" (đây là việc Admin làm, không phải PM — xem mục 4.3 nếu bạn muốn giữ lại phần này).
- **Bỏ hẳn**: cột "Trạng thái" (ACTIVE/INACTIVE của membership) — vì PM không quản lý việc này nữa. Có thể vẫn hiện nhỏ dạng tag phụ nếu bạn muốn biết Engineer đó còn active trong project hay không (chỉ xem, không thao tác).

### 3.2 Backend cần thêm (nhỏ, không phải build hết Phase 4)
Chỉ cần 1 endpoint **read-only** kiểm tra plan đã tồn tại chưa cho mỗi membership — **không** build luồng sinh Candidate Plan thật (đó vẫn là Phase 4 đầy đủ):
```
GET /onboarding-plans/pm/by-membership/{membership_id}
→ 200 + OnboardingPlanResponseDTO (nếu đã có)
→ 404 (nếu chưa có) → FE hiện "Chưa có Plan"
```
Cần tạo model migration? **Không** — `OnboardingPlan` đã có sẵn trong `src/model/onboarding_plan.py`, chỉ cần viết DTO + service + router tối thiểu (get theo membership_id), không cần route tạo plan thật (nút "Tạo Onboarding Plan" ở Phase 1 v2 này **disabled + tag "Sắp có"**, kích hoạt thật khi làm Phase 4 đầy đủ — đúng nguyên tắc "không nút chết" vì có tag rõ ràng, không giả vờ hoạt động).

### 3.3 Action "Xem tiến độ" (member đã có Plan)
Ở Phase 1 v2 này: **disabled + tag "Sắp có"** (Phase 5 mới build màn hình milestone thật). Chỉ hiện đúng trạng thái Plan hiện tại qua pill, chưa cần trang chi tiết.

---

## 4. Trang "Dự án" — sửa theo phản hồi

### 4.1 Bỏ nút + modal "Tạo project"
Xoá `CreateProjectForm.tsx`, nút "+ Tạo project" khỏi `ProjectListView.tsx`. Trang này chỉ còn: xem danh sách project PM đang phụ trách (read-only), không có hành động tạo mới.

### 4.2 Thêm search/filter
Ô tìm kiếm theo `key`/`name` phía trên bảng (lọc client-side, danh sách project của 1 PM thường không nhiều nên chưa cần server-side search).

### 4.3 Câu hỏi cần bạn xác nhận
Trang "Dự án" sau khi bỏ "Tạo project" thì gần như chỉ còn là **danh sách + click chọn** (không còn hành động nào khác) — có cần giữ nút "Khoá"/xem chi tiết project nào không, hay đúng là **chỉ xem + chọn** thôi?

---

## 5. UI polish (áp dụng cho cả 2 trang)

| Vấn đề | Cách sửa |
|---|---|
| Khoảng cách 2 bên quá rộng | `.content` padding giảm từ `--pm-sp-6` (24px) → `--pm-sp-5` (20px) trái phải; `.contentInner` bỏ `max-width:1100px` cố định, đổi thành `max-width: 1400px` hoặc full width trừ padding — cần xem màn hình thật của bạn để canh đúng, sẽ chỉnh rồi cho bạn xem lại. |
| KPI card không icon | Thêm icon (badge tròn nhỏ màu accent, giống `.bannerIcon`) bên trái mỗi KPI — vd icon `users` cho "Tổng thành viên", `check2` cho "Đang hoạt động". |
| Trạng thái không giải thích | Thêm dòng chú thích nhỏ dưới mỗi bảng (vd: "ACTIVE = đang hoạt động trong project · INACTIVE = đã bị khoá") hoặc tooltip khi hover vào pill. |
| Thiếu search/filter | Thêm thanh search (icon `search` có sẵn trong sprite) + dropdown filter trạng thái ở đầu mỗi bảng. |
| Modal header/footer chưa đẹp | Với modal còn giữ lại (nếu có, xem mục 3.2/4.3), thiết kế lại header có icon + footer căn phải chuẩn hơn — chi tiết làm khi biết chắc còn giữ modal nào. |

---

## 6. Việc sẽ làm (theo đúng thứ tự, sau khi bạn duyệt plan này)

1. Fix bug data: xoá membership PM sai của `pm.phoneshop` trên TOURBOOK.
2. Backend: xoá lời gọi "Tạo project" khỏi PM flow (giữ API), thêm route read-only `GET /onboarding-plans/pm/by-membership/{id}` (DTO + service + router tối thiểu).
3. Frontend `ProjectListView`: bỏ nút/modal tạo project, thêm search, giảm khoảng cách layout, thêm icon KPI.
4. Frontend `MembersView` → đổi hẳn logic: chỉ hiện Engineer, thêm cột/pill trạng thái Plan, bỏ nút thêm/khoá thành viên, thêm action "Tạo Onboarding Plan" (disabled+"Sắp có") và "Xem tiến độ" (disabled+"Sắp có"), thêm search/filter.
5. Xoá các file không còn dùng: `AddMemberForm.tsx` (+scss), `CreateProjectForm.tsx` (+scss), `ProjectSwitcher` giữ lại (vẫn cần chọn project xem).
6. Viết test lại cho đúng luồng mới (test cũ cho "tạo project qua PM" cần xoá/sửa).
7. Chạy pytest + tsc + lint + build + docker rebuild, chụp lại bằng chứng, cập nhật báo cáo Phase 1 (viết lại rõ lý do đổi phạm vi, không chỉ thêm mục nối đuôi như mấy lần trước).

## 7. Điều tôi CHƯA chắc, cần bạn xác nhận trước khi code

**Đã chốt theo mặc định đề xuất (bạn nói "tiến hành code đi" sau khi xem plan này, không phản hồi riêng từng câu):**
1. Xoá hẳn API backend tạo project/thêm-membership luôn, hay chỉ gỡ khỏi giao diện PM? → **Giữ API, chỉ gỡ FE** (xem mục 2) — đã code đúng vậy, backend CRUD Project/ProjectMembership không đổi.
2. Trang "Dự án" chỉ còn xem, có cần hành động nào khác? → **Chỉ xem + chọn**, không thêm hành động nào khác (mục 4.3) — đã code đúng vậy.
3. Cột "Trạng thái" (ACTIVE/INACTIVE của membership) ở trang Thành viên — bỏ hẳn hay giữ dạng chỉ xem? → **Bỏ cột riêng, giữ 1 tag nhỏ "Đã khoá" cạnh tên khi membership không ACTIVE** (không có nút thao tác) — theo đúng gợi ý mở ở mục 3.1.

---

## 8. Thiết kế lại Sidebar + Header (topbar)

Theo ảnh bạn gửi: sidebar còn trống 1 khoảng lớn giữa menu và footer; topbar chỉ có chữ "Dự án" + nút dark mode, quá sơ sài; **footer sidebar đang hardcode cứng chữ "PM PhoneShop API"** — sai vì không phản ánh đúng `CURRENT_PM_USER_ID` thật (nếu đổi hằng số này sang PM khác, footer vẫn hiện sai tên cũ).

### 8.1 Sidebar footer — lấy đúng data thật thay vì hardcode
```
Hiện tại (SAI):                          Sửa lại (ĐÚNG):
┌─────────────────────┐                  ┌─────────────────────┐
│ [PM] PM PhoneShop API│  <- text cứng    │ [PA] PM PhoneShop API│  <- PmAvatar (initials
│      PM — Project Mgr│                  │      PM — Project Mgr│     màu theo email thật)
└─────────────────────┘                  └─────────────────────┘
```
Gọi `GET /api/v1/users/{CURRENT_PM_USER_ID}` 1 lần khi load `PmShell`, hiện `display_name` thật + dùng `PmAvatar` (đã có sẵn component) thay vì ô vuông "PM" chữ cứng. Trong lúc đang tải: hiện skeleton/placeholder mờ, không hiện tên sai.

### 8.2 Khoảng trống giữa menu và footer
Đây là hành vi bình thường của layout sidebar cố định chiều cao (footer luôn dính đáy qua `margin-top:auto`) — không phải lỗi, nhưng để đỡ trống trải, đề xuất thêm 1 khối nhỏ phía trên footer: **"Dự án đang xem"** (rút gọn từ project switcher, hiện luôn project đang chọn ngay trong sidebar thay vì chỉ ở topbar) — vừa lấp khoảng trống vừa hữu ích, không phải trang trí vô nghĩa.

### 8.3 Header (topbar) — thêm nội dung thật, bớt sơ sài
```
┌──────────────────────────────────────────────────────────────────────┐
│ [icon] Dự án      [🔍 Tìm dự án, thành viên...]      [🔔] [🌙]        │
└──────────────────────────────────────────────────────────────────────┘
```
- Breadcrumb có icon nhỏ đi kèm (khớp trang đang xem) thay vì chữ trơn.
- Thêm ô search thật (icon `search` có sẵn) — với "Dự án" thì search theo key/name; với "Thành viên" thì search theo tên/email (nối vào phần search/filter đã đề cập ở mục 5).
- Thêm icon chuông thông báo — **disabled + tooltip "Sắp có"** (chưa có hệ thống notification, không giả vờ hoạt động).
- Tăng chiều cao topbar 54px → 58px, thêm `box-shadow` nhẹ phía dưới để tách biệt rõ khỏi content khi cuộn.

---

## 9. Footer bảng + phân trang

Cả 2 bảng (Dự án, Thành viên) hiện chưa có phân trang — API backend đã có sẵn `limit`/`offset` (`GET /projects/pm?limit=&offset=`, `GET /project-memberships/pm?limit=&offset=`) nhưng FE đang gọi cố định `limit=200`/mặc định 50, không có UI điều hướng trang.

### Thiết kế footer bảng
```
┌────────────────────────────────────────────────────────────┐
│  (nội dung bảng...)                                          │
├────────────────────────────────────────────────────────────┤
│  Hiển thị 1–10 trong 24 kết quả          [‹ Trước] [Sau ›]   │
└────────────────────────────────────────────────────────────┘
```
- Component dùng chung `PmTableFooter` (mới, đặt trong `components/ui/`) — nhận `total`, `page`, `pageSize`, `onPageChange`.
- Page size cố định 10/trang cho Phase 1 (không cần chọn số dòng/trang, giữ đơn giản).
- Áp dụng cho cả bảng Dự án và bảng Thành viên (Engineer) trong redesign ở mục 3.
- Nút "‹ Trước"/"Sau ›" disabled đúng lúc ở đầu/cuối danh sách, không phải lúc nào cũng bấm được.
