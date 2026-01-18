"""Pytest fixtures for API tests."""

import os
import pytest
import pytest_asyncio
from unittest.mock import patch

# Set test environment variables before importing app modules
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["ENABLE_PASSWORD_VALIDATION"] = "false"
os.environ["VECTOR_DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["OLLAMA_API_URL"] = "http://localhost:11434"

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from src.api.db.base import Base


@pytest_asyncio.fixture
async def test_engine():
    """Create an in-memory SQLite engine for testing."""
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
