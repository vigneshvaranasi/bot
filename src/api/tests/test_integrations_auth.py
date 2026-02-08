"""Tests for integrations endpoint authorization and credential masking."""

import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from uuid import uuid4
from datetime import datetime, timezone

from src.api.core.jwt import create_access_token
from src.api.routers.integrations import mask_sensitive_config, mask_integration_response


class TestIntegrationAuthorization:
    """Tests for integration endpoint authorization - verifying non-admin users get 403."""

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
    async def test_get_all_integrations_requires_admin(self, mock_client_with_user):
        """Test that getting all integrations requires admin role."""
        response = await mock_client_with_user.get("/integrations/all")
        assert response.status_code == 403
        assert "Missing role: admin" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_integration_by_id_requires_admin(self, mock_client_with_user):
        """Test that getting integration by ID requires admin role."""
        response = await mock_client_with_user.get(f"/integrations/id/{uuid4()}")
        assert response.status_code == 403
        assert "Missing role: admin" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_integration_requires_admin(self, mock_client_with_user):
        """Test that creating integration requires admin role."""
        response = await mock_client_with_user.post(
            "/integrations/create",
            json={
                "service_name": "servicenow",
                "auth_type": "basic_auth",
                "config": {"url": "https://example.com", "username": "test", "password": "secret"},
                "is_active": True,
                "status": "success"
            }
        )
        assert response.status_code == 403
        assert "Missing role: admin" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_integration_requires_admin(self, mock_client_with_user):
        """Test that deleting integration requires admin role."""
        response = await mock_client_with_user.delete(f"/integrations/delete/{uuid4()}")
        assert response.status_code == 403
        assert "Missing role: admin" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_integration_requires_admin(self, mock_client_with_user):
        """Test that updating integration requires admin role."""
        response = await mock_client_with_user.put(
            f"/integrations/update/{uuid4()}",
            json={
                "service_name": "servicenow",
                "auth_type": "basic_auth",
                "config": {},
                "is_active": True
            }
        )
        assert response.status_code == 403
        assert "Missing role: admin" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_sync_integration_requires_admin(self, mock_client_with_user):
        """Test that syncing integration requires admin role."""
        response = await mock_client_with_user.post(f"/integrations/sync/{uuid4()}")
        assert response.status_code == 403
        assert "Missing role: admin" in response.json()["detail"]


class TestIntegrationUnauthenticated:
    """Tests for unauthenticated access to integration endpoints."""

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
        response = await mock_client.get("/integrations/all")
        assert response.status_code == 403  # No Authorization header


class TestCredentialMasking:
    """Tests for credential masking in integration responses."""

    def test_mask_sensitive_config_masks_password(self):
        """Test that password field is masked."""
        config = {
            "url": "https://example.com",
            "username": "admin",
            "password": "supersecret123"
        }
        masked = mask_sensitive_config(config)

        assert masked["url"] == "https://example.com"
        assert masked["username"] == "admin"
        assert masked["password"] == "********"

    def test_mask_sensitive_config_masks_api_key(self):
        """Test that api_key field is masked."""
        config = {
            "url": "https://api.example.com",
            "api_key": "sk-12345abcde"
        }
        masked = mask_sensitive_config(config)

        assert masked["url"] == "https://api.example.com"
        assert masked["api_key"] == "********"

    def test_mask_sensitive_config_masks_token(self):
        """Test that token fields are masked."""
        config = {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "refresh_token": "dGhpc2lzYXJlZnJlc2h0b2tlbg==",
            "token": "bearer-token-123"
        }
        masked = mask_sensitive_config(config)

        assert masked["access_token"] == "********"
        assert masked["refresh_token"] == "********"
        assert masked["token"] == "********"

    def test_mask_sensitive_config_masks_secret(self):
        """Test that secret fields are masked."""
        config = {
            "client_secret": "secret123",
            "api_secret": "apiSecret456"
        }
        masked = mask_sensitive_config(config)

        assert masked["client_secret"] == "********"
        assert masked["api_secret"] == "********"

    def test_mask_sensitive_config_preserves_non_sensitive(self):
        """Test that non-sensitive fields are preserved."""
        config = {
            "url": "https://example.com",
            "username": "admin",
            "port": 443,
            "enabled": True,
            "timeout": 30
        }
        masked = mask_sensitive_config(config)

        assert masked["url"] == "https://example.com"
        assert masked["username"] == "admin"
        assert masked["port"] == 443
        assert masked["enabled"] is True
        assert masked["timeout"] == 30

    def test_mask_sensitive_config_handles_empty(self):
        """Test that empty config is handled."""
        assert mask_sensitive_config({}) == {}
        assert mask_sensitive_config(None) is None

    def test_mask_sensitive_config_case_insensitive(self):
        """Test that field name matching is case-insensitive."""
        config = {
            "PASSWORD": "secret1",
            "Api_Key": "secret2",
            "TOKEN": "secret3"
        }
        masked = mask_sensitive_config(config)

        assert masked["PASSWORD"] == "********"
        assert masked["Api_Key"] == "********"
        assert masked["TOKEN"] == "********"

    def test_mask_integration_response(self):
        """Test that mask_integration_response creates properly masked response."""
        # Create a mock integration object
        mock_integration = MagicMock()
        mock_integration.id = uuid4()
        mock_integration.service_name = "servicenow"
        mock_integration.auth_type = "basic_auth"
        mock_integration.config = {
            "url": "https://company.service-now.com",
            "username": "admin",
            "password": "supersecret"
        }
        mock_integration.is_active = True
        mock_integration.last_synced_at = datetime.now(timezone.utc)
        mock_integration.last_sync_status = "success"
        mock_integration.last_sync_error = None
        mock_integration.updated_at = datetime.now(timezone.utc)
        mock_integration.user_id = uuid4()

        masked = mask_integration_response(mock_integration)

        assert masked["service_name"] == "servicenow"
        assert masked["config"]["url"] == "https://company.service-now.com"
        assert masked["config"]["username"] == "admin"
        assert masked["config"]["password"] == "********"  # Should be masked
        assert masked["is_active"] is True


class TestIntegrationAdminAccess:
    """Tests for admin access to integration endpoints."""

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
    async def test_admin_can_access_integrations_list(self, mock_client_with_admin):
        """Test that admin can access integrations list."""
        response = await mock_client_with_admin.get("/integrations/all")
        # Should not get 403 - admin has access
        assert response.status_code != 403
