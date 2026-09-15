# Cài đặt môi trường local

Hướng dẫn này giúp bạn chạy được Todo API trên máy cá nhân trong khoảng 5 phút, kể cả khi bạn chưa
từng chạy dự án FastAPI nào trước đây.

## 1. Yêu cầu hệ thống

- **Python 3.11 trở lên** — kiểm tra bằng `python --version` (hoặc `python3 --version` trên
  macOS/Linux). Nếu chưa có, tải tại https://www.python.org/downloads/.
- **pip** — đi kèm sẵn với Python, kiểm tra bằng `pip --version`.
- Không cần cài PostgreSQL/MySQL gì cả — dự án dùng SQLite, tự tạo file database khi chạy lần đầu.

## 2. Clone và tạo virtualenv

```bash
git clone <repository-url> todo-api
cd todo-api
python -m venv .venv
```

Kích hoạt virtualenv:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (cmd)
.venv\Scripts\activate.bat
```

Sau khi kích hoạt, prompt terminal sẽ hiện tiền tố `(.venv)` — đây là dấu hiệu bạn đang dùng đúng
môi trường ảo, không cài nhầm package vào Python hệ thống.

## 3. Cài dependency

```bash
pip install -r requirements.txt
```

File `requirements.txt` gồm 3 package chính: `fastapi`, `uvicorn[standard]`, `sqlalchemy`. Nếu cài
lỗi, kiểm tra lại đã activate đúng virtualenv chưa (bước 2).

## 4. Cấu hình biến môi trường

```bash
cp .env.example .env
```

Mở file `.env` vừa tạo, các biến mặc định đã đủ để chạy local, không cần sửa gì thêm trừ khi bạn
muốn đổi tên file database hoặc port. Xem chi tiết ý nghĩa từng biến ở
[docs/access/security-guide.md](../access/security-guide.md).

## 5. Chạy server

```bash
uvicorn app.main:app --reload
```

- `--reload` giúp server tự khởi động lại mỗi khi bạn sửa code — chỉ nên dùng khi phát triển local,
  không dùng khi deploy thật.
- Mặc định server chạy ở `http://127.0.0.1:8000`.
- Lần chạy đầu tiên, `app/database.py` sẽ tự tạo file `todo.db` (SQLite) cùng bảng `todos` — không
  cần chạy migration thủ công.

## 6. Thử gọi API

Mở `http://127.0.0.1:8000/docs` để xem Swagger UI — giao diện web cho phép thử từng endpoint trực
tiếp trên trình duyệt, không cần cài Postman.

Hoặc dùng `curl`:

```bash
curl -X POST http://127.0.0.1:8000/todos \
  -H "Content-Type: application/json" \
  -d '{"title": "Viết báo cáo", "priority": "high"}'

curl http://127.0.0.1:8000/todos
```

## 7. Chạy test

```bash
pytest tests/
```

Test dùng database SQLite riêng trong bộ nhớ (`sqlite:///:memory:`), không đụng tới file `todo.db`
bạn đang dùng khi chạy server thủ công — chạy test xong không cần dọn dẹp gì.

## 8. Sự cố thường gặp

| Triệu chứng | Nguyên nhân khả dĩ | Cách khắc phục |
|---|---|---|
| `ModuleNotFoundError: No module named 'fastapi'` | Chưa activate virtualenv hoặc chưa `pip install` | Lặp lại bước 2 và 3 |
| `Address already in use` khi chạy `uvicorn` | Port 8000 đang bị chương trình khác dùng | Chạy `uvicorn app.main:app --port 8001` |
| `sqlite3.OperationalError: unable to open database file` | Thư mục chạy lệnh không có quyền ghi | Chạy lệnh từ đúng thư mục gốc dự án, kiểm tra quyền ghi |
| Test fail do "database is locked" | Đang chạy server song song với test dùng chung file `todo.db` | Dừng server trước khi chạy `pytest`, hoặc kiểm tra `tests/` có đang dùng in-memory DB đúng cách không |
