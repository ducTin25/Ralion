# Báo cáo: Đồng bộ Model theo spec mới (systemRole, knowledgeDomain, First PR, BlockerAttachment...)

> Trạng thái: **ĐÃ HOÀN THÀNH** — thực hiện theo [plan-model-sync-spec-moi.md](./plan-model-sync-spec-moi.md).
> Ngày: 2026-08-11.

## Tóm tắt
Đã đồng bộ `src/model/*.py` theo quyết định thiết kế mới từ Google Doc (mục "Critical Schema Changes (from P-040)"), tạo + apply migration `087bc97c54cf`, rebuild Docker image, seed lại data, verify qua Docker container thật. Toàn bộ 3 test hiện có vẫn pass, `alembic check` sạch.

## 1. Thay đổi model đã áp dụng

| Entity | Thay đổi |
|---|---|
| `User` | Đổi cột `role`→`system_role`, enum `UserRole` chỉ còn `ADMIN`/`HR` (bỏ `PM`/`ENGINEER`), cột **nullable** — nhân viên thường để trống, quyền theo dự án đọc từ `ProjectMembership.project_role` |
| `Project` | Thêm `created_at: DateTime NOT NULL` |
| `KnowledgeDocument` | Đổi `scope (ORGANIZATION\|PROJECT)` → `knowledge_domain (PROJECT\|POLICY)`; xoá field `category` gộp chung, tách thành `document_category` (7 giá trị, chỉ dùng khi domain=PROJECT) + `policy_category` (6 giá trị mới, chỉ dùng khi domain=POLICY); CHECK constraint mới enforce đúng 1 trong 2 field có giá trị theo domain |
| `OnboardingPlan` | Thêm `first_pr_url`, `first_pr_merged_at`, `first_pr_confirmed_by_user_id` (theo dõi mốc First PR) |
| `Blocker` | Thêm entity liên quan mới `BlockerAttachment` (1 blocker – nhiều file đính kèm: `storage_key`, `file_name`, `mime_type`, `uploaded_at`) |
| `ChatSession` | Thêm `user_id NOT NULL` (để ADMIN/HR/PM không có membership vẫn chat được), `knowledge_domain`, `project_id?`; `membership_id` đổi thành **nullable** |
| `SupportDepartment`, `SupportRequest` | **Xoá khỏi MVP** — theo quyết định: Engineer báo BLOCKED, PM dự án tự xử lý, chưa cần ticket liên phòng ban |
| `AuditLog`, `Notification` | **Xoá khỏi MVP** — ngoài phạm vi theo phân công team |

**Enum liên quan**: xoá `DocumentScope`, `SupportType`, `TicketPriority`, `TicketStatus`, `NotificationType`; thêm `DocumentDomain`, `PolicyCategory`; sửa lại `UserRole`, `DocumentCategory`.

**Kết quả**: từ 21 entity còn **18 entity** (19 bảng gồm cả `blocker_attachments` mới, trừ `alembic_version`).

## 2. Migration `087bc97c54cf`

File tự sinh (`alembic revision --autogenerate`) ban đầu có **2 lỗi thật**, đã sửa tay trước khi apply:

1. **Enum type không tự tạo với `op.add_column`**: khác với `op.create_table` (tự phát `CREATE TYPE`), `op.add_column` đơn lẻ không tự tạo Postgres enum type — phải gọi tường minh `postgresql.ENUM(...).create(bind, checkfirst=True)` trước, rồi dùng `create_type=False` khi khai cột.
2. **Trùng tên type khi đổi giá trị enum**: `system_role` dùng lại tên type `user_role` nhưng khác tập giá trị với type `role` cũ — phải `DROP TYPE user_role` (sau khi drop cột `role` cũ) rồi mới `CREATE TYPE` lại. Áp dụng tương tự cho `document_category` (giá trị cũ có `POLICY`/`WORKFLOW`/`REFERENCE_PR`, giá trị mới khác hẳn).
3. (Đã tự phát hiện thêm) **Thứ tự DROP TABLE sai**: `support_departments` bị drop trước `support_requests` dù `support_requests` có FK trỏ tới nó — Postgres từ chối. Đổi thứ tự: drop bảng phụ thuộc trước.

Migration cuối cùng chạy sạch cả `upgrade()` lẫn `downgrade()` (đã viết tay đối xứng, xử lý đúng thứ tự DROP TYPE/CREATE TYPE cho rollback).

## 3. Xử lý seed data cũ

Bảng `users` có sẵn 6 row từ trước với `role=ENGINEER/PM` — giá trị này không tồn tại trong enum `user_role` mới. Vì chỉ là dev/test data, đã `TRUNCATE TABLE users CASCADE` trước khi migrate (cascade xoá luôn data ở các bảng con tham chiếu `users` — chấp nhận được vì toàn bộ đang là data test). Sau migration, chạy lại `scripts/seed_dev_data.py` (đã cập nhật: `admin`/`hr` có `system_role`, `pm`/`engineer` để `system_role=None`).

## 4. Code tầng API đã cập nhật theo (để không vỡ khi rebuild)

Vì đổi tên cột `role`→`system_role` sẽ làm `User(role=...)` lỗi ngay khi gọi (dù import không lỗi), đã sửa luôn 4 file liên quan tới `User` (nằm ngoài phạm vi ban đầu của plan nhưng cần để giữ API chạy được sau rebuild):
- `src/dto/request/user_request_dto.py` — field `role`→`system_role`
- `src/dto/response/user_response_dto.py` — field `role`→`system_role`
- `src/services/user_service.py` — `create_user`/`update_user` dùng `system_role`
- `scripts/seed_dev_data.py` — seed đúng theo enum mới

## 5. Verify

- `alembic upgrade head` chạy sạch, `alembic check` → "No new upgrade operations detected".
- `\dt` trong Postgres: 19 bảng đúng danh sách (4 bảng cũ biến mất, `blocker_attachments` xuất hiện).
- `\d users`, `\d knowledge_documents` → đúng cột, đúng CHECK constraint như thiết kế.
- Rebuild Docker (`docker compose up -d --build`) thành công, container `backend`+`db` đều `healthy`.
- Test qua HTTP thật trên container Docker (`http://localhost:8000/api/v1/users`) — trả đúng `system_role: "ADMIN"/"HR"/null`.
- `pytest tests/ -v` — 3/3 test pass.

## 6. Việc còn lại (chưa làm, ngoài phạm vi lần này)

- DTO/service/router cho `Project`, `KnowledgeDocument` vẫn đang ở dạng khung (comment, chưa code logic) — cần cập nhật khớp field mới (`created_at`, `knowledge_domain`, `document_category`/`policy_category`) khi triển khai thật.
- Chưa có DTO/service/router cho `BlockerAttachment`, `ChatSession` (đổi field), `OnboardingPlan` (thêm field First PR).
- Chưa có validation tầng service cho các rule mới: ví dụ "chỉ 1 trong document_category/policy_category có giá trị" đã có CHECK ở DB, nhưng rule như "First PR chỉ set khi PlanTask liên quan đã DONE" (nếu có) chưa được enforce ở đâu.
- Repository scanner (ZIP upload), Object Storage, signed URL — các phần mới nhắc tới trong doc, hoàn toàn chưa có code (ngoài phạm vi model).
