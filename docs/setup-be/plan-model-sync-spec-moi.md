# Plan: Cập nhật lại Model theo spec mới nhất (Google Doc "Critical Schema Changes")

> Trạng thái: **CHỜ DUYỆT** — chưa code, chỉ để review trước khi triển khai.

## Context
User gửi 2 link tới cùng 1 Google Doc (khác tab) chứa **quyết định thay đổi thiết kế mới**, được viết dưới dạng so sánh trực tiếp với chính repo P-040 hiện tại (doc có mục "Critical Schema Changes (from P-040)" và "Phân công TV1-TV4" — cho thấy đây là tài liệu làm việc nhóm, nhiều người sẽ dựa vào để code). Đã fetch nội dung doc và đối chiếu từng entity với `src/model/*.py` hiện có.

**Phạm vi lần này** (theo yêu cầu): chỉ sửa lớp **model SQLAlchemy** (`src/model/*.py`, `enums.py`) cho khớp spec mới + migration tương ứng. **Chưa đụng tới DTO/service/router** (kể cả của `User` — sẽ update riêng sau khi model chốt xong, vì đổi field sẽ kéo theo đổi DTO/service).

## Bảng so sánh: hiện tại vs spec mới

| Entity | Hiện tại (`src/model/`) | Spec mới yêu cầu | Hành động |
|---|---|---|---|
| **User** | `role: UserRole (ADMIN\|PM\|ENGINEER\|HR)` NOT NULL | `systemRole: (ADMIN\|HR\|NULL)` — bỏ PM/ENGINEER khỏi role toàn hệ thống, role thật giờ đọc từ `ProjectMembership.projectRole` | Đổi tên cột `role`→`system_role`, đổi enum còn `ADMIN`/`HR`, cho **nullable** (nhân viên thường = NULL) |
| **Project** | Không có `created_at` | `createdAt: DateTime NOT NULL` | Thêm cột `created_at` (server_default=now()) |
| **KnowledgeDocument** | `scope: DocumentScope (ORGANIZATION\|PROJECT)`, 1 field `category: DocumentCategory` (9 giá trị gộp chung, có `POLICY`, `WORKFLOW`, `REFERENCE_PR`) | `knowledgeDomain: (PROJECT\|POLICY)` + tách 2 field riêng: `documentCategory` (7 giá trị, chỉ dùng khi domain=PROJECT: OVERVIEW, ARCHITECTURE, SETUP, ACCESS_SECURITY, CODEBASE_GUIDE, CONVENTION, **FIRST_TASK** — bỏ WORKFLOW/REFERENCE_PR) + `policyCategory` (enum mới, chỉ dùng khi domain=POLICY: COMPANY_POLICY, HR_POLICY, SECURITY_POLICY, BENEFIT, WORKING_RULE, GENERAL) | Đổi `scope`→`knowledge_domain` (enum mới `DocumentDomain`), xoá field `category` cũ, thêm `document_category` (nullable) + `policy_category` (nullable, enum mới `PolicyCategory`), sửa lại CHECK constraint theo domain |
| **OnboardingPlan** | Không có field theo dõi First PR | Thêm `firstPrUrl: String?`, `firstPrMergedAt: DateTime?`, `firstPrConfirmedByUserId: Integer? FK→User` | Thêm 3 cột nullable |
| **Blocker** | Không có đính kèm file | Cần đính kèm file cho blocker | Tạo entity mới **`BlockerAttachment`** (1 blocker – nhiều attachment, theo lựa chọn đã chốt): `attachment_id PK, blocker_id FK→blockers, storage_key, file_name, mime_type, uploaded_at` |
| **ChatSession** | `membership_id` NOT NULL, không có `user_id`/`knowledge_domain`/`project_id` | Thêm `userId NOT NULL FK→User` (để ADMIN/HR/PM không có membership vẫn chat được), `knowledgeDomain (PROJECT\|POLICY)`, `projectId?`, **`membershipId` đổi thành nullable** | Thêm 3 cột, sửa `membership_id` thành nullable |
| **SupportDepartment** | Đã tạo bảng | **Xoá khỏi MVP** — quyết định 2.5: "Đồng ý xóa trong MVP. BO-06 chỉ cần Engineer báo BLOCKED trên PlanTask và PM của dự án xử lý; chưa cần nền tảng ticket liên phòng ban." | Xoá file model + DROP TABLE trong migration |
| **SupportRequest** | Đã tạo bảng | **Xoá khỏi MVP** (cùng lý do trên, phụ thuộc SupportDepartment) | Xoá file model + DROP TABLE |
| **AuditLog** | Đã tạo bảng | **Ngoài phạm vi MVP** — mục 7 (Phân công): "Notification, Audit Log, ticket routing và thông báo approval plan được đưa ra ngoài phạm vi MVP." | Xoá file model + DROP TABLE |
| **Notification** | Đã tạo bảng | **Ngoài phạm vi MVP** (cùng câu trên) | Xoá file model + DROP TABLE |

Các entity còn lại (`ProjectMembership`, `DocumentVersion`, `DocumentChunk`, `OnboardingTemplate`, `TemplateVersion`, `TemplateTask`, `TaskDependency`, `PlanTask`, `PlanTaskSource`, `ChatMessage`, `Citation`) — **không đổi**, khớp spec mới.

## Chi tiết kỹ thuật

