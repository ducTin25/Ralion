# notes-final

Cài Python 3.11, tạo virtualenv bằng `python -m venv .venv`, activate rồi `pip install -r
requirements.txt`. Copy `.env.example` thành `.env`. Chạy server bằng `uvicorn app.main:app
--reload`, mở `http://127.0.0.1:8000/docs` để test thử API.

Nếu port 8000 bị chiếm thì đổi port khác. Chạy test bằng `pytest tests/`.

> Ghi chú: nội dung file này gần như trùng với `docs/setup/local-setup.md`, nhưng đặt tên
> "notes-final.md" — không theo convention đặt tên tài liệu nào cả. Đây là case cố tình để test
> scanner Phase 3 nhận diện đúng category (`SETUP`) dựa trên **nội dung**, không chỉ dựa vào tên
> file hoặc đường dẫn thư mục.
