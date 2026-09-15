"""Test PM (Project/ProjectMembership/OnboardingPlan) — đặt NGOÀI thư mục `tests/` có chủ đích:
CI (`.github/workflows/ci.yml`) chạy đúng `pytest tests/`, không quét thư mục này, nên CI không
còn fail vì thiếu Postgres trên self-hosted runner (runner hiện chưa có DB reachable ở
localhost:5433 — xem gốc vấn đề trong `src/config.py`). Chạy tay bằng `pytest PM-test/ -v` khi
có Docker Postgres local (`docker compose up -d db`).

Gộp 2 fixture từ `tests/conftest.py` (client) và `tests/test_api/conftest.py` (test_data) vì
pytest chỉ tự nạp conftest theo cây thư mục cha — thư mục này nằm ngoài `tests/` nên cần định
nghĩa lại đầy đủ ở đây.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, false, or_, select

from src.ai.providers.embeddings_fake import FakeEmbedder
from src.api.dependencies import get_embedder
from src.config import get_settings
from src.main import app
from src.model.blocker import Blocker
from src.model.blocker_attachment import BlockerAttachment
from src.model.document_chunk import DocumentChunk
from src.model.document_version import DocumentVersion
from src.model.knowledge_document import KnowledgeDocument
from src.model.onboarding_plan import OnboardingPlan
from src.model.onboarding_template import OnboardingTemplate
from src.model.plan_task import PlanTask
from src.model.plan_task_citation import PlanTaskCitation
from src.model.plan_task_source import PlanTaskSource
from src.model.project import Project
from src.model.project_github_credential import ProjectGithubCredential
from src.model.project_membership import ProjectMembership
from src.model.session import AsyncSessionLocal
from src.model.task_dependency import TaskDependency
from src.model.template_task import TemplateTask
from src.model.template_version import TemplateVersion
from src.model.user import User


@pytest.fixture(autouse=True)
def allow_header_user_context():
    """Bật lối tắt `X-User-Id` cho toàn bộ test trong thư mục này.

    `Settings.allow_header_user_context` mặc định False (đúng: client tự đặt được header này nên nó
    không có giá trị xác thực ở production, và `validate_production_auth` chặn hẳn khi
    APP_ENV=production). Test ở đây gọi API qua ASGITransport nên không có trình duyệt để giữ cookie
    phiên — dùng header là cách gọn nhất, và chỉ bật trong phạm vi test.

    `get_settings` có @lru_cache nên sửa thẳng instance đang cache là đủ; khôi phục ở teardown để
    không rò trạng thái sang test khác (cùng cách `test_plan_generation.disable_ai_generation` làm).
    """
    settings = get_settings()
    original = settings.allow_header_user_context
    settings.allow_header_user_context = True
    yield
    settings.allow_header_user_context = original


@pytest.fixture(autouse=True)
def fake_embedder_for_tests():
    """Ép embedder giả cho MỌI test trong thư mục này, không phụ thuộc `.env`.

    `.env` đặt `USE_FAKE_EMBEDDER=false` để runtime (và chat/RAG của TV3) dùng BGE-M3 thật — nếu
    không, ingest lưu vector giả còn `get_bge_m3_embedder()` ở `retrieval_engine.py:250` mã hoá câu
    hỏi bằng vector thật, cùng 1024 chiều nên không crash nhưng similarity ra ngẫu nhiên.

    Test thì ngược lại: gọi Modal thật sẽ chậm và phụ thuộc mạng/quota. Override thẳng dependency
    (giống `tests/test_api/test_hr_policy_upload.py` đang làm) để test vẫn nhanh và tất định, đồng
    thời không phải sửa `.env` mỗi lần chạy test.
    """
    app.dependency_overrides[get_embedder] = lambda: FakeEmbedder()
    yield
    app.dependency_overrides.pop(get_embedder, None)


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing API endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class _TestDataTracker:
    def __init__(self) -> None:
        self.project_ids: list[int] = []
        self.user_ids: list[int] = []


@pytest_asyncio.fixture
async def test_data():
    tracker = _TestDataTracker()
    yield tracker

    if not tracker.project_ids and not tracker.user_ids:
        return

    async with AsyncSessionLocal() as db:
        if tracker.project_ids:
            # F2 GitHub credential — 1:1 với Project qua project_id, không phụ thuộc thứ tự với
            # bất kỳ nhánh dọn dẹp nào khác bên dưới, nên xoá sớm là đủ.
            await db.execute(
                delete(ProjectGithubCredential).where(
                    ProjectGithubCredential.project_id.in_(tracker.project_ids)
                )
            )
            # Phase 4: PHẢI dọn Plan ĐẦU TIÊN. PlanTask tham chiếu CẢ hai phía —
            # plan_tasks.plan_id -> onboarding_plans VÀ plan_tasks.template_task_id -> template_tasks
            # nên nếu xoá cây template trước sẽ vướng FK fk_plan_tasks_template_task_id_template_tasks.
            # Thứ tự đúng: plan_task_sources -> plan_tasks -> onboarding_plans -> (cây template).
            membership_ids = list(
                (
                    await db.scalars(
                        select(ProjectMembership.membership_id).where(
                            ProjectMembership.project_id.in_(tracker.project_ids)
                        )
                    )
                ).all()
            )
            # Gom CẢ HAI loại plan: plan của kỹ sư (gắn membership) VÀ lộ trình chuẩn của dự án
            # (membership_id NULL, gắn project_id). Bỏ sót loại thứ 2 là teardown sẽ vướng FK khi
            # xoá template_tasks, vì PlanTask của bản chuẩn vẫn tham chiếu tới chúng.
            plan_ids = list(
                (
                    await db.scalars(
                        select(OnboardingPlan.plan_id).where(
                            or_(
                                OnboardingPlan.membership_id.in_(membership_ids)
                                if membership_ids
                                else false(),
                                OnboardingPlan.project_id.in_(tracker.project_ids),
                            )
                        )
                    )
                ).all()
            )
            if plan_ids:
                plan_task_ids = list(
                    (
                        await db.scalars(
                            select(PlanTask.plan_task_id).where(PlanTask.plan_id.in_(plan_ids))
                        )
                    ).all()
                )
                if plan_task_ids:
                    # Trích dẫn mức đoạn trỏ tới plan_task_sources -> phải xoá TRƯỚC nguồn.
                    await db.execute(
                        delete(PlanTaskCitation).where(
                            PlanTaskCitation.plan_task_id.in_(plan_task_ids)
                        )
                    )
                    await db.execute(
                        delete(PlanTaskSource).where(PlanTaskSource.plan_task_id.in_(plan_task_ids))
                    )
                    # Blocker.plan_task_id -> plan_tasks, không CASCADE -> phải xoá blocker (và file
                    # đính kèm của nó) TRƯỚC khi xoá plan_tasks, nếu không vỡ FK.
                    blocker_ids = list(
                        (
                            await db.scalars(
                                select(Blocker.blocker_id).where(
                                    Blocker.plan_task_id.in_(plan_task_ids)
                                )
                            )
                        ).all()
                    )
                    if blocker_ids:
                        await db.execute(
                            delete(BlockerAttachment).where(
                                BlockerAttachment.blocker_id.in_(blocker_ids)
                            )
                        )
                        await db.execute(delete(Blocker).where(Blocker.blocker_id.in_(blocker_ids)))
                    await db.execute(delete(PlanTask).where(PlanTask.plan_task_id.in_(plan_task_ids)))
                await db.execute(delete(OnboardingPlan).where(OnboardingPlan.plan_id.in_(plan_ids)))

            # Từ Phase 2: mỗi project tự có 1 OnboardingTemplate (fork từ GLOBAL) khi tạo, nên
            # phải dọn hết cây template_id -> version_id -> task_id -> dependency trước khi xoá
            # Project, nếu không sẽ vướng FK (OnboardingTemplate.project_id -> projects.project_id).
            template_ids = list(
                (
                    await db.scalars(
                        select(OnboardingTemplate.template_id).where(
                            OnboardingTemplate.project_id.in_(tracker.project_ids)
                        )
                    )
                ).all()
            )
            if template_ids:
                version_ids = list(
                    (
                        await db.scalars(
                            select(TemplateVersion.version_id).where(TemplateVersion.template_id.in_(template_ids))
                        )
                    ).all()
                )
                if version_ids:
                    task_ids = list(
                        (
                            await db.scalars(
                                select(TemplateTask.template_task_id).where(
                                    TemplateTask.version_id.in_(version_ids)
                                )
                            )
                        ).all()
                    )
                    if task_ids:
                        await db.execute(
                            delete(TaskDependency).where(
                                or_(
                                    TaskDependency.predecessor_task_id.in_(task_ids),
                                    TaskDependency.successor_task_id.in_(task_ids),
                                )
                            )
                        )
                        await db.execute(delete(TemplateTask).where(TemplateTask.template_task_id.in_(task_ids)))
                    await db.execute(delete(TemplateVersion).where(TemplateVersion.version_id.in_(version_ids)))
                await db.execute(delete(OnboardingTemplate).where(OnboardingTemplate.template_id.in_(template_ids)))
            # Phase 3: KnowledgeDocument/DocumentVersion tạo qua repo scanner/upload cũng tham
            # chiếu project_id — phải dọn trước khi xoá Project, nếu không vướng FK.
            document_ids = list(
                (
                    await db.scalars(
                        select(KnowledgeDocument.document_id).where(
                            KnowledgeDocument.project_id.in_(tracker.project_ids)
                        )
                    )
                ).all()
            )
            if document_ids:
                # Từ khi luồng upload dùng chung lõi ingest (`ingest_or_update`), tài liệu PROJECT
                # có DocumentChunk thật — phải xoá chunk trước, nếu không vướng FK
                # fk_document_chunks_version_id_document_versions.
                version_ids_to_delete = list(
                    (
                        await db.scalars(
                            select(DocumentVersion.version_id).where(
                                DocumentVersion.document_id.in_(document_ids)
                            )
                        )
                    ).all()
                )
                if version_ids_to_delete:
                    await db.execute(
                        delete(DocumentChunk).where(DocumentChunk.version_id.in_(version_ids_to_delete))
                    )
                await db.execute(delete(DocumentVersion).where(DocumentVersion.document_id.in_(document_ids)))
                await db.execute(delete(KnowledgeDocument).where(KnowledgeDocument.document_id.in_(document_ids)))
            await db.execute(delete(ProjectMembership).where(ProjectMembership.project_id.in_(tracker.project_ids)))
        if tracker.user_ids:
            await db.execute(delete(ProjectMembership).where(ProjectMembership.user_id.in_(tracker.user_ids)))
        if tracker.project_ids:
            await db.execute(delete(Project).where(Project.project_id.in_(tracker.project_ids)))
        if tracker.user_ids:
            await db.execute(delete(User).where(User.user_id.in_(tracker.user_ids)))
        await db.commit()


@pytest_asyncio.fixture
async def admin_id(test_data) -> int:
    """Admin riêng cho mỗi test, không phụ thuộc ID hoặc dữ liệu seed của môi trường.

    Tạo thẳng qua DB, KHÔNG qua `POST /api/v1/users` — router đó giờ tự nó đã bắt buộc người gọi
    phải là admin (`require_admin`), nên gọi qua API sẽ luôn 401 (con gà quả trứng: cần admin để
    tạo admin). `tests/test_api/conftest.py::admin_id` gặp đúng lỗi này nhưng chưa lộ vì hiện chưa
    có test nào trong `tests/` thật sự gọi tới nó."""
    async with AsyncSessionLocal() as db:
        user = User(
            email=f"test-admin-{uuid.uuid4().hex[:8]}@onboarding.dev",
            display_name="Test Admin",
            system_role="ADMIN",
            status="ACTIVE",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        user_id = user.user_id
    test_data.user_ids.append(user_id)
    return user_id
