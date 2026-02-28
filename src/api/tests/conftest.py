"""Pytest fixtures for API tests."""

import os
import uuid as uuid_module
from datetime import datetime, timedelta, timezone
import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock

# Set test environment variables before importing app modules
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["ENABLE_PASSWORD_VALIDATION"] = "false"
os.environ["VECTOR_DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["OLLAMA_API_URL"] = "http://localhost:11434"
os.environ["ENCRYPTION_KEY"] = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from src.api.db.base import Base


# SQLite does not support JSONB — compile it as JSON instead.
@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


# Patch PostgreSQL UUID bind_processor so string UUIDs work on SQLite.
# The chat router passes user_id as a plain string from the JWT token,
# which works on PostgreSQL but fails on SQLite because the default
# processor expects a uuid.UUID object with a .hex attribute.
_original_uuid_bind_processor = PG_UUID.bind_processor

def _uuid_bind_processor_sqlite_compat(self, dialect):
    if dialect.name == "sqlite":
        def process(value):
            if value is None:
                return value
            if isinstance(value, uuid_module.UUID):
                return value.hex
            if isinstance(value, str):
                return uuid_module.UUID(value).hex
            return value
        return process
    return _original_uuid_bind_processor(self, dialect)

PG_UUID.bind_processor = _uuid_bind_processor_sqlite_compat


# Remove PostgreSQL partial unique indexes (postgresql_where) from metadata.
# SQLite ignores the WHERE clause and creates a full unique constraint,
# which incorrectly prevents multiple rows with the same value.
_partial_indexes_removed = False

def _strip_partial_unique_indexes():
    global _partial_indexes_removed
    if _partial_indexes_removed:
        return
    for table in Base.metadata.tables.values():
        to_remove = [
            idx for idx in table.indexes
            if idx.unique and idx.dialect_kwargs.get("postgresql_where") is not None
        ]
        for idx in to_remove:
            table.indexes.discard(idx)
    _partial_indexes_removed = True


@pytest_asyncio.fixture
async def test_engine():
    """Create an in-memory SQLite engine for testing."""
    _strip_partial_unique_indexes()
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine):
    """Create a test database session."""
    async_session = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_session):
    """Create an async test client with overridden dependencies."""
    from src.api.main import app
    from src.api.db.session import get_session

    async def override_get_session():
        yield test_session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def mock_env_vars():
    """Fixture to mock environment variables."""
    with patch.dict(os.environ, {
        "JWT_SECRET_KEY": "test-secret-key",
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "JWT_ALGORITHM": "HS256",
        "JWT_EXPIRY": "7",
        "ENABLE_PASSWORD_VALIDATION": "true",
    }):
        yield


# ============================================================
# Shared authentication & permission fixtures
# ============================================================

ALL_PERMISSIONS = {
    "role.view", "role.create", "role.edit", "role.delete",
    "llm.view", "llm.create", "llm.edit", "llm.delete", "llm.test",
    "aiml.view", "aiml.edit",
    "auth.view", "auth.edit",
    "settings.view", "settings.edit", "settings.history",
    "history.view", "history.rollback",
    "chat.view", "chat.create", "chat.edit", "chat.delete",
    "feedback.view", "feedback.create", "feedback.manage",
    "golden_example.view", "golden_example.create", "golden_example.edit", "golden_example.delete",
    "integration.view", "integration.create", "integration.edit", "integration.delete",
    "kb.view", "kb.create", "kb.edit", "kb.delete",
    "kb.upload", "kb.validate", "kb.ingest", "kb.rollback", "kb.version_manage",
    "user.view", "user.create", "user.edit", "user.delete",
    "permission.view", "permission.edit",
    "permission_set.view", "permission_set.create", "permission_set.edit", "permission_set.delete",
    "llm_provider.view", "llm_provider.create", "llm_provider.edit",
    "llm_provider.delete", "llm_provider.test",
    "integration.sync",
}


@pytest_asyncio.fixture
async def admin_client(test_session):
    """Authenticated client with full admin permissions.

    Overrides get_current_user and patches get_user_permissions
    so every require_permission() check passes.

    Yields: (AsyncClient, AsyncSession, UUID)
    """
    from src.api.main import app
    from src.api.db.session import get_session
    from src.api.auth.dependencies import get_current_user

    user_id = uuid_module.uuid4()
    user_payload = {
        "user_id": str(user_id),
        "role": "admin",
        "auth_provider": "local",
        "token_version": "0",
        "jti": str(uuid_module.uuid4()),
        "exp": int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp()),
    }

    async def override_get_current_user():
        return user_payload

    async def override_get_session():
        yield test_session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_get_current_user

    with patch(
        "src.api.auth.dependencies.get_user_permissions",
        new_callable=AsyncMock,
        return_value=ALL_PERMISSIONS,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, test_session, user_id

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def no_perms_client(test_session):
    """Authenticated client with NO permissions.

    The user is authenticated (get_current_user passes) but has
    zero permissions, so every require_permission() check fails with 403.

    Yields: (AsyncClient, AsyncSession, UUID)
    """
    from src.api.main import app
    from src.api.db.session import get_session
    from src.api.auth.dependencies import get_current_user

    user_id = uuid_module.uuid4()
    user_payload = {
        "user_id": str(user_id),
        "role": "user",
        "auth_provider": "local",
        "token_version": "0",
    }

    async def override_get_current_user():
        return user_payload

    async def override_get_session():
        yield test_session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_get_current_user

    with patch(
        "src.api.auth.dependencies.get_user_permissions",
        new_callable=AsyncMock,
        return_value=set(),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, test_session, user_id

    app.dependency_overrides.clear()
