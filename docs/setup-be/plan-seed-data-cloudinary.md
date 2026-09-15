# Plan: Seed data đầy đủ + 3 bộ tài liệu mẫu + upload Cloudinary + lưu URL vào Postgres

> Trạng thái: **CHỜ DUYỆT** — chưa code, chỉ để review trước khi triển khai.

## Mục tiêu
1. Có sẵn **seed data đầy đủ** cho các bảng chính, để ai clone repo về chạy lên là có data test được các chức năng ngay (không phải tự tay tạo project/plan/task từ đầu).
2. Tạo **3 bộ tài liệu mẫu** (file thật, dạng Markdown/PDF) ứng với 3 project khác nhau, đúng cấu trúc `KnowledgeDocument` (7 category: OVERVIEW, ARCHITECTURE, SETUP, ACCESS_SECURITY, CODEBASE_GUIDE, CONVENTION, FIRST_TASK) + vài tài liệu POLICY dùng chung công ty.
3. **Upload các file đó lên Cloudinary** (object storage), lấy URL — Postgres chỉ lưu URL (`source_url`, `storage_uri`), không lưu file thật trong DB, đúng nguyên tắc đã ghi trong đặc tả gốc.

## 1. Seed data đầy đủ

Mở rộng `scripts/seed_dev_data.py` hiện tại (mới có 4 `User`) thành seed đủ chuỗi nghiệp vụ, theo đúng thứ tự phụ thuộc FK:

| Bước | Bảng | Số lượng mẫu | Ghi chú |
|---|---|---|---|
| 1 | `users` | 4 (đã có) | admin, hr, + 2 "nhân viên thường" (pm/engineer, `system_role=NULL`) |
| 2 | `projects` | **3** | 3 project mẫu (xem mục 2) |
| 3 | `project_memberships` | ~6 | mỗi project: 1 PM + 1-2 ENGINEER |
| 4 | `projects.primary_pm_membership_id` | update | gán PM chính sau khi có membership (do vòng lặp FK) |
| 5 | `onboarding_templates` + `template_versions` + `template_tasks` + `task_dependencies` | 1 template GLOBAL, ~5-7 task | checklist onboarding mẫu dùng chung |
| 6 | `knowledge_documents` + `document_versions` + `document_chunks` | 3 project × 7 category + ~3 policy doc org-wide | nội dung thật lấy từ file mục 2, `document_chunks` seed vài chunk demo (chưa chạy pipeline embedding thật) |
| 7 | `onboarding_plans` + `plan_tasks` + `plan_task_sources` | 1 plan/engineer | materialize từ template ở bước 5 |
| 8 | `chat_sessions` + `chat_messages` + `citations` | 1-2 session mẫu | demo hội thoại có trích dẫn |
| 9 | `blockers` + `blocker_attachments` | 1-2 mẫu | demo 1 blocker OPEN |

Script chạy 1 lệnh (`python scripts/seed_dev_data.py`), idempotent (check tồn tại trước khi insert, như code hiện tại) để chạy lại nhiều lần không lỗi trùng.

## 2. 3 project mẫu + tài liệu

Đề xuất 3 project (đặt tên generic, có thể đổi khi duyệt):

| Project key | Tên | Chủ đề |
|---|---|---|
| `PAYMENT` | Payment Service | Backend xử lý thanh toán |
| `BOOKING` | Tourism Booking Platform | Đặt tour/booking (khớp tên "Tourism Microservices" đã thấy trong pgAdmin của bạn) |
| `MOBILE` | Mobile App | App di động nội bộ |

Mỗi project → **7 file Markdown** (khớp 7 `document_category`):
```
docs/setup-be/sample-docs/payment/
  overview.md
  architecture.md
  setup.md
  access-security.md
  codebase-guide.md
  convention.md
  first-task.md
docs/setup-be/sample-docs/booking/  (7 file tương tự)
docs/setup-be/sample-docs/mobile/   (7 file tương tự)
```
Nội dung mỗi file: 1-2 đoạn ngắn, đủ để demo RAG (không cần dài, chỉ cần thật/hợp lý về nghiệp vụ).

Thêm **3 file POLICY** dùng chung công ty (không gắn project, `project_id=NULL`), khớp `policy_category`:
```
docs/setup-be/sample-docs/policy/
  company-policy.md
  hr-policy.md
  security-policy.md
```

## 3. Hướng dẫn lấy Cloudinary API key

1. Vào **https://cloudinary.com** → **Sign up** (free tier: 25GB storage, 25GB bandwidth/tháng — đủ cho demo).
2. Sau khi đăng nhập, vào **Dashboard** (trang chủ sau login) → phần **Product Environment Credentials** sẽ hiện sẵn 3 giá trị:
   - `Cloud name`
   - `API Key`
   - `API Secret` (bấm "Reveal" để xem)
3. Copy 3 giá trị này vào `.env`:
   ```
   CLOUDINARY_CLOUD_NAME=xxx
   CLOUDINARY_API_KEY=xxx
   CLOUDINARY_API_SECRET=xxx
   ```
4. Không commit `.env` (đã có sẵn trong `.gitignore`).

## 4. Script upload lên Cloudinary + lưu URL vào Postgres

- Thêm dependency: `cloudinary` (Python SDK chính thức) vào `requirements.txt`.
- Thêm `cloudinary_cloud_name`, `cloudinary_api_key`, `cloudinary_api_secret` vào `src/config.py` (đọc từ `.env`).
- Script mới `scripts/upload_sample_docs_to_cloudinary.py`:
  1. Đọc toàn bộ file trong `docs/setup-be/sample-docs/**/*.md`.
  2. Với mỗi file: gọi `cloudinary.uploader.upload(file_path, resource_type="raw", folder="knowledge-documents/<project_key>")` → nhận về `secure_url`.
  3. Insert/update `KnowledgeDocument` (title, category, project_id tương ứng, `source_url = secure_url`) + `DocumentVersion` (version_no=1, `storage_uri = secure_url`, `checksum` = sha256 nội dung file, `status=ACTIVE`).
  4. In log từng file đã upload + URL, để dễ kiểm tra bằng tay trên Cloudinary Media Library.

## File sẽ tạo/sửa
- Sửa: `scripts/seed_dev_data.py` (mở rộng seed đầy đủ theo mục 1)
- Tạo mới: 24 file mẫu (`docs/setup-be/sample-docs/{payment,booking,mobile}/*.md` × 7, `docs/setup-be/sample-docs/policy/*.md` × 3)
- Tạo mới: `scripts/upload_sample_docs_to_cloudinary.py`
- Sửa: `requirements.txt` (thêm `cloudinary`), `src/config.py` (3 field Cloudinary), `.env.example`

## Việc bạn cần tự làm (tôi không làm thay được)
- Đăng ký tài khoản Cloudinary + lấy API key (mục 3) — cần đăng nhập tài khoản cá nhân/công ty của bạn.
- Dán 3 giá trị Cloudinary vào `.env` thật trên máy bạn.

## Verification
1. `python scripts/seed_dev_data.py` chạy xong → `\dt` các bảng có data (không rỗng).
2. `python scripts/upload_sample_docs_to_cloudinary.py` chạy xong → 27 file xuất hiện trên Cloudinary Media Library (kiểm tra bằng mắt trên web Cloudinary).
3. `SELECT source_url FROM knowledge_documents;` trong psql/pgAdmin → toàn bộ là URL Cloudinary thật (dạng `https://res.cloudinary.com/...`), không phải path local.
4. `GET /api/v1/knowledge-documents` (khi đã code router thật, hiện đang khung) trả về đúng data.
