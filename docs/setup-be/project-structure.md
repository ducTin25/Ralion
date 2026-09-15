# Kiến trúc thư mục dự án — Project Onboarding Buddy (BO-06)

> Mô tả cấu trúc thư mục hiện tại của repo, mỗi thư mục/file dùng để làm gì. Cập nhật khi cấu trúc thay đổi.

## Sơ đồ tổng quan

```
P-040/
├── src/                    # Toàn bộ source code backend (FastAPI)
│   ├── main.py               # Entry point FastAPI app
│   ├── config.py              # Settings đọc từ .env (pydantic-settings)
│   ├── model/                 # Entity SQLAlchemy — map thẳng xuống bảng Postgres
│   ├── dto/                   # Pydantic DTO — hình dạng JSON request/response của API
│   │   ├── request/
│   │   └── response/
│   ├── api/                   # FastAPI router (controller)
│   ├── agents/                 # LangGraph agent (state, node, tool)
│   └── services/                # Service gọi ra ngoài (LLM...)
├── alembic/                # Migration Alembic (versioned schema history)
├── scripts/                # Script tiện ích chạy tay (seed data, logging hook...)
├── tests/                   # Test, mirror cấu trúc src/
├── docs/                    # Tài liệu dự án
├── docker-compose.yml       # Định nghĩa service backend + db (Postgres) chạy local
├── Dockerfile                # Build image cho service backend
├── requirements.txt          # Dependency Python (production)
├── requirements-dev.txt       # Dependency chỉ dùng khi dev (lint, test...)
├── alembic.ini                # Config Alembic (trỏ vào alembic/env.py)
├── .env / .env.example         # Biến môi trường (DB, API key...)
└── render.yaml                # Cấu hình deploy lên Render
```

## `src/` — chi tiết

### `src/main.py`
Entry point FastAPI. Tạo `app = FastAPI(...)`, gắn CORS middleware, include router từ `src/api/routes.py` với prefix `/api/v1`, định nghĩa `/health`.

### `src/config.py`
Class `Settings` (pydantic-settings) đọc từ file `.env` — chứa `database_url`, `openai_api_key`, `chroma_persist_dir`, `cors_origins`... Có hàm `get_settings()` cache bằng `@lru_cache` để không đọc lại `.env` mỗi lần gọi.

### `src/model/` — Entity SQLAlchemy (tương đương `@Entity` trong JPA/Spring Boot)
Mỗi file = 1 bảng trong Postgres, đúng 1-class-1-file. Đây là nơi định nghĩa **cấu trúc dữ liệu lưu trữ**, không liên quan tới hình dạng JSON trả ra API.

| File | Bảng | Nhóm domain |
|---|---|---|
| `base.py` | — | `DeclarativeBase` dùng chung + naming convention cho constraint (PK/FK/UNIQUE/CHECK) |
| `session.py` | — | Async engine, `async_sessionmaker`, hàm `get_db()` (FastAPI dependency inject session) |
| `enums.py` | — | 25 enum Python dùng chung cho toàn bộ entity (UserRole, TaskStatus, TicketPriority...) |
| `user.py` | `users` | Identity & Access |
| `project.py` | `projects` | Identity & Access |
| `project_membership.py` | `project_memberships` | Identity & Access |
| `knowledge_document.py` | `knowledge_documents` | Project Knowledge |
| `document_version.py` | `document_versions` | Project Knowledge |
| `document_chunk.py` | `document_chunks` | Project Knowledge |
| `onboarding_template.py` | `onboarding_templates` | Template & Plan |
| `template_version.py` | `template_versions` | Template & Plan |
| `template_task.py` | `template_tasks` | Template & Plan |
| `task_dependency.py` | `task_dependencies` | Template & Plan |
| `onboarding_plan.py` | `onboarding_plans` | Template & Plan |
| `plan_task.py` | `plan_tasks` | Template & Plan |
| `plan_task_source.py` | `plan_task_sources` | Template & Plan |
| `chat_session.py` | `chat_sessions` | RAG & Support |
| `chat_message.py` | `chat_messages` | RAG & Support |
| `citation.py` | `citations` | RAG & Support |
| `blocker.py` | `blockers` | RAG & Support |
| `support_department.py` | `support_departments` | RAG & Support |
| `support_request.py` | `support_requests` | RAG & Support |
| `audit_log.py` | `audit_logs` | Cross-cutting |
| `notification.py` | `notifications` | Cross-cutting |

**Lưu ý**: hiện các entity mới dùng `ForeignKey` cột thô, **chưa khai báo `relationship()`/`back_populates`** — join hiện phải viết tay bằng query. Sẽ bổ sung khi cần (đã trao đổi, chưa quyết định thời điểm làm).

