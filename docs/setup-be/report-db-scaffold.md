# Báo cáo: Scaffold DB (21 entity) + Postgres Docker + pgAdmin + Seed data

> Trạng thái: **ĐÃ HOÀN THÀNH** — thực hiện theo [plan-db-docker-pgadmin.md](./plan-db-docker-pgadmin.md).
> Ngày: 2026-08-11.
> **Cập nhật 2026-08-11**: sau báo cáo này, đã đổi tên `src/db` → `src/model` và `src/models` → `src/dto/{request,response}` theo yêu cầu convention Java. Cấu trúc code ở mục 2 bên dưới **đã lỗi thời về đường dẫn** (giữ nguyên để tham khảo lịch sử) — xem cấu trúc thật hiện tại tại [project-structure.md](./project-structure.md).

## Tóm tắt
Đã dựng xong lớp persistence cho toàn bộ 21 entity trong class diagram BO-06: SQLAlchemy models (async) + Alembic migrations + Postgres 16 chạy trong Docker + ChromaDB (embedded) cho vector search. Đã chạy thật, verify bằng psql, và pytest vẫn xanh.

## 1. Hạ tầng

| Thành phần | Giá trị |
|---|---|
| Postgres | `postgres:16` (Docker), container `p-040-db-1` |
| Cổng host | **5433** (không dùng 5432 — máy đã có Postgres 16 native chiếm cổng này, xem mục "Sự cố") |
| Database | `pgonboarding` |
| User/Password | `app` / `app` (dev only, đổi khi lên production) |
| Vector store | ChromaDB, persistent client, ghi file tại `./data/chroma` (không chạy container riêng) |
| ORM | SQLAlchemy 2.0 (async) + asyncpg |
| Migration | Alembic (async template) |

Volume Postgres: named volume `pgdata` (Docker) — dữ liệu không mất khi container restart, chỉ mất khi `docker compose down -v`.

## 2. Cấu trúc code tạo mới

```
src/db/
  base.py                 # DeclarativeBase + naming convention cho constraint
  session.py               # async engine, async_sessionmaker, get_db()
  enums.py                 # 25 enum (toàn bộ domain model)
  __init__.py               # import 21 module entity để đăng ký lên Base.metadata
  user.py, project.py, project_membership.py                          # Identity & Access
  knowledge_document.py, document_version.py, document_chunk.py        # Project Knowledge
  onboarding_template.py, template_version.py, template_task.py,
  task_dependency.py, onboarding_plan.py, plan_task.py,
  plan_task_source.py                                                  # Template & Plan
  chat_session.py, chat_message.py, citation.py, blocker.py,
  support_department.py, support_request.py                            # RAG & Support
  audit_log.py, notification.py                                        # Cross-cutting

alembic/
  env.py                   # wired vào settings.database_url + Base.metadata
  versions/
    2fb68a7d5469_create_users_table.py            # migration #1: bảng users (proof of concept)
    9fbecdaefe53_add_remaining_20_entities.py      # migration #2: 20 entity còn lại
    092eacb97740_fix_check_constraint_names_and_add_.py  # migration #3: fix bug (xem mục 4)

scripts/
  seed_dev_data.py         # insert 4 user mẫu (ADMIN/PM/ENGINEER/HR)
```

**Quyết định cấu trúc**: mỗi entity 1 file riêng (không gộp theo nhóm domain như bản kế hoạch đầu), theo yêu cầu — giống convention "1 `@Entity` = 1 file" của JPA/Spring Boot. `enums.py` giữ chung 1 file vì là vocabulary dùng chéo nhiều entity, không phải bản thân 1 bảng DB.

## 3. Đã sửa những file có sẵn

- `requirements.txt`: bật `sqlalchemy`, `alembic`, `asyncpg`, `chromadb` (bỏ comment); không dùng `psycopg2-binary` (chỉ 1 driver async).
- `docker-compose.yml`: thêm service `db` (Postgres 16, cổng `5433:5432`, healthcheck, volume `pgdata`); `backend` thêm `depends_on: db (service_healthy)`.
- `.env`, `.env.example`: `DATABASE_URL=postgresql+asyncpg://app:app@localhost:5433/pgonboarding`, `POSTGRES_USER/PASSWORD/DB`, `CHROMA_PERSIST_DIR=./data/chroma`.
- `src/config.py`: `database_url` default trỏ Postgres thay vì sqlite.

