# Báo cáo: Seed data đầy đủ 3 project + Upload tài liệu lên Cloudinary

> Trạng thái: **ĐÃ HOÀN THÀNH** — thực hiện theo [plan-seed-data-cloudinary.md](./plan-seed-data-cloudinary.md) (đã điều chỉnh: 3 project khác tech stack thay vì 1 project theo yêu cầu bổ sung, và dùng cơ chế "upload 1 lần + xuất SQL portable" thay vì mỗi người tự upload).
> Ngày: 2026-08-11.

## Tóm tắt
Đã seed đầy đủ dữ liệu demo cho 3 project với 3 tech stack khác nhau, upload 24 file tài liệu mẫu lên Cloudinary (tài khoản free tier), và sinh ra 1 file SQL chứa sẵn URL thật để **bất kỳ ai trong team chạy lại cũng có đủ data, không cần tài khoản Cloudinary riêng**.

## 1. 3 project demo

| Key | Tên | Tech stack | Chủ đề |
|---|---|---|---|
| `PHONESHOP` | PhoneShop API | Python (FastAPI) | Bán điện thoại |
| `TOURBOOK` | TourBooking Service | Java (Spring Boot) | Đặt tour du lịch |
| `FURNISTORE` | FurniStore | Node.js (Express) | Bán nội thất |

Mỗi project có nội dung tài liệu **khác biệt thật sự theo tech stack** (ví dụ: PhoneShop hướng dẫn `poetry install` + `alembic`, TourBook hướng dẫn `./mvnw` + Flyway, FurniStore hướng dẫn `pnpm` + Prisma) — không phải copy-paste đổi tên.

## 2. Dữ liệu đã seed (`scripts/seed_dev_data.py`)

| Bảng | Số lượng | Chi tiết |
|---|---|---|
| `users` | 10 | 1 ADMIN, 1 HR, 3 PM (1/project), 3 ENGINEER (1/project) — PM/Engineer có `system_role=NULL` |
| `projects` | 3 | PHONESHOP, TOURBOOK, FURNISTORE, đã gán `primary_pm_membership_id` |
| `project_memberships` | 6 | 1 PM + 1 ENGINEER / project |
| `onboarding_templates` + `template_versions` | 1 + 1 | Template GLOBAL "Standard Engineer Onboarding", dùng chung cho cả 3 project |
| `template_tasks` + `task_dependencies` | 6 + 5 | 6 task theo 6 category (ORIENTATION→ACCESS→SETUP→CODEBASE→CONVENTION→FIRST_TASK), phụ thuộc tuần tự |
| `onboarding_plans` + `plan_tasks` | 3 + 18 | 1 plan/engineer, materialize từ template, trạng thái demo đa dạng (2 DONE, 1 IN_PROGRESS, 3 NOT_STARTED mỗi plan) |
| `blockers` + `blocker_attachments` | 3 + 3 | 1 blocker OPEN/project (nhóm ACCESS) kèm 1 attachment demo |

Script idempotent — chạy lại nhiều lần không tạo trùng (check tồn tại theo email/key trước khi insert).

## 3. Upload tài liệu lên Cloudinary + sinh SQL portable

**Vấn đề cần giải quyết**: không thể bắt mỗi thành viên team tự tạo tài khoản Cloudinary chỉ để có data demo giống nhau.

**Giải pháp đã làm**: `scripts/upload_sample_docs_to_cloudinary.py`
1. Đọc 24 file Markdown ở `docs/setup-be/sample-docs/{phoneshop,tourbook,furnistore,policy}/`.
2. Upload lên Cloudinary **1 lần duy nhất** (từ máy tôi, dùng credential trong `.env`).
3. Với mỗi file: chia nhỏ theo heading `## ` thành các "chunk" demo (chưa chạy pipeline embedding thật — đúng như đã ghi rõ trong plan gốc).
4. Sinh ra file **`scripts/sql/seed_knowledge_documents.sql`** — chứa sẵn URL Cloudinary thật, dùng subquery tra theo `key`/`email` (không hardcode ID số) để chạy đúng trên bất kỳ DB nào đã chạy `seed_dev_data.py` trước đó.

**Cách team dùng** (không cần Cloudinary):
```bash
python scripts/seed_dev_data.py
docker exec -i <container_postgres> psql -U app -d pgonboarding < scripts/sql/seed_knowledge_documents.sql
```
Chỉ người **cập nhật nội dung tài liệu mẫu** mới cần chạy lại `upload_sample_docs_to_cloudinary.py` (cần Cloudinary credential) để sinh SQL mới.

## 4. Bug gặp phải và đã sửa

1. **`datetime.now(timezone.utc)` vs cột `TIMESTAMP WITHOUT TIME ZONE`**: asyncpg từ chối bind datetime có timezone vào cột naive → đổi sang `datetime.utcnow()` (naive) trong `seed_dev_data.py`.
2. **`UnicodeEncodeError` khi print tiếng Việt trên console Windows** (mặc định cp1252, không phải lỗi dữ liệu — data đã insert đúng trước khi print crash): thêm `sys.stdout.reconfigure(encoding="utf-8")` đầu 2 script.
3. **Code thừa/lỗi khi tự viết hàm sinh SQL cho `document_chunks`** (1 dòng bị lặp `FROM ver, (VALUES` do sót logic nháp): dọn lại cho sạch trước khi chạy.

## 5. Kết quả verify

- Cả 24 file đều lên Cloudinary thật, kiểm tra `curl` → `HTTP 200`, nội dung UTF-8 tiếng Việt hiển thị đúng.
- DB sau khi apply SQL: **24 `knowledge_documents`, 24 `document_versions`, 99 `document_chunks`**, đúng khớp `document_category`/`policy_category` theo từng loại.
- `pytest tests/ -v` → 3/3 pass.
- `alembic check` → không có drift.
- Rebuild Docker (`docker compose up -d --build`) với dependency `cloudinary` mới.

## 6. Việc còn lại (chưa làm, ngoài phạm vi lần này)

- `ChatSession`/`ChatMessage`/`Citation` demo (hỏi-đáp có trích dẫn từ chunk) — chưa seed, có thể làm ở round sau khi cần demo tính năng chat.
- `document_chunks.vector_id` hiện là placeholder (`demo-<title>-<index>`), chưa chạy qua embedding model thật + ChromaDB — cần làm khi triển khai pipeline RAG thật.
- Router/service CRUD cho `KnowledgeDocument`, `OnboardingPlan`, `Blocker`... vẫn đang khung comment, chưa code logic thật (đã ghi trong báo cáo trước).
