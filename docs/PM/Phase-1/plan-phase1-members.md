# Plan chi tiết — Phase 1: Thành viên & Add Member Wizard

> Thuộc [plan-frontend-pm.md](plan-frontend-pm.md) — Phase 1/7. Trạng thái: **đang triển khai**.

## Mục tiêu
Sau Phase 1: PM có thể — xem danh sách project mình quản lý, xem danh sách thành viên trong 1 project, thêm thành viên mới (chọn user có sẵn + gán project role) — chạy thật trên DB thật, có test tự động, có bằng chứng (test pass + server chạy được).

## 1. Backend

### 1.1 Model (đã cập nhật sau khi merge `develop`)
`Project` và `ProjectMembership` đúng spec, không cần sửa model/migration cho phần CRUD cơ bản của phase này. **Cập nhật 12/08/2026**: teammate merge nhánh `develop` thêm 2 field mới vào `Project` (`sync_status`, `last_synced_at`) + **3 database trigger ép buộc bất biến kiến trúc** (migration `a1b2c3d4e5f6_add_sync_fields_and_schema_invariants.py`) — quan trọng nhất với Phase 1:

> **INV1**: user có `system_role IS NOT NULL` (ADMIN/HR) **không được phép** có bất kỳ `ProjectMembership` nào, và ngược lại — ép buộc bằng trigger ở cả 2 chiều (`INSERT/UPDATE` trên `project_memberships`, và `UPDATE system_role` trên `users`). Vi phạm → Postgres raise exception ngay, không phải lỗi validate ở tầng service.

⚠️ Ảnh hưởng trực tiếp: test ban đầu dùng `user_id=19` (admin) để tạo membership test **sẽ vỡ** sau khi trigger có hiệu lực — đã sửa lại dùng user tạo riêng (`system_role=NULL`) cho từng test, xem mục 2.

Chốt lại field dùng:
- `Project`: `project_id, key, name, primary_pm_membership_id, created_by_admin_id, status(ACTIVE|ARCHIVED), sync_status(NOT_STARTED|SYNCING|SUCCESS|PARTIAL|FAILED), last_synced_at, created_at`
- `ProjectMembership`: `membership_id, user_id, project_id, project_role(PM|ENGINEER), status(ACTIVE|INACTIVE), assigned_by_admin_id, joined_at`, UNIQUE(user_id, project_id) — **+ ràng buộc INV1 ở trên**

### 1.2 DTO — `src/dto/request/project_request_dto.py`
```python
class ProjectCreateRequestDTO(BaseModel):
    key: str = Field(..., min_length=2)
    name: str = Field(..., min_length=1)
    created_by_admin_id: int

class ProjectUpdateRequestDTO(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    status: ProjectStatus | None = None
```

### 1.3 DTO — `src/dto/response/project_response_dto.py`
```python
class ProjectResponseDTO(BaseModel):
    project_id: int
    key: str
    name: str
    primary_pm_membership_id: int | None
    created_by_admin_id: int
    status: ProjectStatus
    sync_status: SyncStatus          # mới, từ nhánh develop (NOT_STARTED|SYNCING|SUCCESS|PARTIAL|FAILED)
    last_synced_at: datetime | None  # mới, từ nhánh develop
    created_at: datetime

    @classmethod
    def from_entity(cls, project: Project) -> "ProjectResponseDTO": ...
```

### 1.4 DTO — `src/dto/request/project_membership_request_dto.py`
```python
class ProjectMembershipCreateRequestDTO(BaseModel):
    user_id: int
    project_id: int
    project_role: ProjectRole
    assigned_by_admin_id: int

class ProjectMembershipUpdateRequestDTO(BaseModel):
    project_role: ProjectRole | None = None
    status: MembershipStatus | None = None
```

### 1.5 DTO — `src/dto/response/project_membership_response_dto.py`
```python
class ProjectMembershipResponseDTO(BaseModel):
    membership_id: int
    user_id: int
    project_id: int
    project_role: ProjectRole
    status: MembershipStatus
    assigned_by_admin_id: int
    joined_at: datetime

    @classmethod
    def from_entity(cls, m: ProjectMembership) -> "ProjectMembershipResponseDTO": ...
```

### 1.6 Service — `src/services/project_service.py`
Theo đúng pattern `user_service.py`: `create_project`, `get_project`, `list_projects(limit, offset)`, `update_project`, `archive_project` (soft-delete: `status=ARCHIVED`).

### 1.7 Service — `src/services/project_membership_service.py`
`create_membership`, `get_membership`, `list_memberships_by_project(project_id, limit, offset)`, `update_membership`, `deactivate_membership` (soft-delete: `status=INACTIVE`).

### 1.8 Router — `src/api/routers/project_router.py`
`POST /projects`, `GET /projects`, `GET /projects/{project_id}`, `PATCH /projects/{project_id}`, `DELETE /projects/{project_id}` (soft, trả về project với status=ARCHIVED). `key` trùng → bắt `IntegrityError` → 409.

### 1.9 Router — `src/api/routers/project_membership_router.py`
`POST /project-memberships`, `GET /project-memberships?project_id=`, `GET /project-memberships/{membership_id}`, `PATCH /project-memberships/{membership_id}`, `DELETE /project-memberships/{membership_id}` (soft). UNIQUE(user_id, project_id) trùng → bắt `IntegrityError` → 409 ("User đã là thành viên project này").

