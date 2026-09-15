# Hướng dẫn mã nguồn

## 1. Nên đọc code theo thứ tự nào?

Với người mới join dự án, thứ tự đọc đề xuất:

1. `app/main.py` — biết ứng dụng khởi động ra sao, có những router nào.
2. `app/models.py` — biết dữ liệu cốt lõi (`Todo`) có những field gì.
3. `app/schemas.py` — biết "hợp đồng" API: client được gửi gì lên, nhận gì về.
4. `app/routes.py` — biết logic xử lý từng endpoint.
5. `app/database.py` — biết session/connection được quản lý thế nào (thường không cần sửa file này).
6. `tests/test_todos.py` — xem ví dụ thực tế cách gọi từng endpoint, kỳ vọng kết quả gì.

## 2. Điểm bắt đầu (entry point)

`app/main.py` là điểm khởi động — chạy `uvicorn app.main:app` nghĩa là uvicorn import biến `app`
trong file này (instance `FastAPI()`) rồi phục vụ nó qua HTTP.

## 3. Quy ước code

- **Đặt tên**: dùng `snake_case` cho biến/hàm, `PascalCase` cho class (`Todo`, `TodoCreate`...),
  đúng chuẩn PEP 8.
- **Kiểu dữ liệu**: mọi hàm public đều có type hint đầy đủ (tham số + giá trị trả về).
- **Schema vào/ra tách riêng**: không bao giờ dùng thẳng model ORM (`Todo`) làm response — luôn đi
  qua `TodoRead` để kiểm soát chính xác field nào được trả ra ngoài.
- **Không business logic trong route handler dài dòng**: nếu logic phức tạp hơn vài dòng, tách
  thành hàm riêng (dự án hiện tại đủ đơn giản nên chưa cần, nhưng đây là quy ước cho tương lai).
- **Mọi thay đổi field trong `models.py` phải có test tương ứng** trong `tests/test_todos.py`.

## 4. Giải thích từng file

### `app/models.py`
```python
class Todo(Base):
    __tablename__ = "todos"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    is_done = Column(Boolean, default=False, nullable=False)
    priority = Column(String, default="medium", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
```
Đây là "nguồn sự thật" duy nhất về cấu trúc bảng `todos`. Muốn thêm field mới, sửa ở đây trước,
sau đó cập nhật `schemas.py` để field đó xuất hiện đúng chỗ (input/output/cả hai).

### `app/routes.py`
Mỗi hàm trong file này ứng với đúng 1 endpoint, đặt tên hàm mô tả rõ hành động
(`create_todo`, `list_todos`, `get_todo`, `update_todo`, `delete_todo`) — không dùng tên chung
chung như `handler1`.

## 5. Câu hỏi thường gặp khi mới đọc code

**Vì sao có cả `TodoCreate` và `TodoUpdate` mà không dùng chung 1 schema?**
`TodoCreate` bắt buộc `title`; `TodoUpdate` mọi field đều tuỳ chọn (dùng cho `PATCH` — chỉ gửi
field muốn đổi). Gộp chung sẽ làm `title` vô tình trở thành tuỳ chọn khi tạo mới, dễ gây bug.

**Vì sao `routes.py` không tự tạo session mà phải qua `Depends(get_db)`?**
Đây là cách FastAPI khuyến nghị để quản lý vòng đời session theo từng request (mở khi có request,
đóng khi request kết thúc, kể cả khi có lỗi) — không cần tự viết try/finally thủ công ở mỗi hàm.

**Muốn thêm 1 field mới cho Todo thì sửa những đâu?**
1. `app/models.py` — thêm cột.
2. `app/schemas.py` — thêm field vào `TodoCreate`/`TodoUpdate`/`TodoRead` tuỳ nhu cầu hiển thị/nhập.
3. `tests/test_todos.py` — thêm test cho field mới.
4. Xoá file `todo.db` cũ (SQLite không tự động migrate schema) rồi chạy lại server để bảng được tạo
   lại với cột mới — dự án demo chưa có Alembic/migration tool.
