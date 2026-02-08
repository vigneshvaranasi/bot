"""Tests for settings endpoint authorization."""

import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from uuid import uuid4

from src.api.core.jwt import create_access_token


class TestSettingsAuthorization:
    """Tests for settings endpoint authorization - verifying non-admin users get 403."""

    @pytest_asyncio.fixture
    async def regular_user_payload(self):
        """Create a regular user payload for mocking."""
        return {
            "user_id": str(uuid4()),
            "role": "user",  # Regular user, NOT admin
            "auth_provider": "local",
            "token_version": "1"
        }

    @pytest_asyncio.fixture
    async def mock_client_with_user(self, regular_user_payload):
        """Create a mock client with regular (non-admin) user."""
        from src.api.main import app
        from src.api.db.session import get_session
        from src.api.auth.dependencies import get_current_user

        # Mock the database session
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalars = lambda: MagicMock(first=lambda: None, all=lambda: [])
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def override_get_session():
            yield mock_session

        # Override get_current_user to return a regular user (not admin)
        async def override_get_current_user():
            return regular_user_payload

        app.dependency_overrides[get_session] = override_get_session
        app.dependency_overrides[get_current_user] = override_get_current_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_setting_requires_admin(self, mock_client_with_user):
        """Test that creating settings requires admin role."""
        response = await mock_client_with_user.post(
            "/settings/",
            json={
                "deny_words": "test",
                "model": "gpt-4",
                "temperature": 0.7,
                "langfuse_enabled": False,
                "auth_google_enabled": True,
                "auth_github_enabled": True,
                "auth_microsoft_enabled": True,
                "auth_local_enabled": True
            }
        )
        assert response.status_code == 403
        assert "Missing role: admin" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_latest_setting_requires_admin(self, mock_client_with_user):
        """Test that getting latest setting requires admin role."""
        response = await mock_client_with_user.get("/settings/")
        assert response.status_code == 403
        assert "Missing role: admin" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_settings_requires_admin(self, mock_client_with_user):
        """Test that listing all settings requires admin role."""
        response = await mock_client_with_user.get("/settings/all")
        assert response.status_code == 403
        assert "Missing role: admin" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_last_setting_requires_admin(self, mock_client_with_user):
        """Test that getting last setting requires admin role."""
        response = await mock_client_with_user.get("/settings/last")
        assert response.status_code == 403
        assert "Missing role: admin" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_rollback_setting_requires_admin(self, mock_client_with_user):
        """Test that rollback settings requires admin role."""
        response = await mock_client_with_user.put("/settings/rollback")
        assert response.status_code == 403
        assert "Missing role: admin" in response.json()["detail"]

    # ============================================================
    # Segment-based endpoint tests
    # ============================================================

    @pytest.mark.asyncio
    async def test_get_aiml_segment_requires_admin(self, mock_client_with_user):
        """Test that getting AI/ML segment settings requires admin role."""
        response = await mock_client_with_user.get("/settings/segment/aiml")
        assert response.status_code == 403
        assert "Missing role: admin" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_auth_segment_requires_admin(self, mock_client_with_user):
        """Test that getting auth segment settings requires admin role."""
        response = await mock_client_with_user.get("/settings/segment/auth")
        assert response.status_code == 403
        assert "Missing role: admin" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_aiml_segment_requires_admin(self, mock_client_with_user):
        """Test that updating AI/ML segment settings requires admin role."""
        response = await mock_client_with_user.put(
            "/settings/segment/aiml",
            json={"model": "gemma3:4b", "temperature": "0.5"}
        )
        assert response.status_code == 403
        assert "Missing role: admin" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_auth_segment_requires_admin(self, mock_client_with_user):
        """Test that updating auth segment settings requires admin role."""
        response = await mock_client_with_user.put(
            "/settings/segment/auth",
            json={"auth_google_enabled": True}
        )
        assert response.status_code == 403
        assert "Missing role: admin" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_history_requires_admin(self, mock_client_with_user):
        """Test that getting settings history requires admin role."""
        response = await mock_client_with_user.get("/settings/history")
        assert response.status_code == 403
        assert "Missing role: admin" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_rollback_to_version_requires_admin(self, mock_client_with_user):
        """Test that rollback to specific version requires admin role."""
        response = await mock_client_with_user.post(f"/settings/rollback/{uuid4()}")
        assert response.status_code == 403
        assert "Missing role: admin" in response.json()["detail"]


class TestSettingsUnauthenticated:
    """Tests for unauthenticated access to settings endpoints."""

    @pytest_asyncio.fixture
    async def mock_client(self):
        """Create a mock client without authentication override."""
        from src.api.main import app
        from src.api.db.session import get_session

        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalars = lambda: MagicMock(first=lambda: None, all=lambda: [])
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def override_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_get_session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_unauthenticated_request_rejected(self, mock_client):
        """Test that unauthenticated requests are rejected."""
        response = await mock_client.get("/settings/")
        assert response.status_code == 403  # No Authorization header


class TestSettingsAdminAccess:
    """Tests for admin access to settings endpoints."""

    @pytest_asyncio.fixture
    async def admin_user_payload(self):
        """Create admin user payload for mocking."""
        return {
            "user_id": str(uuid4()),
            "role": "admin",
            "auth_provider": "local",
            "token_version": "1"
        }

    @pytest_asyncio.fixture
    async def mock_client_with_admin(self, admin_user_payload):
        """Create a mock client with admin user."""
        from src.api.main import app
        from src.api.db.session import get_session
        from src.api.auth.dependencies import get_current_user

        # Mock the database session
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalars = lambda: MagicMock(first=lambda: None, all=lambda: [])
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def override_get_session():
            yield mock_session

        # Override get_current_user to return an admin user
        async def override_get_current_user():
            return admin_user_payload

        app.dependency_overrides[get_session] = override_get_session
        app.dependency_overrides[get_current_user] = override_get_current_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_admin_can_access_settings_list(self, mock_client_with_admin):
        """Test that admin can access settings list."""
        response = await mock_client_with_admin.get("/settings/all")
        # Should not get 403 - admin has access
        assert response.status_code != 403

    @pytest.mark.asyncio
    async def test_admin_can_access_aiml_segment(self, mock_client_with_admin):
        """Test that admin can access AI/ML segment settings."""
        response = await mock_client_with_admin.get("/settings/segment/aiml")
        # Should not get 403 - admin has access
        assert response.status_code != 403

    @pytest.mark.asyncio
    async def test_admin_can_access_auth_segment(self, mock_client_with_admin):
        """Test that admin can access auth segment settings."""
        response = await mock_client_with_admin.get("/settings/segment/auth")
        # Should not get 403 - admin has access
        assert response.status_code != 403

    @pytest.mark.asyncio
    async def test_admin_can_access_history(self, mock_client_with_admin):
        """Test that admin can access settings history."""
        response = await mock_client_with_admin.get("/settings/history")
        # Should not get 403 - admin has access
        assert response.status_code != 403