### 1.10 Đăng ký router
Thêm `project_router`, `project_membership_router` vào `src/api/routers/__init__.py` (hiện chỉ có `user_router`).

## 2. Backend — Test (`tests/test_api/test_projects.py`, `tests/test_api/test_project_memberships.py`)

Dùng đúng fixture `client` có sẵn trong `tests/conftest.py` (chạy qua ASGITransport, nối DB thật đang chạy trong Docker — không mock DB, giống cách test User hiện tại đã xác nhận hoạt động).

**`test_projects.py`**:
1. `test_create_project` — POST tạo project mới với `key` ngẫu nhiên (tránh đụng seed data) → 201, đúng field trả về.
2. `test_create_project_duplicate_key` — tạo lại đúng `key` vừa tạo → 409.
3. `test_list_projects` — GET list → 200, trả về mảng có ít nhất project vừa tạo.
4. `test_get_project_not_found` — GET `/projects/999999` → 404.
5. `test_update_project` — PATCH đổi `name` → 200, đúng giá trị mới.
6. `test_archive_project` — DELETE → 200, `status == "ARCHIVED"`.

**`test_project_memberships.py`** (⚠️ sau INV1, **không được dùng user có `system_role`** — ví dụ `admin`/`hr` seed — làm `user_id` cho membership, Postgres sẽ raise exception. Test tự tạo 1 user mới (`system_role=None`) qua `POST /api/v1/users` cho mỗi test, dọn qua fixture `cleanup_users`):
1. `test_create_membership` — POST tạo membership (user tự tạo, `system_role=None` + project tự tạo) → 201.
2. `test_create_membership_duplicate` — tạo lại đúng `(user_id, project_id)` → 409.
3. `test_list_memberships_by_project` — GET `?project_id=` → 200, chứa membership vừa tạo.
4. `test_update_membership_role` — PATCH đổi `project_role` → 200.
5. `test_deactivate_membership` — DELETE → 200, `status == "INACTIVE"`.

**Dọn dẹp data test**: `tests/test_api/conftest.py` có 2 fixture `cleanup_projects`/`cleanup_users` — hard-delete thật (không phải soft-delete như app) các row test tự tạo sau khi test xong, tránh tích rác `TEST*` trong DB thật qua nhiều lần chạy (bài học từ lần chạy đầu: 47 project rác `TEST*` bị bỏ lại trong DB do chưa có cleanup).

## 3. Frontend

### 3.1 DTO — `frontend/src/dto/requestDTO/projectMembership.request.ts`
```typescript
export type CreateProjectMembershipRequestDTO = {
  user_id: number;
  project_id: number;
  project_role: "PM" | "ENGINEER";
  assigned_by_admin_id: number;
};
```

### 3.2 DTO — `frontend/src/dto/responseDTO/project.response.ts` + `projectMembership.response.ts`
Khớp 1:1 field với `ProjectResponseDTO`/`ProjectMembershipResponseDTO` phía backend (snake_case, xem mục 1.3/1.5).

### 3.3 API client — mở rộng `frontend/src/lib/api.ts`
Thêm hằng `PROJECTS_ENDPOINT`, `PROJECT_MEMBERSHIPS_ENDPOINT` theo đúng pattern `CHAT_ENDPOINT` đã có.

### 3.4 UI — `frontend/src/app/product-manager/`
Thay nội dung placeholder hiện tại bằng 3 màn hình thật (route con hoặc tab trong 1 page, đơn giản hoá cho Phase 1 — chưa cần Access Scope/wizard 3 bước theo đúng quyết định đã ghi trong plan tổng: bỏ Access Scope vì backend chưa có entity):
- `owner-projects`: bảng danh sách project (key, name, status) + nút "Tạo project".
- `owner-members`: chọn 1 project → bảng thành viên (email/tên user, role, status) + nút "Thêm thành viên".
- `owner-addmember`: form đơn giản (chọn `user_id` có sẵn qua dropdown gọi `/api/v1/users`, chọn `project_role`) — **bỏ bước Access Scope** so với mockup gốc (lý do: chưa có entity backend, đã quyết định ở plan tổng).

Component đặt tại `frontend/src/features/project-management/components/` (feature mới, theo đúng convention nêu trong `frontend/README.md`: tổ chức theo feature, không theo role).

## 4. Definition of Done (bằng chứng bắt buộc trước khi báo hoàn thành)
1. `pytest tests/ -v` — toàn bộ test cũ + mới đều pass, dán output đầy đủ.
2. `alembic check` — sạch, xác nhận không đổi model nên không có drift.
3. `cd frontend && npx tsc --noEmit` — sạch.
4. Chạy `docker compose up -d --build` (backend) — gọi thử `curl` thật vào `/api/v1/projects` và `/api/v1/project-memberships`, dán response thật.
5. Chạy `npm run dev` (frontend) tại `frontend/` — xác nhận server lên cổng 3000, đưa URL để bạn tự mở trình duyệt xem trực tiếp `/product-manager`.

## Ngoài phạm vi Phase 1
- Access Scope/ACL (đã quyết định hoãn ở plan tổng).
- Trang `owner-projects` chọn project đang active lưu vào state toàn cục (context/store) — Phase 1 dùng state cục bộ đơn giản, có thể nâng cấp khi làm Phase 4+ cần share project đang chọn giữa nhiều trang.