**1. `src/model/enums.py`**:
- `UserRole` → đổi thành chỉ còn `ADMIN`, `HR` (bỏ `PM`, `ENGINEER`).
- Xoá `DocumentScope`, thêm `DocumentDomain (PROJECT|POLICY)`.
- Sửa `DocumentCategory`: bỏ `POLICY`, `WORKFLOW`, `REFERENCE_PR`; thêm `FIRST_TASK`.
- Thêm enum mới `PolicyCategory (COMPANY_POLICY|HR_POLICY|SECURITY_POLICY|BENEFIT|WORKING_RULE|GENERAL)`.

**2. `src/model/user.py`**: cột `role` → `system_role`, `Mapped[UserRole | None]`, nullable=True.

**3. `src/model/project.py`**: thêm `created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)`.

**4. `src/model/knowledge_document.py`**:
- `scope` → `knowledge_domain: Mapped[DocumentDomain]`.
- Xoá `category`, thêm `document_category: Mapped[DocumentCategory | None]` + `policy_category: Mapped[PolicyCategory | None]`.
- Sửa lại `CheckConstraint`: `(knowledge_domain='PROJECT' AND project_id IS NOT NULL AND document_category IS NOT NULL AND policy_category IS NULL) OR (knowledge_domain='POLICY' AND project_id IS NULL AND policy_category IS NOT NULL AND document_category IS NULL)`.

**5. `src/model/onboarding_plan.py`**: thêm `first_pr_url: Mapped[str | None]`, `first_pr_merged_at: Mapped[datetime | None]`, `first_pr_confirmed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))`.

**6. `src/model/blocker_attachment.py`** (mới):
```python
class BlockerAttachment(Base):
    __tablename__ = "blocker_attachments"
    attachment_id: Mapped[int] = mapped_column(primary_key=True)
    blocker_id: Mapped[int] = mapped_column(ForeignKey("blockers.blocker_id"), nullable=False)
    storage_key: Mapped[str] = mapped_column(nullable=False)
    file_name: Mapped[str] = mapped_column(nullable=False)
    mime_type: Mapped[str] = mapped_column(nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
```

**7. `src/model/chat_session.py`**: thêm `user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)`, `knowledge_domain: Mapped[DocumentDomain]`, `project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.project_id"))`; sửa `membership_id` thành `Mapped[int | None]`.

**8. Xoá file**: `src/model/support_department.py`, `src/model/support_request.py`, `src/model/audit_log.py`, `src/model/notification.py`. Xoá import tương ứng trong `src/model/__init__.py`.

**9. Migration**: `alembic revision --autogenerate -m "sync model voi spec moi: systemRole, knowledgeDomain, firstPR, BlockerAttachment, ChatSession.userId, xoa SupportDept/SupportRequest/AuditLog/Notification"` — review kỹ file sinh ra (đặc biệt lệnh `DROP TABLE` và `ALTER COLUMN ... TYPE` cho enum đổi giá trị, Postgres cần `USING` clause khi đổi enum có giá trị bị xoá) rồi `alembic upgrade head`.

⚠️ Lưu ý: đổi giá trị enum `UserRole`/`DocumentCategory` (xoá giá trị cũ) trên cột đã có dữ liệu (bảng `users` đang có 6 row với `role=ENGINEER/PM` từ seed) sẽ lỗi vì giá trị cũ không map được sang enum mới. Cần xử lý: xoá data seed cũ trước khi migrate (chấp nhận được vì chỉ là dev/test data), hoặc migration có bước update data trước khi đổi kiểu cột.

## File sẽ sửa/xoá/tạo
- Sửa: `src/model/enums.py`, `src/model/user.py`, `src/model/project.py`, `src/model/knowledge_document.py`, `src/model/onboarding_plan.py`, `src/model/chat_session.py`, `src/model/__init__.py`
- Tạo mới: `src/model/blocker_attachment.py`
- Xoá: `src/model/support_department.py`, `src/model/support_request.py`, `src/model/audit_log.py`, `src/model/notification.py`
- Migration mới: `alembic/versions/xxxx_sync_model_voi_spec_moi.py`

## Ngoài phạm vi lần này (ghi chú, không làm)
- `user_request_dto.py`/`user_response_dto.py`/`user_service.py`/`user_router.py` đang dùng field `role` — sẽ vỡ sau khi đổi tên cột, cần sửa theo sau (round riêng).
- 5 file khung (`service`/`router` rỗng comment) của `Project`, `ProjectMembership`, `KnowledgeDocument`, `DocumentVersion`, `DocumentChunk` — không đụng tới lần này.
- Seed script `scripts/seed_dev_data.py` dùng `role=UserRole.ENGINEER/PM` — sẽ lỗi sau khi đổi enum, cần sửa lại sau.

## Verification
1. `alembic upgrade head` chạy sạch, `alembic check` không còn drift.
2. `docker exec ... psql -c "\dt"` — xác nhận `support_departments`, `support_requests`, `audit_logs`, `notifications` đã biến mất; `blocker_attachments` xuất hiện.
3. `docker exec ... psql -c "\d knowledge_documents"` — xác nhận cột `knowledge_domain`, `document_category`, `policy_category` đúng, CHECK constraint mới đúng.
4. `docker exec ... psql -c "\d users"` — xác nhận cột `system_role` (không còn `role`), enum chỉ còn ADMIN/HR.
5. `pytest tests/ -v` — 3 test hiện có vẫn pass (không đụng gì tới model User qua API nên không bị ảnh hưởng trực tiếp, nhưng cần chạy để chắc chắn import không vỡ).