## 4. Sự cố gặp phải khi triển khai (và cách đã sửa)

### 4.1. Xung đột cổng 5432
Máy đã có PostgreSQL 16 cài native (Windows service `postgresql-x64-16`) đang lắng nghe `0.0.0.0:5432`. Khi map container cũng ra `5432:5432`, kết nối từ host bị route lẫn lộn giữa 2 tiến trình (auth container thất bại dù đúng user/pass — do đôi khi trúng vào Postgres native). **Fix**: đổi cổng host sang **5433**. Container vẫn dùng `5432` bên trong, không ảnh hưởng gì nội bộ.

### 4.2. FK vòng lặp `Project ↔ ProjectMembership` không được tạo thật
Model khai báo `ForeignKey(..., use_alter=True)` để xử lý vòng lặp, nhưng khi Alembic autogenerate render thành `op.create_table()` riêng lẻ (không qua `MetaData.create_all()`), cờ `use_alter` **không tự động phát ra ALTER TABLE hoãn lại** như kỳ vọng — constraint bị bỏ sót hoàn toàn trong migration đầu. Phát hiện qua `alembic check` báo `add_fk` còn treo. **Fix**: migration `092eacb97740` thêm `op.create_foreign_key('fk_projects_primary_pm_membership_id', ...)` tường minh. Đã verify FK tồn tại thật trong `\d projects`.

### 4.3. Tên CHECK constraint bị lặp prefix
Naming convention của `Base.metadata` đã tự thêm `ck_<table>_` vào tên constraint, nhưng tôi lại tự tay thêm `ck_<table>_` một lần nữa khi gọi `CheckConstraint(name=...)` → sinh ra tên kiểu `ck_support_departments_ck_support_departments_response_sla_positive` (Postgres cắt còn 63 ký tự kèm hash, dẫn tới lệch với tên "sạch" mà autogenerate mong đợi). **Fix**: bỏ prefix tự thêm, để naming convention tự lo — tên cuối cùng gọn: `ck_support_departments_response_sla_positive`.

Sau khi sửa cả 2 lỗi, `alembic check` báo **"No new upgrade operations detected"** — model, migration, và DB thật đã khớp 100%.

## 5. Kết quả verify

- `docker compose up -d db` → container `healthy`.
- `alembic upgrade head` chạy sạch qua cả 3 migration, không lỗi.
- `alembic check` → không còn drift.
- 22 bảng trong Postgres (21 entity + `alembic_version`) — xem `\dt` output.
- FK vòng lặp `projects.primary_pm_membership_id → project_memberships.membership_id` tồn tại thật.
- Seed script `scripts/seed_dev_data.py` chạy thành công, insert 4 user mẫu (`admin@onboarding.dev`, `pm@onboarding.dev`, `engineer@onboarding.dev`, `hr@onboarding.dev`).
- `pytest tests/ -v` → **5/5 test cũ pass** (không có test mới cho lớp DB ở bước này — nằm ngoài phạm vi yêu cầu hiện tại).

## 6. Cách xem dữ liệu bằng pgAdmin

Theo hướng dẫn ở [plan-db-docker-pgadmin.md](./plan-db-docker-pgadmin.md), **chỉ cần đổi Port từ 5432 thành 5433** (do sự cố mục 4.1):

1. Servers → Register → Server...
2. General → Name: `P-040 Onboarding Buddy (Docker)`
3. Connection → Host: `localhost`, **Port: `5433`**, Maintenance database: `pgonboarding`, Username: `app`, Password: `app`.
4. Save → mở `Databases > pgonboarding > Schemas > public > Tables` → sẽ thấy đủ 21 bảng.
5. Chuột phải bảng `users` → View/Edit Data → All Rows → thấy 4 user vừa seed.

## 7. Việc còn lại (chưa làm, ngoài phạm vi lần này)

- Router CRUD (`src/api/routers/*.py`) cho từng entity — chưa làm, mới có `/chat`, `/status` cũ.
- Test tự động cho lớp DB (`tests/test_db/`) — chưa có, hiện chỉ verify thủ công qua psql/pytest cũ.
- CI (`.github/workflows/ci.yml`) chưa có Postgres service container — cần thêm trước khi có test đụng DB.
- Pipeline RAG/LangGraph thực sự dùng ChromaDB — chưa làm, mới dừng ở việc bật dependency + cấu hình `CHROMA_PERSIST_DIR`.
