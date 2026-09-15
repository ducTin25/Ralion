# Todo API

Todo API là dịch vụ backend quản lý danh sách công việc (todo) cho một nhóm nhỏ người dùng nội bộ.
Dự án được viết bằng **Python 3.11**, framework **FastAPI**, ORM **SQLAlchemy**, lưu trữ trên
**SQLite** để đơn giản hoá việc chạy demo (không cần cài đặt database server riêng).

> Đây là project demo dùng để kiểm thử tính năng "PM nhập tài liệu dự án" (UC-04) của hệ thống
> Project Onboarding Buddy — Phase 3, đóng vai trò một repository thật để bộ quét (scanner) đọc,
> phân loại tài liệu và tạo Coverage Report. Code trong repo này **chạy được thật** (không phải
> file rỗng), tài liệu cố tình viết dài/chi tiết như 1 dự án thật. Giữ tối giản, chỉ có đúng 2 case
> biên cố tình cài vào — mỗi case test đúng 1 tầng của cơ chế phân loại, không thêm file nhiễu
> ngoài mục đích rõ ràng: `notes-final.md` (tên sai convention nhưng nội dung khớp SETUP — test
> tầng phân loại theo NỘI DUNG) và `docs/adr/0001-single-service.md` (path/tên/nội dung đều không
> có từ khoá nào khớp — test tầng cuối cùng, phải gọi AI mới phân loại đúng ARCHITECTURE được).

## Mục tiêu sản phẩm

Todo API phục vụ 3 nhóm nhu cầu chính:

1. **Quản lý công việc cá nhân** — người dùng tạo, xem, sửa, xoá các todo item của mình, mỗi item
   có tiêu đề, mô tả (tuỳ chọn), trạng thái hoàn thành (`is_done`), độ ưu tiên (`priority`), thời
   gian tạo và thời gian cập nhật gần nhất.
2. **Lọc và tìm kiếm** — cho phép lọc danh sách theo trạng thái hoàn thành và theo độ ưu tiên, để
   người dùng dễ dàng xem "việc còn phải làm" thay vì toàn bộ lịch sử.
3. **Tích hợp đơn giản** — API trả JSON thuần, không yêu cầu SDK riêng, để các công cụ khác (script
   nội bộ, bot nhắc việc...) có thể gọi trực tiếp qua HTTP.

Phạm vi **không** bao gồm (cố tình bỏ ngoài MVP để giữ demo gọn):

- Không có xác thực/đăng nhập (mọi request được coi là hợp lệ).
- Không có phân quyền nhiều người dùng (chỉ 1 danh sách todo dùng chung).
- Không có thông báo/nhắc việc qua email hay push notification.
- Không có đính kèm file cho từng todo.

## Cấu trúc thư mục

```
sample-repo/
├── app/                      # Source code chính của ứng dụng
│   ├── __init__.py
│   ├── main.py                # Khởi tạo FastAPI app, đăng ký router, cấu hình CORS
│   ├── database.py             # Engine + Session SQLAlchemy, khởi tạo bảng
│   ├── models.py                # Model ORM Todo (bảng "todos")
│   ├── schemas.py                 # Pydantic schema cho request/response
│   └── routes.py                    # Router /todos: CRUD + filter
├── tests/                    # Test tự động (pytest)
│   └── test_todos.py
├── docs/                     # Tài liệu dự án — đây là phần scanner Phase 3 sẽ quét
│   ├── architecture/system-design.md
│   ├── adr/0001-single-service.md   # Không path/tên/nội dung nào khớp rule -> bắt buộc gọi AI
│   ├── setup/local-setup.md
│   ├── access/security-guide.md
│   └── codebase-guide.md
├── requirements.txt
├── .env.example               # Mẫu biến môi trường (KHÔNG chứa secret thật) — test scanner NHẬN
├── .env                          # Secret giả — test scanner LOẠI TRỪ file này
├── notes-final.md              # Nội dung khớp Setup nhưng đặt tên sai convention — test phân loại
│                                 theo NỘI DUNG thay vì theo tên file
├── node_modules/fake-pkg/     # Thư mục dependency giả — test scanner LOẠI TRỪ theo path
├── assets/demo-diagram.png   # File ảnh — test loại theo đuôi file không phải tài liệu
├── app.log                      # File log — test loại theo đuôi file không phải tài liệu
└── README.md
```

## Bắt đầu nhanh

Xem hướng dẫn cài đặt chi tiết từng bước ở [docs/setup/local-setup.md](docs/setup/local-setup.md).
Tóm tắt siêu ngắn cho người đã quen FastAPI:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Sau đó mở `http://127.0.0.1:8000/docs` để xem Swagger UI và thử gọi API trực tiếp trên trình duyệt.

## API tóm tắt

| Method | Endpoint      | Mô tả                                              |
|--------|---------------|-----------------------------------------------------|
| GET    | `/todos`      | Danh sách todo, hỗ trợ filter `is_done`/`priority`   |
| POST   | `/todos`      | Tạo todo mới                                          |
| GET    | `/todos/{id}` | Xem chi tiết 1 todo                                    |
| PATCH  | `/todos/{id}` | Cập nhật 1 todo (title/is_done/priority)                |
| DELETE | `/todos/{id}` | Xoá 1 todo                                                |

## Tài liệu liên quan

- [Kiến trúc hệ thống](docs/architecture/system-design.md) — thành phần, luồng xử lý, quyết định thiết kế.
- [Cài đặt môi trường](docs/setup/local-setup.md) — hướng dẫn cài đặt và chạy local từng bước.
- [Quyền truy cập & bảo mật](docs/access/security-guide.md) — biến môi trường, phạm vi truy cập, lưu ý bảo mật.
- [Hướng dẫn mã nguồn](docs/codebase-guide.md) — giải thích từng file, quy ước code, điểm bắt đầu đọc code.

## Đóng góp

Dự án demo này không nhận pull request từ bên ngoài — mọi thay đổi phục vụ mục đích test nội bộ
của Phase 3 (Project Onboarding Buddy).
