# BO-06 Frontend

Frontend cho **BO-06 — AI Technical Onboarding Buddy**, dùng Next.js,
TypeScript và Tailwind CSS. Ứng dụng đã tích hợp phiên đăng nhập, RBAC, project
membership, Admin/HR workspace, PM workspace và Engineer Portal với FastAPI.

## Kiến trúc frontend

Frontend tổ chức theo **feature**, không copy component theo role:

- Feature là năng lực nghiệp vụ: Chat, Documents, Tasks, Onboarding và User
  Management.
- Role (`user`, `hr`, `admin`, `product-manager`) quyết định dashboard/menu và
  quyền sử dụng feature, không phải nơi nhân bản component.
- Frontend chỉ hiện UI phù hợp; Backend là nguồn quyết định cuối cùng về
  membership, role và Access Scope.

Ví dụ: HR và Product Manager cùng dùng Chat thì đều sử dụng
`features/chat/`, không tạo hai phiên bản Chat khác nhau.

## Routes hiện có

| Route                | Mục đích hiện tại                                                |
| -------------------- | ---------------------------------------------------------------- |
| `/`                  | Trang khởi đầu của BO-06.                                        |
| `/login`             | Đăng nhập và resolve workspace theo session.                     |
| `/chat`              | Project/Policy RAG Chat dùng chung.                              |
| `/documents`         | Route dự phòng cho quản lý tài liệu.                             |
| `/tasks`             | Route dự phòng cho task; checklist chính nằm trong `/user`.      |
| `/onboarding`        | Route dự phòng cho onboarding; flow chính nằm trong role portal. |
| `/user`              | Engineer Portal theo `?project=<project_id>`.                    |
| `/admin`             | Admin workspace.                                                 |
| `/admin/users`       | Quản lý người dùng của Admin.                                    |
| `/admin/projects`    | Quản lý project của Admin.                                       |
| `/admin/memberships` | Quản lý membership của Admin.                                    |
| `/hr`                | HR policy workspace.                                             |
| `/product-manager`   | PM workspace theo `?project=<project_id>`.                       |
| `/select-project`    | Chọn context khi có nhiều membership ACTIVE.                     |

URL frontend chỉ giữ state điều hướng; không suy ra quyền truy cập từ URL hay
tin `project_id` do client gửi. Backend luôn kiểm tra lại session và membership.

## Luồng sau đăng nhập

1. `/login` xác thực rồi gọi `/auth/me` để lấy `system_role` và memberships.
2. `ADMIN` vào `/admin`; `HR` vào `/hr` và không đi qua project selection.
3. User project-scoped không có membership hợp lệ nhận trạng thái không có quyền.
4. Có đúng một membership ACTIVE trên project ACTIVE: frontend gọi
   `POST /api/v1/me/active-membership` để kiểm tra lại rồi vào thẳng portal theo
   `project_role`.
5. Có nhiều membership hợp lệ: mở `/select-project` đúng một lần. Sau khi chọn,
   PM vào `/product-manager?project=<id>`, Engineer vào `/user?project=<id>`.
6. Trong portal, project switcher ở topbar dùng để đổi context; portal không mở
   thêm một màn hình chọn project chặn toàn trang.
7. Engineer báo blocker từ task detail hoặc mục `Blocker của tôi`; PM cùng project
   theo dõi tại mục `Blocker Engineer` và xác nhận `Đã xử lý`. Trạng thái blocker
   được đồng bộ lại để Engineer nhìn thấy kết quả, không tạo thêm một kênh ticket riêng.

## Yêu cầu

- Node.js 22 trở lên.
- npm đi kèm Node.js.
- Git.

## Chạy local

Từ thư mục gốc repository:

```powershell
cd frontend
Copy-Item .env.example .env.local
npm.cmd install
npm.cmd run dev
```

Mở http://localhost:3000 trong trình duyệt. Dừng development server bằng
`Ctrl+C`.

> Trên một số máy Windows, PowerShell có thể chặn `npm.ps1`. Khi đó dùng
> `npm.cmd` như các lệnh trên.

## Biến môi trường

| Biến                       | Bắt buộc | Mục đích                                                                                        |
| -------------------------- | -------: | ----------------------------------------------------------------------------------------------- |
| `API_UPSTREAM_URL`         |    Không | Backend mà rewrite `/api/:path*` chuyển tiếp tới; mặc định `http://127.0.0.1:8000`.              |
| `NEXT_PUBLIC_API_URL`      |    Không | Chỉ đặt khi cần gọi FastAPI trực tiếp, bỏ qua proxy. Để trống thì API đi cùng origin với trang.  |
| `NEXT_PUBLIC_DEMO_USER_ID` |    Không | User context development; seed mặc định dùng ID `9`.                                            |

