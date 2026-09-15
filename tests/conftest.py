from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import src.model  # noqa: F401 — import để mọi entity được đăng ký vào Base.metadata
from src.config import get_settings
from src.main import app
from src.model.base import Base
from src.model.session import get_db


@pytest.fixture(autouse=True)
def allow_header_user_context():
    """Bật lối tắt `X-User-Id` cho test.

    `Settings.allow_header_user_context` mặc định False (đúng cho production: client tự đặt được
    header này nên nó không có giá trị xác thực, và `validate_production_auth` chặn hẳn khi
    APP_ENV=production). Test gọi API qua ASGITransport nên không có trình duyệt giữ cookie phiên —
    dùng header là cách gọn nhất, và chỉ bật trong phạm vi test.

    `get_settings` có @lru_cache nên sửa thẳng instance đang cache là đủ; khôi phục ở teardown để
    không rò trạng thái sang test khác.
    """
    settings = get_settings()
    original = settings.allow_header_user_context
    original_app_env = settings.app_env
    settings.app_env = "test"
    settings.allow_header_user_context = True
    yield
    settings.allow_header_user_context = original
    settings.app_env = original_app_env


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing API endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session():
    """Database SQLite in-memory dựng lại từ đầu cho mỗi test.

    Dùng SQLite thay PostgreSQL để test nghiệp vụ chạy được trên máy bất kỳ mà không
    cần dựng container. `StaticPool` giữ nguyên một connection duy nhất, nếu không
    mỗi lần checkout sẽ nhận một database rỗng khác.

    Hạn chế cần biết: SQLite không thực thi CHECK constraint đặc thù PostgreSQL và
    không kiểm tra kiểu ENUM ở tầng DB. Vì vậy các test ở đây kiểm tra *logic
    nghiệp vụ trong service*, không phải ràng buộc ở tầng database.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def db_client(db_session):
    """HTTP client dùng chung database in-memory với test, để test tự tạo dữ liệu mẫu."""
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def mock_llm():
    """Mock LLM to avoid calling OpenAI during tests.

    Usage in test:
        def test_something(mock_llm):
            # LLM calls will return mock response instead of hitting OpenAI
            ...
    """
    mock = AsyncMock()
    mock.ainvoke.return_value = AsyncMock(content="Mocked LLM response")
    return mock
