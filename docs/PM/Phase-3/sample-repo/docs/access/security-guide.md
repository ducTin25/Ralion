# Quyền truy cập & bảo mật

## 1. Phạm vi tài liệu

Tài liệu này mô tả biến môi trường, phạm vi truy cập dữ liệu, và các lưu ý bảo mật khi phát triển
hoặc vận hành Todo API. Vì đây là dự án demo, một số mục sẽ ghi rõ "không áp dụng ở bản demo, cần
làm trước khi lên production thật" thay vì giả vờ đã có sẵn.

## 2. Biến môi trường (`.env`)

| Biến | Bắt buộc | Ý nghĩa | Giá trị mẫu |
|---|---|---|---|
| `DATABASE_URL` | Không (có default) | Đường dẫn kết nối SQLite | `sqlite:///./todo.db` |
| `APP_ENV` | Không (có default) | Môi trường chạy (`development`/`production`) | `development` |
| `API_SECRET_KEY` | Có, cho môi trường production | Khoá bí mật dự trù cho việc ký token khi thêm authentication sau này | *(không có giá trị mẫu — phải tự sinh, xem mục 4)* |

File `.env.example` trong repo chỉ chứa **giá trị mẫu vô hại**, không phải secret thật — luôn copy
thành `.env` rồi mới điền giá trị thật (nếu có), **không commit file `.env` thật lên git**.

## 3. Phạm vi truy cập dữ liệu hiện tại

Bản demo hiện tại **không có hệ thống đăng nhập/phân quyền** — mọi request tới API đều được coi là
hợp lệ và có toàn quyền đọc/ghi mọi todo. Đây là giới hạn đã biết, phù hợp cho mục đích demo nội bộ
nhưng **không phù hợp để expose ra Internet công khai** ở dạng hiện tại.

Nếu triển khai thật, cần bổ sung tối thiểu:

1. Authentication (ví dụ JWT) để xác định người gọi API.
2. Authorization theo user — mỗi người chỉ thấy/sửa todo của chính mình.
3. Rate limiting để tránh lạm dụng API.
4. HTTPS bắt buộc (không chạy HTTP trần ngoài môi trường local).

## 4. Quản lý secret

- Không hard-code secret trong source code.
- Không commit file `.env` thật lên git (đã có `.env` trong `.gitignore` — kiểm tra kỹ trước khi
  push nếu bạn thêm biến môi trường mới).
- Nếu cần sinh `API_SECRET_KEY` ngẫu nhiên: `python -c "import secrets; print(secrets.token_hex(32))"`.
- Không chia sẻ secret qua chat/email — dùng công cụ quản lý secret riêng (ngoài phạm vi demo này).

## 5. Dependency và lỗ hổng bảo mật

Dự án dùng 3 dependency chính (`fastapi`, `uvicorn`, `sqlalchemy`) — nên định kỳ kiểm tra phiên bản
mới có bản vá bảo mật hay không (ví dụ bằng `pip list --outdated`). Đây là dự án demo nên không có
quy trình audit dependency tự động, nhưng dự án thật nên có bước này trong CI.

## 6. Ghi log

Hiện tại ứng dụng dùng log mặc định của `uvicorn` (ghi ra stdout), không log nội dung todo của
người dùng ra file log dài hạn — tránh vô tình lưu dữ liệu nhạy cảm nếu người dùng đặt tên todo có
chứa thông tin cá nhân.