API luôn được gọi bằng đường dẫn tương đối và Next proxy sang `API_UPSTREAM_URL`. Nhờ vậy
cookie phiên là first-party trên chính domain của frontend — điều kiện bắt buộc để trình
duyệt lưu cookie `SameSite=Lax` và để `middleware.ts` đọc được nó. Trỏ `NEXT_PUBLIC_API_URL`
sang một hostname khác sẽ làm đăng nhập trả 200 mà không có phiên.

`NEXT_PUBLIC_*` được đưa vào JavaScript bundle phía browser. Không đặt API key,
token, credential hoặc bất kỳ secret Backend nào trong `.env.local` của
frontend.

## Cấu trúc source

```text
src/
├── app/                              # Next.js routes
│   ├── chat/page.tsx                  # /chat
│   ├── documents/page.tsx             # /documents
│   ├── tasks/page.tsx                 # /tasks
│   ├── onboarding/page.tsx            # /onboarding
│   ├── select-project/page.tsx         # /select-project
│   ├── user/page.tsx                  # Role dashboard /user
│   ├── hr/page.tsx                    # Role dashboard /hr
│   ├── product-manager/page.tsx       # Role dashboard /product-manager
│   └── admin/
│       ├── page.tsx                   # Role dashboard /admin
│       └── users/page.tsx             # /admin/users
├── components/
│   └── ui/                            # Button, Input, Modal... dùng chung
├── features/
│   ├── chat/                          # UI, hooks và logic Chat dùng chung
│   ├── documents/                     # UI, hooks và logic Documents
│   ├── tasks/                         # UI, hooks và logic Tasks
│   ├── onboarding/                    # UI, hooks và logic Onboarding
│   ├── project-selection/             # UI + hook chọn active project membership
│   └── user-management/               # UI, hooks và logic quản lý người dùng
├── hooks/                             # Hooks dùng chung toàn ứng dụng
├── lib/api.ts                         # API URL và endpoint constants, chưa gọi request
└── types/chat.ts                      # TypeScript types theo Chat API Contract
```

Quy ước đặt code:

- `app/<route>/page.tsx` chỉ chịu trách nhiệm route và ghép component.
- Component, hook và API client riêng cho một feature đặt trong
  `features/<feature>/`.
- Component UI có thể tái sử dụng đặt trong `components/ui/`.
- Hook có tính toàn ứng dụng đặt trong `hooks/`.

## Quality checks

Chạy trước khi mở Pull Request:

```powershell
npm.cmd run lint
npm.cmd run test
npm.cmd run format:check
npm.cmd run build
```

Nếu cần tự format code:

```powershell
npm.cmd run format
```

Quy ước branch, Pull Request và bảo mật nằm tại
[`CONTRIBUTING.md`](CONTRIBUTING.md).

## Tích hợp Backend

Authentication và Project Selection gọi API thật:

- `POST /api/v1/auth/login` tạo session cookie; `GET /api/v1/auth/me` trả identity
  cùng membership để frontend resolve workspace.
- `GET /api/v1/me/memberships?status=ACTIVE` lấy membership/project đang ACTIVE.
- `POST /api/v1/me/active-membership` kiểm tra lại membership và project trước khi điều hướng.
- Engineer dùng `GET /api/v1/member/blockers?project_id={id}` để xem và
  `POST /api/v1/member/plan-tasks/{task_id}/blockers` để báo blocker; PM dùng
  `GET /api/v1/pm/projects/{project_id}/blockers` và
  `PATCH /api/v1/pm/projects/{project_id}/blockers/{blocker_id}/resolve` để theo dõi,
  xác nhận xử lý. Các endpoint đều kiểm tra membership ACTIVE và project role ở backend.
- Development gửi `X-User-Id`; cần thay bằng SSO/OIDC trước production.

Project RAG Chat sẽ gọi `POST /api/v1/chat` theo
`docs/specs/01-chat-api-contract.md`. Khi tích hợp, UI Chat phải hiển thị
citation hoặc fallback do Backend trả về; không được tự bypass ACL hay giữ
secret trong browser.

Engineer Portal, Admin/HR workspace và PM workspace đã dùng API theo từng
feature. Mọi endpoint mới vẫn phải có API contract và authorization phía server.

## Giới hạn hiện tại

- Các route `/documents`, `/tasks` và `/onboarding` ở cấp root chỉ là route dự
  phòng; trải nghiệm nghiệp vụ chính nằm trong role portal tương ứng.
- Một số feature MVP còn tiếp tục hoàn thiện, nhưng không được bypass API/RBAC
  bằng dữ liệu hard-code phía browser.
- Chưa có SSO/OIDC; `X-User-Id` chỉ dùng cho development.
- Frontend có Vitest và Playwright E2E; vẫn phải chạy lint, format check và
  production build trước khi bàn giao.
