# Kiến trúc hệ thống Todo API

## 1. Tổng quan

Todo API theo kiến trúc phân lớp đơn giản (layered architecture), phù hợp cho một dịch vụ quy mô
nhỏ, không cần scale ngang, không có microservice, không có message queue. Mục tiêu thiết kế là
**dễ đọc, dễ chạy, dễ mở rộng từng bước** — không tối ưu sớm cho những nhu cầu chưa xuất hiện.

```
        ┌────────────┐      ┌────────────┐      ┌────────────┐      ┌───────────┐
Client ─▶  routes.py  ─▶   schemas.py   ─▶   models.py    ─▶   database.py  ─▶  SQLite
        │  (HTTP)    │      │ (validate) │      │  (ORM)     │      │ (session)  │
        └────────────┘      └────────────┘      └────────────┘      └───────────┘
```

## 2. Thành phần

### 2.1. `app/main.py` — Application entrypoint
Khởi tạo instance `FastAPI()`, cấu hình CORS (cho phép gọi từ frontend demo nếu có), gọi
`init_db()` để tạo bảng nếu chưa tồn tại, và `include_router(todos_router)` để đăng ký toàn bộ
endpoint `/todos`. Đây là file đầu tiên nên đọc khi mới vào dự án — nó cho biết ứng dụng "khởi
động" như thế nào trước khi đi sâu vào từng route.

### 2.2. `app/database.py` — Kết nối dữ liệu
Tạo `engine` SQLAlchemy trỏ tới file SQLite cục bộ (`todo.db`), định nghĩa `SessionLocal` (factory
tạo session cho mỗi request) và hàm dependency `get_db()` dùng trong FastAPI `Depends()`. Cũng chứa
`Base` (declarative base) mà `models.py` kế thừa.

### 2.3. `app/models.py` — Mô hình dữ liệu
Định nghĩa class `Todo(Base)` ánh xạ tới bảng `todos`, gồm các cột: `id` (khoá chính, tự tăng),
`title` (bắt buộc), `description` (tuỳ chọn), `is_done` (boolean, mặc định `False`), `priority`
(chuỗi giới hạn `"low"/"medium"/"high"`, mặc định `"medium"`), `created_at` và `updated_at`
(timestamp tự động).

### 2.4. `app/schemas.py` — Hợp đồng API (contract)
Các Pydantic model dùng để validate input và định hình output:
- `TodoCreate` — dữ liệu bắt buộc khi tạo mới (`title`, `description?`, `priority?`).
- `TodoUpdate` — mọi field đều tuỳ chọn (dùng cho `PATCH`, chỉ cập nhật field được gửi lên).
- `TodoRead` — hình dạng dữ liệu trả về cho client, bao gồm cả `id`, `created_at`, `updated_at`.

Việc tách riêng schema "vào" (Create/Update) và "ra" (Read) là quy ước quan trọng của dự án — xem
thêm ở [Hướng dẫn mã nguồn](../codebase-guide.md).

### 2.5. `app/routes.py` — Tầng HTTP
Định nghĩa `APIRouter` với 5 endpoint (`GET/POST /todos`, `GET/PATCH/DELETE /todos/{id}`), mỗi
endpoint nhận `db: Session = Depends(get_db)` để thao tác dữ liệu, raise `HTTPException(404)` khi
không tìm thấy todo theo id.

## 3. Luồng xử lý 1 request điển hình (tạo todo mới)

1. Client gửi `POST /todos` kèm JSON body `{"title": "Viết báo cáo", "priority": "high"}`.
2. FastAPI parse body theo schema `TodoCreate` — nếu thiếu `title` hoặc `priority` không nằm trong
   3 giá trị hợp lệ, trả lỗi `422 Unprocessable Entity` ngay, không chạm tới database.
3. Route handler tạo instance `Todo(**payload.model_dump())`, `db.add()`, `db.commit()`,
   `db.refresh()` để lấy lại `id`/`created_at` do database sinh ra.
4. Trả về JSON theo schema `TodoRead` — FastAPI tự serialize nhờ `response_model=TodoRead`.

## 4. Quyết định thiết kế và lý do

| Quyết định | Lý do |
|---|---|
| Dùng SQLite thay vì PostgreSQL | Đây là demo, không cần concurrent write nhiều, ưu tiên "chạy được ngay" không cần cài server riêng. |
| Không có authentication | Ngoài phạm vi demo — mục tiêu là minh hoạ luồng CRUD, không phải hệ thống production thật. |
| Không có background job/queue | Mọi xử lý đồng bộ trong request — khối lượng dữ liệu nhỏ, không cần xử lý nền. |
| Tách schema Create/Update/Read riêng | Tránh lộ field nội bộ ra response, tránh cho phép client ghi đè `id`/`created_at`. |
| 1 file `routes.py` duy nhất | Ứng dụng chỉ có 1 resource (`Todo`) — chưa cần chia nhiều router theo domain. |

## 5. Hướng mở rộng (không nằm trong phạm vi hiện tại)

- Thêm bảng `users` + JWT authentication nếu cần nhiều người dùng.
- Đổi SQLite sang PostgreSQL nếu cần concurrent write hoặc deploy nhiều instance.
- Thêm `tags`/`due_date` cho mỗi todo nếu nghiệp vụ yêu cầu.

Những hướng trên **chưa được lên kế hoạch chính thức** — chỉ liệt kê ở đây để người đọc hiểu giới
hạn hiện tại của kiến trúc, không phải cam kết roadmap.
