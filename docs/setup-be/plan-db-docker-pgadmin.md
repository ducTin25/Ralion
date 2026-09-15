# Plan: PostgreSQL trong Docker + Entity đầu tiên (auto-gen table) + Kết nối pgAdmin

> Trạng thái: **CHỜ DUYỆT** — chưa code, chỉ để review trước khi triển khai.
> Đây là bản thu hẹp của Phase A + phần đầu Phase B trong [plan-bo06-scaffold.md](./plan-bo06-scaffold.md), tập trung vào 1 mục tiêu cụ thể: dựng Postgres chạy trong Docker, tạo 1 entity SQLAlchemy, cho Alembic tự sinh bảng tương ứng, rồi xem bảng đó bằng pgAdmin (giống cách bạn đang xem project "Tourism Microservices" trong ảnh).

> **Cập nhật hướng vector store**: đã đổi từ pgvector → **ChromaDB** (tự host, miễn phí, phù hợp quy mô tool nội bộ). PostgreSQL vì vậy dùng image thường (`postgres:16`), không cần extension vector. Chroma chạy ở chế độ **persistent client** (embedded trong process backend, ghi file xuống `./data/chroma`) — không cần thêm service/container riêng trong `docker-compose.yml`, không có UI kiểu pgAdmin (dữ liệu vector không xem trực tiếp bằng SQL được, chỉ Postgres mới xem qua pgAdmin).

## Mục tiêu
1. Postgres (bảng quan hệ/metadata) chạy trong container qua `docker-compose`. ChromaDB (vector embedding) chạy embedded, lưu file cục bộ — không cần container riêng.
2. Định nghĩa entity bằng SQLAlchemy (Python) — tương đương `@Entity` bên Java.
3. Alembic đọc entity, tự sinh migration, chạy migration → bảng xuất hiện thật trong Postgres (không phải "auto-ddl" lúc runtime như Hibernate `ddl-auto=update`, mà là migration có file, có thể review — đã giải thích ở lượt chat trước).
4. Kết nối pgAdmin vào Postgres đang chạy trong Docker để xem bảng bằng UI, y như ảnh bạn gửi (Query Tool → `SELECT * FROM ...`).

## Bước 1 — Thêm service Postgres vào `docker-compose.yml`
Thêm service `db` dùng image Postgres thường (không cần pgvector nữa vì vector embedding sẽ do Chroma quản lý riêng), map ra cổng `5432` trên máy host để pgAdmin (chạy ngoài Docker) kết nối được:

```yaml
services:
  db:
    image: postgres:16
    restart: unless-stopped
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: pgonboarding
    ports:
      - "5432:5432"          # host:container — pgAdmin sẽ connect vào localhost:5432
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d pgonboarding"]
      interval: 5s
      timeout: 5s
      retries: 10

  backend:
    # ... giữ nguyên, thêm:
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./data:/app/data     # đã có sẵn — đây cũng là nơi Chroma ghi file persist (./data/chroma)

volumes:
  pgdata:
```

Lưu ý: nếu máy bạn **đã có Postgres 16 chạy sẵn ngoài Docker** (thấy trong ảnh pgAdmin có server "PostgreSQL 16" riêng), cổng `5432` trên host có thể đã bị chiếm. Nếu vậy đổi map cổng thành ví dụ `"5433:5432"` và khi kết nối pgAdmin dùng Port = `5433`.

## Bước 2 — Cấu hình `.env` / `.env.example`
```
DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/pgonboarding
POSTGRES_USER=app
POSTGRES_PASSWORD=app
POSTGRES_DB=pgonboarding
CHROMA_PERSIST_DIR=./data/chroma
```
(`CHROMA_PERSIST_DIR` đã có sẵn field tương ứng trong `src/config.py` — chỉ cần bật dùng, không cần thêm gì mới. Nếu backend chạy trong Docker cùng network với `db`, host Postgres sẽ là `db` thay vì `localhost` — sẽ chốt cụ thể lúc code.)

## Bước 3 — Bật dependency Python
Trong `requirements.txt`, bỏ comment và thêm:
```
sqlalchemy>=2.0.36
alembic>=1.14.0
asyncpg>=0.30.0

# Vector Store
chromadb>=0.5.0
```
(Dòng `chromadb>=0.5.0` đã có sẵn trong file, chỉ cần bỏ comment — không cần thêm gói `pgvector` nữa.)

## Bước 4 — Tạo entity đầu tiên (ví dụ: `User`)
Tạo `src/db/base.py` (Base class dùng chung) và `src/db/models/identity.py` với 1 entity mẫu để chứng minh luồng chạy được trước khi làm hết 21 entity:

```python
# src/db/models/identity.py (minh hoạ, chưa code thật)
class User(Base):
    __tablename__ = "users"
    user_id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus, name="user_status"), default=UserStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```
Đây chính là phần tương đương `@Entity`/`@Table`/`@Column` bên Spring Boot.

## Bước 5 — Alembic sinh & chạy migration (bảng xuất hiện thật trong Postgres)
```bash
alembic init -t async alembic          # 1 lần duy nhất
alembic revision --autogenerate -m "create users table"   # đọc entity, sinh file migration
alembic upgrade head                   # chạy migration → CREATE TABLE users thật trong Postgres
```
Sau bước này, bảng `users` sẽ tồn tại thật trong database `pgonboarding` chạy trong container Docker — đây là lúc bạn có thể mở pgAdmin để xác nhận.

## Bước 6 — Kết nối pgAdmin vào Postgres trong Docker
Trong pgAdmin (đang mở sẵn theo ảnh bạn gửi):
1. Chuột phải vào **Servers** → **Register** → **Server...**
2. Tab **General**:
   - Name: `P-040 Onboarding Buddy (Docker)`
3. Tab **Connection**:
   - Host name/address: `localhost`
   - Port: `5432` (hoặc `5433` nếu bị trùng cổng, xem lưu ý ở Bước 1)
   - Maintenance database: `pgonboarding`
   - Username: `app`
   - Password: `app`
   - (tuỳ chọn) tick **Save password**
4. Bấm **Save**.

Sau khi kết nối thành công, cây bên trái sẽ có thêm:
```
Servers
 └─ P-040 Onboarding Buddy (Docker)
     └─ Databases
         └─ pgonboarding
             └─ Schemas
                 └─ public
                     └─ Tables
                         └─ users   ← bảng vừa được Alembic tạo
```
Chuột phải vào `users` → **View/Edit Data** → **All Rows**, hoặc mở **Query Tool** và chạy:
```sql
SELECT * FROM public.users ORDER BY user_id ASC;
```
— y hệt cách bạn đang xem `outbox_events` trong ảnh, chỉ khác server/database.

## Bước 7 — Verification checklist
- [ ] `docker compose up -d db` → container healthy (`docker compose ps` báo `healthy`).
- [ ] `alembic upgrade head` chạy không lỗi.
- [ ] pgAdmin kết nối được server Docker mới, thấy database `pgonboarding`.
- [ ] Bảng `users` xuất hiện dưới `Schemas > public > Tables`.
- [ ] Query Tool `SELECT * FROM users;` chạy được (trả về 0 dòng vì chưa insert data, nhưng không lỗi).

## Sau khi bạn duyệt bước này
Nếu OK, các entity còn lại (20 entity trong 5 nhóm — xem [plan-bo06-scaffold.md](./plan-bo06-scaffold.md)) sẽ làm theo đúng luồng y hệt: định nghĩa entity → `alembic revision --autogenerate` → `alembic upgrade head` → kiểm tra lại trong pgAdmin, lặp lại theo từng phase B→F đã thống nhất.