### `src/dto/` — DTO (Data Transfer Object), tương đương layer DTO trong Spring Boot
Định nghĩa hình dạng JSON đi vào/ra khỏi API — **khác hoàn toàn** với `src/model/` (entity DB). Một entity có thể có nhiều DTO khác nhau (ví dụ `UserResponseDTO` không trả `password_hash`, trong khi entity `User` có thể có field đó).

- `request/` — DTO cho dữ liệu client gửi lên (`ChatRequestDTO`...).
- `response/` — DTO cho dữ liệu server trả về (`ChatResponseDTO`...).

Hiện chỉ có 2 DTO cho endpoint `/chat` cũ. Khi làm CRUD cho 21 entity (chưa làm) sẽ có thêm DTO tương ứng, ví dụ `request/user_request_dto.py`, `response/user_response_dto.py`.

### `src/api/` — Router (Controller)
- `routes.py`: router hiện tại, có `POST /chat` và `GET /status` (demo LangGraph từ template gốc, chưa liên quan tới 21 entity).
- **Chưa có**: router CRUD cho entity (`User`, `Project`...). Khi làm, dự kiến thêm `src/api/controller/` — mỗi entity 1 file (`user_controller.py`...), gộp lại và mount vào `main.py`, giống mỗi `@RestController` trong Spring Boot ứng với 1 resource.

### `src/agents/` — LangGraph agent
- `graph.py`: dựng `StateGraph` (`analyze` → `respond`), export `agent` đã compile.
- `state.py`: định nghĩa `AgentState` (kiểu dữ liệu state truyền qua các node).
- `nodes/`: các node xử lý trong graph (hiện là `example_node.py`, đặt tên tạm/demo).
- `tools/`: tool mà agent có thể gọi (hiện là `example_tool.py`, demo).

Toàn bộ thư mục này vẫn là code mẫu từ template, **chưa customize** cho domain onboarding thật (chưa có node RAG, node tạo plan, tool gọi API tạo task...).

### `src/services/`
- `llm.py`: hàm `get_llm()` khởi tạo `ChatOpenAI` từ config (model, temperature, api key).

## `alembic/` — Migration
- `env.py`: wire vào `settings.database_url` + import `src.model` để `Base.metadata` có đủ 21 entity trước khi autogenerate.
- `versions/`: lịch sử migration theo thứ tự thời gian:
  1. `2fb68a7d5469_create_users_table.py` — tạo bảng `users` (proof of concept ban đầu).
  2. `9fbecdaefe53_add_remaining_20_entities.py` — tạo 20 bảng còn lại.
  3. `092eacb97740_fix_check_constraint_names_and_add_.py` — fix tên CHECK constraint bị lặp prefix + thêm FK vòng lặp `projects.primary_pm_membership_id` (bị sót ở migration #2).

## `scripts/`
- `seed_dev_data.py`: insert 4 user mẫu (ADMIN/PM/ENGINEER/HR) để test thủ công qua pgAdmin/psql.
- `log_hook.py`, `log_manual.py`, `log_antigravity.py`, `submit_log.py`: script phục vụ AI usage-logging của khoá học (không liên quan tới domain logic của app).

## `tests/`
Mirror cấu trúc `src/`: `tests/test_agents/`, `tests/test_api/`. Hiện chỉ test các endpoint demo (`/chat`, `/status`, `/health`) — **chưa có `tests/test_model/`** để test entity/constraint/migration (việc còn tồn đọng, đã ghi trong báo cáo trước).

## `docs/`
- `setup-be/`: tài liệu backend do quá trình làm việc này tạo ra — plan, báo cáo, hướng dẫn (file bạn đang đọc nằm ở đây).
- Các file khác (`guide/`, `architecture/`...): tài liệu chung của template cohort, phần lớn còn ở dạng placeholder.

## File cấu hình ở gốc repo
| File | Vai trò |
|---|---|
| `docker-compose.yml` | Service `db` (Postgres 16, cổng 5433) + `backend` (FastAPI) |
| `Dockerfile` | Build image cho `backend` |
| `requirements.txt` | Dependency chạy app (FastAPI, SQLAlchemy, Alembic, LangChain...) |
| `requirements-dev.txt` | Dependency chỉ dev (ruff, pytest...) |
| `alembic.ini` | Trỏ Alembic tới `alembic/env.py` |
| `.env` / `.env.example` | Biến môi trường thật / mẫu |
| `ruff.toml` | Config linter |
| `render.yaml` | Cấu hình deploy Render |
| `Makefile` | Lệnh tắt (`make test`, `make run`...) |

## Việc còn tồn đọng (chưa làm, ngoài phạm vi hiện tại)
- `src/api/controller/` — router CRUD cho 21 entity.
- `relationship()`/`back_populates` trên entity.
- `tests/test_model/` — test constraint, migration round-trip.
- Node/tool LangGraph thật cho RAG, tạo plan, blocker routing (hiện vẫn là code demo).
- Postgres service container trong CI (`.github/workflows/ci.yml`).
