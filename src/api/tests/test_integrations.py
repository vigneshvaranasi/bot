"""Comprehensive tests for Integrations endpoints (/integrations).

Covers:
- List integrations (GET /integrations/all)
- Get integration by ID (GET /integrations/id/{id})
- Create integration (POST /integrations/create)
- Update integration (PUT /integrations/update/{id})
- Delete integration (DELETE /integrations/delete/{id})
- Credential masking in responses
- Permission/RBAC enforcement
- Unauthenticated access

Note: POST /integrations/sync/{id} is an SSE streaming endpoint that
calls external ServiceNow APIs, so it is not tested here.
"""

import pytest
from uuid import uuid4
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone

from sqlalchemy.future import select

from src.api.db.models import Integration


# ============================================================
# Helpers
# ============================================================

def _make_integration(user_id, *, service_name="servicenow", **kw):
    """Build an Integration ORM instance."""
    defaults = dict(
        service_name=service_name,
        auth_type="basic_auth",
        config={"url": "https://example.service-now.com", "username": "admin", "password": "secret123"},
        is_active=True,
        user_id=user_id,
    )
    defaults.update(kw)
    return Integration(**defaults)


# ============================================================
# GET /integrations/all — List integrations
# ============================================================


class TestListIntegrations:
    """Tests for GET /integrations/all"""

    @pytest.mark.asyncio
    async def test_list_integrations_empty(self, admin_client):
        """Returns empty list when no integrations exist."""
        client, _, _ = admin_client
        response = await client.get("/integrations/all")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["integrations"] == []

    @pytest.mark.asyncio
    async def test_list_integrations_returns_data(self, admin_client):
        """Returns integrations after creating some."""
        client, session, user_id = admin_client
        session.add(_make_integration(user_id, service_name="snow1"))
        session.add(_make_integration(user_id, service_name="snow2"))
        await session.commit()

        response = await client.get("/integrations/all")
        data = response.json()
        assert data["success"] is True
        assert len(data["integrations"]) == 2
        names = {i["service_name"] for i in data["integrations"]}
        assert names == {"snow1", "snow2"}

    @pytest.mark.asyncio
    async def test_list_integrations_masks_sensitive_fields(self, admin_client):
        """Passwords and secrets are masked in list responses."""
        client, session, user_id = admin_client
        session.add(_make_integration(user_id))
        await session.commit()

        response = await client.get("/integrations/all")
        config = response.json()["integrations"][0]["config"]
        assert config["password"] == "********"
        assert config["url"] == "https://example.service-now.com"
        assert config["username"] == "admin"

    @pytest.mark.asyncio
    async def test_list_integrations_requires_permission(self, no_perms_client):
        """Requires integration.view permission."""
        client, _, _ = no_perms_client
        response = await client.get("/integrations/all")
        assert response.status_code == 403


# ============================================================
# GET /integrations/id/{id} — Get integration by ID
# ============================================================


class TestGetIntegration:
    """Tests for GET /integrations/id/{integration_id}"""

    @pytest.mark.asyncio
    async def test_get_integration_success(self, admin_client):
        """Returns a specific integration by ID."""
        client, session, user_id = admin_client
        intg = _make_integration(user_id, service_name="get_test")
        session.add(intg)
        await session.commit()
        await session.refresh(intg)

        response = await client.get(f"/integrations/id/{intg.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["integration"]["service_name"] == "get_test"

    @pytest.mark.asyncio
    async def test_get_integration_masks_password(self, admin_client):
        """Password is masked in single integration response."""
        client, session, user_id = admin_client
        intg = _make_integration(user_id)
        session.add(intg)
        await session.commit()
        await session.refresh(intg)

        response = await client.get(f"/integrations/id/{intg.id}")
        assert response.json()["integration"]["config"]["password"] == "********"

    @pytest.mark.asyncio
    async def test_get_integration_not_found(self, admin_client):
        """Non-existent integration returns error."""
        client, _, _ = admin_client
        response = await client.get(f"/integrations/id/{uuid4()}")
        data = response.json()
        assert data["success"] is False
        assert "not found" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_get_integration_requires_permission(self, no_perms_client):
        """Requires integration.view permission."""
        client, _, _ = no_perms_client
        response = await client.get(f"/integrations/id/{uuid4()}")
        assert response.status_code == 403


# ============================================================
# POST /integrations/create — Create integration
# ============================================================


class TestCreateIntegration:
    """Tests for POST /integrations/create"""

    @pytest.mark.asyncio
    async def test_create_integration_success(self, admin_client):
        """Create a new integration."""
        client, _, _ = admin_client
        response = await client.post("/integrations/create", json={
            "service_name": "servicenow",
            "auth_type": "basic_auth",
            "config": {"url": "https://new.service-now.com", "username": "admin", "password": "pass"},
            "is_active": True,
            "status": "success",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["integration"]["service_name"] == "servicenow"

    @pytest.mark.asyncio
    async def test_create_integration_masks_response(self, admin_client):
        """Created integration response masks sensitive fields."""
        client, _, _ = admin_client
        response = await client.post("/integrations/create", json={
            "service_name": "servicenow",
            "auth_type": "basic_auth",
            "config": {"url": "https://x.com", "username": "u", "password": "secret"},
            "is_active": False,
            "status": "success",
        })
        config = response.json()["integration"]["config"]
        assert config["password"] == "********"

    @pytest.mark.asyncio
    async def test_create_integration_persists(self, admin_client):
        """Created integration is persisted in the database."""
        client, session, _ = admin_client
        await client.post("/integrations/create", json={
            "service_name": "persist_test",
            "auth_type": "basic_auth",
            "config": {"url": "https://p.com"},
            "is_active": True,
            "status": "success",
        })

        result = await session.execute(
            select(Integration).where(Integration.service_name == "persist_test")
        )
        intg = result.scalar_one_or_none()
        assert intg is not None
        assert intg.config["url"] == "https://p.com"

    @pytest.mark.asyncio
    async def test_create_integration_api_token_auth(self, admin_client):
        """Create integration with API token auth type."""
        client, _, _ = admin_client
        response = await client.post("/integrations/create", json={
            "service_name": "servicenow",
            "auth_type": "api_token",
            "config": {"url": "https://x.com", "api_key": "sk-123"},
            "is_active": True,
            "status": "success",
        })
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_create_integration_requires_permission(self, no_perms_client):
        """Requires integration.create permission."""
        client, _, _ = no_perms_client
        response = await client.post("/integrations/create", json={
            "service_name": "servicenow",
            "auth_type": "basic_auth",
            "config": {},
            "is_active": True,
            "status": "success",
        })
        assert response.status_code == 403


# ============================================================
# PUT /integrations/update/{id} — Update integration
# ============================================================


class TestUpdateIntegration:
    """Tests for PUT /integrations/update/{integration_id}"""

    @pytest.mark.asyncio
    async def test_update_integration_success(self, admin_client):
        """Update an integration's config."""
        client, session, user_id = admin_client
        intg = _make_integration(user_id)
        session.add(intg)
        await session.commit()
        await session.refresh(intg)

        response = await client.put(f"/integrations/update/{intg.id}", json={
            "service_name": "servicenow",
            "auth_type": "basic_auth",
            "config": {"url": "https://updated.com", "username": "new_user", "password": "new_pass"},
            "is_active": False,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["integration"]["config"]["url"] == "https://updated.com"
        assert data["integration"]["is_active"] is False

    @pytest.mark.asyncio
    async def test_update_integration_not_found(self, admin_client):
        """Non-existent integration returns error."""
        client, _, _ = admin_client
        response = await client.put(f"/integrations/update/{uuid4()}", json={
            "service_name": "servicenow",
            "auth_type": "basic_auth",
            "config": {},
            "is_active": True,
        })
        data = response.json()
        assert data["success"] is False
        assert "not found" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_update_integration_persists(self, admin_client):
        """Updated fields are persisted in the database."""
        client, session, user_id = admin_client
        intg = _make_integration(user_id, service_name="before_update")
        session.add(intg)
        await session.commit()
        await session.refresh(intg)
        intg_id = intg.id

        await client.put(f"/integrations/update/{intg_id}", json={
            "service_name": "after_update",
            "auth_type": "basic_auth",
            "config": {"url": "https://after.com"},
            "is_active": True,
        })

        session.expire_all()
        result = await session.execute(
            select(Integration).where(Integration.id == intg_id)
        )
        db_intg = result.scalar_one()
        assert db_intg.service_name == "after_update"

    @pytest.mark.asyncio
    async def test_update_integration_requires_permission(self, no_perms_client):
        """Requires integration.edit permission."""
        client, _, _ = no_perms_client
        response = await client.put(f"/integrations/update/{uuid4()}", json={
            "service_name": "x",
            "auth_type": "basic_auth",
            "config": {},
            "is_active": True,
        })
        assert response.status_code == 403


# ============================================================
# DELETE /integrations/delete/{id} — Delete integration
# ============================================================


class TestDeleteIntegration:
    """Tests for DELETE /integrations/delete/{integration_id}"""

    @pytest.mark.asyncio
    async def test_delete_integration_success(self, admin_client):
        """Delete an integration."""
        client, session, user_id = admin_client
        intg = _make_integration(user_id)
        session.add(intg)
        await session.commit()
        await session.refresh(intg)

        response = await client.delete(f"/integrations/delete/{intg.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "deleted" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_delete_integration_removes_from_db(self, admin_client):
        """Deleted integration is removed from database (hard delete)."""
        client, session, user_id = admin_client
        intg = _make_integration(user_id)
        session.add(intg)
        await session.commit()
        await session.refresh(intg)
        intg_id = intg.id

        await client.delete(f"/integrations/delete/{intg_id}")

        session.expire_all()
        result = await session.execute(
            select(Integration).where(Integration.id == intg_id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_delete_integration_not_found(self, admin_client):
        """Non-existent integration returns error."""
        client, _, _ = admin_client
        response = await client.delete(f"/integrations/delete/{uuid4()}")
        data = response.json()
        assert data["success"] is False
        assert "not found" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_delete_integration_requires_permission(self, no_perms_client):
        """Requires integration.delete permission."""
        client, _, _ = no_perms_client
        response = await client.delete(f"/integrations/delete/{uuid4()}")
        assert response.status_code == 403


# ============================================================
# Edge Cases — Create Integration
# ============================================================


class TestCreateIntegrationEdgeCases:
    """Edge cases for POST /integrations/create"""

    @pytest.mark.asyncio
    async def test_create_with_empty_config(self, admin_client):
        """Create integration with empty config dict."""
        client, _, _ = admin_client
        response = await client.post("/integrations/create", json={
            "service_name": "servicenow",
            "auth_type": "basic_auth",
            "config": {},
            "is_active": True,
            "status": "success",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["integration"]["config"] == {}

    @pytest.mark.asyncio
    async def test_create_with_special_chars_in_service_name(self, admin_client):
        """Service name with special characters is stored correctly."""
        client, _, _ = admin_client
        special = "snow <test> & 'quotes' 日本語"
        response = await client.post("/integrations/create", json={
            "service_name": special,
            "auth_type": "basic_auth",
            "config": {"url": "https://x.com"},
            "is_active": True,
            "status": "success",
        })
        assert response.status_code == 200
        assert response.json()["integration"]["service_name"] == special

    @pytest.mark.asyncio
    async def test_create_masks_multiple_sensitive_fields(self, admin_client):
        """All sensitive config keys (password, api_key, secret, token) are masked."""
        client, _, _ = admin_client
        response = await client.post("/integrations/create", json={
            "service_name": "servicenow",
            "auth_type": "basic_auth",
            "config": {
                "url": "https://x.com",
                "password": "secret_pw",
                "api_key": "sk-12345",
                "secret": "my_secret",
                "token": "bearer_token",
                "access_token": "at_12345",
            },
            "is_active": True,
            "status": "success",
        })
        assert response.status_code == 200
        config = response.json()["integration"]["config"]
        assert config["url"] == "https://x.com"
        assert config["password"] == "********"
        assert config["api_key"] == "********"
        assert config["secret"] == "********"
        assert config["token"] == "********"
        assert config["access_token"] == "********"

    @pytest.mark.asyncio
    async def test_create_integration_xss_in_service_name(self, admin_client):
        """XSS payload in service_name is stored as-is (no server-side sanitization)."""
        client, _, _ = admin_client
        xss = "<img src=x onerror=alert(1)>"
        response = await client.post("/integrations/create", json={
            "service_name": xss,
            "auth_type": "basic_auth",
            "config": {},
            "is_active": True,
            "status": "success",
        })
        assert response.status_code == 200
        # Documents that XSS is stored; frontend must sanitize
        assert response.json()["integration"]["service_name"] == xss

    @pytest.mark.asyncio
    async def test_create_verifies_response_fields(self, admin_client):
        """Created integration response includes all expected fields."""
        client, _, _ = admin_client
        response = await client.post("/integrations/create", json={
            "service_name": "servicenow",
            "auth_type": "api_token",
            "config": {"url": "https://test.com", "api_key": "key"},
            "is_active": False,
            "status": "success",
        })
        assert response.status_code == 200
        intg = response.json()["integration"]
        expected_fields = {"id", "service_name", "auth_type", "config", "is_active", "user_id"}
        assert expected_fields.issubset(set(intg.keys()))
        assert intg["is_active"] is False
        assert intg["auth_type"] == "api_token"


# ============================================================
# Edge Cases — Update Integration
# ============================================================


class TestUpdateIntegrationEdgeCases:
    """Edge cases for PUT /integrations/update/{integration_id}"""

    @pytest.mark.asyncio
    async def test_update_with_masked_password_overwrites(self, admin_client):
        """Sending '********' as password actually stores that string.
        Documents current behavior — no unmasking logic on write."""
        client, session, user_id = admin_client
        intg = _make_integration(user_id)
        session.add(intg)
        await session.commit()
        await session.refresh(intg)
        intg_id = intg.id

        await client.put(f"/integrations/update/{intg_id}", json={
            "service_name": "servicenow",
            "auth_type": "basic_auth",
            "config": {"url": "https://x.com", "username": "u", "password": "********"},
            "is_active": True,
        })

        session.expire_all()
        result = await session.execute(
            select(Integration).where(Integration.id == intg_id)
        )
        db_intg = result.scalar_one()
        # The masked value is stored as-is (documents current behavior)
        assert db_intg.config["password"] == "********"

    @pytest.mark.asyncio
    async def test_update_changes_all_fields(self, admin_client):
        """Update should change service_name, auth_type, config, and is_active."""
        client, session, user_id = admin_client
        intg = _make_integration(user_id, service_name="old_name")
        session.add(intg)
        await session.commit()
        await session.refresh(intg)
        intg_id = intg.id

        response = await client.put(f"/integrations/update/{intg_id}", json={
            "service_name": "new_name",
            "auth_type": "api_token",
            "config": {"url": "https://new.com", "api_key": "newkey"},
            "is_active": False,
        })
        assert response.status_code == 200
        data = response.json()["integration"]
        assert data["service_name"] == "new_name"
        assert data["auth_type"] == "api_token"
        assert data["is_active"] is False
        assert data["config"]["url"] == "https://new.com"
        assert data["config"]["api_key"] == "********"

    @pytest.mark.asyncio
    async def test_update_invalid_uuid(self, admin_client):
        """Update with malformed UUID returns not-found or 422."""
        client, _, _ = admin_client
        response = await client.put("/integrations/update/not-a-uuid", json={
            "service_name": "x",
            "auth_type": "basic_auth",
            "config": {},
            "is_active": True,
        })
        data = response.json()
        assert data["success"] is False


# ============================================================
# Edge Cases — Delete Integration
# ============================================================


class TestDeleteIntegrationEdgeCases:
    """Edge cases for DELETE /integrations/delete/{integration_id}"""

    @pytest.mark.asyncio
    async def test_double_delete_integration(self, admin_client):
        """Deleting the same integration twice returns not-found on second."""
        client, session, user_id = admin_client
        intg = _make_integration(user_id)
        session.add(intg)
        await session.commit()
        await session.refresh(intg)
        intg_id = intg.id

        r1 = await client.delete(f"/integrations/delete/{intg_id}")
        assert r1.status_code == 200
        assert r1.json()["success"] is True

        r2 = await client.delete(f"/integrations/delete/{intg_id}")
        assert r2.json()["success"] is False
        assert "not found" in r2.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_delete_then_list_excludes_deleted(self, admin_client):
        """After deletion, integration is excluded from list."""
        client, session, user_id = admin_client
        intg = _make_integration(user_id, service_name="will_delete")
        session.add(intg)
        await session.commit()
        await session.refresh(intg)

        await client.delete(f"/integrations/delete/{intg.id}")

        response = await client.get("/integrations/all")
        names = [i["service_name"] for i in response.json()["integrations"]]
        assert "will_delete" not in names

    @pytest.mark.asyncio
    async def test_delete_then_get_returns_not_found(self, admin_client):
        """After deletion, GET by ID returns not found."""
        client, session, user_id = admin_client
        intg = _make_integration(user_id)
        session.add(intg)
        await session.commit()
        await session.refresh(intg)
        intg_id = intg.id

        await client.delete(f"/integrations/delete/{intg_id}")

        response = await client.get(f"/integrations/id/{intg_id}")
        assert response.json()["success"] is False


# ============================================================
# Edge Cases — List Integrations
# ============================================================


class TestListIntegrationsEdgeCases:
    """Edge cases for GET /integrations/all"""

    @pytest.mark.asyncio
    async def test_list_with_inactive_integrations(self, admin_client):
        """Inactive integrations are still returned in the list."""
        client, session, user_id = admin_client
        session.add(_make_integration(user_id, service_name="active_one", is_active=True))
        session.add(_make_integration(user_id, service_name="inactive_one", is_active=False))
        await session.commit()

        response = await client.get("/integrations/all")
        data = response.json()
        assert len(data["integrations"]) == 2
        names = {i["service_name"] for i in data["integrations"]}
        assert names == {"active_one", "inactive_one"}

    @pytest.mark.asyncio
    async def test_list_masks_various_sensitive_key_patterns(self, admin_client):
        """Config keys containing 'password', 'secret', 'token' are all masked."""
        client, session, user_id = admin_client
        intg = _make_integration(
            user_id,
            config={
                "url": "https://x.com",
                "db_password": "dbpw123",
                "client_secret": "cs123",
                "auth_token": "at123",
                "safe_field": "visible",
            },
        )
        session.add(intg)
        await session.commit()

        response = await client.get("/integrations/all")
        config = response.json()["integrations"][0]["config"]
        assert config["url"] == "https://x.com"
        assert config["safe_field"] == "visible"
        # These contain sensitive substrings and should be masked
        assert config["db_password"] == "********"
        assert config["client_secret"] == "********"
        assert config["auth_token"] == "********"


# ============================================================
# Edge Cases — Get Integration
# ============================================================


class TestGetIntegrationEdgeCases:
    """Edge cases for GET /integrations/id/{integration_id}"""

    @pytest.mark.asyncio
    async def test_get_integration_invalid_uuid(self, admin_client):
        """Malformed UUID returns an error."""
        client, _, _ = admin_client
        response = await client.get("/integrations/id/not-a-uuid")
        data = response.json()
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_get_integration_with_null_config(self, admin_client):
        """Integration with null/empty config should still be retrievable."""
        client, session, user_id = admin_client
        intg = Integration(
            service_name="null_config",
            auth_type="none",
            config=None,
            is_active=True,
            user_id=user_id,
        )
        session.add(intg)
        await session.commit()
        await session.refresh(intg)

        response = await client.get(f"/integrations/id/{intg.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["integration"]["config"] is None


# ============================================================
# Unauthenticated access
# ============================================================


class TestIntegrationsUnauthenticated:
    """Unauthenticated requests to integration endpoints are rejected."""

    @pytest.mark.asyncio
    async def test_list_unauth(self, client):
        response = await client.get("/integrations/all")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_unauth(self, client):
        response = await client.get(f"/integrations/id/{uuid4()}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_unauth(self, client):
        response = await client.post("/integrations/create", json={
            "service_name": "x", "auth_type": "basic_auth",
            "config": {}, "is_active": True, "status": "success",
        })
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_unauth(self, client):
        response = await client.put(f"/integrations/update/{uuid4()}", json={
            "service_name": "x", "auth_type": "basic_auth",
            "config": {}, "is_active": True,
        })
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_unauth(self, client):
        response = await client.delete(f"/integrations/delete/{uuid4()}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_sync_unauth(self, client):
        response = await client.post(f"/integrations/sync/{uuid4()}")
        assert response.status_code == 403

class TestSyncIntegration:
    """Tests for POST /integrations/sync/{integration_id}"""

    @pytest.mark.asyncio
    async def test_sync_not_found(self, admin_client):
        """Sync non-existent integration returns SSE error event."""
        client, _, _ = admin_client
        response = await client.post(f"/integrations/sync/{uuid4()}")
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        body = response.text
        assert "not found" in body.lower()

    @pytest.mark.asyncio
    async def test_sync_missing_config(self, admin_client):
        """Sync with missing ServiceNow config returns SSE error."""
        client, session, user_id = admin_client
        intg = _make_integration(user_id, config={"url": "https://x.com"})
        session.add(intg)
        await session.commit()
        await session.refresh(intg)

        response = await client.post(f"/integrations/sync/{intg.id}")
        assert response.status_code == 200
        body = response.text
        assert "missing" in body.lower() or "error" in body.lower()

    @pytest.mark.asyncio
    async def test_sync_requires_permission(self, no_perms_client):
        """Requires integration.sync permission."""
        client, _, _ = no_perms_client
        response = await client.post(f"/integrations/sync/{uuid4()}")
        assert response.status_code == 403

class TestMaskHelpers:
    """Unit tests for masking helper functions."""

    def test_mask_sensitive_config_empty(self):
        from src.api.routers.integrations import mask_sensitive_config
        assert mask_sensitive_config({}) == {}
        assert mask_sensitive_config(None) is None

    def test_mask_sensitive_config_masks_keys(self):
        from src.api.routers.integrations import mask_sensitive_config
        config = {"url": "x", "password": "pw", "api_key": "k", "secret": "s", "token": "t"}
        result = mask_sensitive_config(config)
        assert result["url"] == "x"
        assert result["password"] == "********"
        assert result["api_key"] == "********"
        assert result["secret"] == "********"
        assert result["token"] == "********"

    def test_mask_integration_response_format(self):
        from src.api.routers.integrations import mask_integration_response
        from unittest.mock import MagicMock
        from datetime import datetime, timezone

        intg = MagicMock()
        intg.id = uuid4()
        intg.service_name = "snow"
        intg.auth_type = "basic"
        intg.config = {"url": "x", "password": "secret"}
        intg.is_active = True
        intg.last_synced_at = datetime.now(timezone.utc)
        intg.last_sync_status = "success"
        intg.last_sync_error = None
        intg.updated_at = datetime.now(timezone.utc)
        intg.user_id = uuid4()

        result = mask_integration_response(intg)
        assert result["service_name"] == "snow"
        assert result["config"]["password"] == "********"
        assert "Z" in result["last_synced_at"]

    def test_sse_event_format(self):
        from src.api.routers.integrations import _sse_event
        result = _sse_event("progress", {"batch": 1})
        assert result.startswith("event: progress\n")
        assert '"batch": 1' in result
        assert result.endswith("\n\n")

class TestIntegrationErrorPaths:
    """Tests for exception handling in integration CRUD."""

    @pytest.mark.asyncio
    async def test_get_integrations_db_error(self, admin_client):
        """DB error in get_integrations returns error response."""
        client, session, _ = admin_client
        with patch.object(session, "execute", side_effect=RuntimeError("db down")):
            response = await client.get("/integrations/all")
        data = response.json()
        assert data["success"] is False

class TestSyncIntegrationSSE:
    """Tests for POST /integrations/sync/{id} SSE endpoint."""

    @pytest.mark.asyncio
    async def test_sync_not_found(self, admin_client):
        """Non-existent integration returns SSE error event."""
        client, _, _ = admin_client
        response = await client.post(f"/integrations/sync/{uuid4()}")
        assert response.status_code == 200
        assert "event-stream" in response.headers.get("content-type", "")
        assert "Integration not found" in response.text

    @pytest.mark.asyncio
    async def test_sync_missing_config(self, admin_client):
        """Integration without url/username/password returns SSE error."""
        client, session, _ = admin_client
        from src.api.db.models import Integration
        intg = Integration(
            service_name="snow", auth_type="basic",
            config={"url": "http://example.com"},  # missing username/password
            is_active=True, user_id=str(uuid4()),
        )
        session.add(intg)
        await session.commit()
        await session.refresh(intg)

        response = await client.post(f"/integrations/sync/{intg.id}")
        assert "Missing ServiceNow configuration" in response.text

    @pytest.mark.asyncio
    async def test_sync_servicenow_error(self, admin_client):
        """ServiceNow fetch error streams error event."""
        client, session, _ = admin_client
        from src.api.db.models import Integration
        intg = Integration(
            service_name="snow", auth_type="basic",
            config={"url": "http://sn.test", "username": "u", "password": "p"},
            is_active=True, user_id=str(uuid4()),
        )
        session.add(intg)
        await session.commit()
        await session.refresh(intg)

        with patch("src.api.routers.integrations.run_servicenow_ingestion",
                   side_effect=RuntimeError("Connection refused")):
            response = await client.post(f"/integrations/sync/{intg.id}")
        body = response.text
        assert "Connection refused" in body
        assert "event: error" in body

    @pytest.mark.asyncio
    async def test_sync_no_incidents(self, admin_client):
        """Sync with 0 incidents succeeds with progress event."""
        client, session, _ = admin_client
        from src.api.db.models import Integration
        intg = Integration(
            service_name="snow", auth_type="basic",
            config={"url": "http://sn.test", "username": "u", "password": "p"},
            is_active=True, user_id=str(uuid4()),
        )
        session.add(intg)
        await session.commit()
        await session.refresh(intg)

        with patch("src.api.routers.integrations.run_servicenow_ingestion",
                   return_value={"normalized": [], "added": 0, "total": 0,
                                 "last_synced": "2025-01-01"}):
            response = await client.post(f"/integrations/sync/{intg.id}")
        body = response.text
        assert "event: complete" in body
        assert "No new incidents" in body or "event: progress" in body

    @pytest.mark.asyncio
    async def test_sync_with_incidents(self, admin_client):
        """Sync with incidents starts ingestion and streams events."""
        client, session, _ = admin_client
        from src.api.db.models import Integration
        intg = Integration(
            service_name="snow", auth_type="basic",
            config={"url": "http://sn.test", "username": "u", "password": "p"},
            is_active=True, user_id=str(uuid4()),
        )
        session.add(intg)
        await session.commit()
        await session.refresh(intg)

        incidents = [{"number": f"INC{i}", "short_description": f"Issue {i}",
                      "description": f"Desc {i}", "priority": "1", "state": "6",
                      "category": "network", "assigned_to": "admin",
                      "sys_created_on": "2025-01-01", "sys_updated_on": "2025-01-02",
                      "resolved_at": "2025-01-03", "close_notes": "fixed"}
                     for i in range(3)]

        mock_svc = AsyncMock()
        mock_upload = MagicMock()
        mock_upload.id = uuid4()
        mock_svc.create_upload_session = AsyncMock(return_value=mock_upload)
        mock_version = MagicMock()
        mock_version.id = uuid4()
        mock_version.version_number = 1
        mock_svc.confirm_and_ingest = AsyncMock(return_value=mock_version)

        with patch("src.api.routers.integrations.run_servicenow_ingestion",
                   return_value={"normalized": incidents, "added": 3, "total": 3,
                                 "last_synced": "2025-01-02"}), \
             patch("src.api.routers.integrations.IncidentIngestionService",
                   return_value=mock_svc):
            response = await client.post(f"/integrations/sync/{intg.id}")
        body = response.text
        assert "event: progress" in body
        assert "event: complete" in body


class TestCreateDeleteErrorPaths:
    """Cover create/delete exception handlers (lines 117-119, 142-144)."""

    @pytest.mark.asyncio
    async def test_create_integration_db_commit_error(self, admin_client):
        """DB error during create returns error response (lines 117-119)."""
        client, session, uid = admin_client
        from src.api.main import app
        from src.api.db.session import get_session as real_get_session

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock(side_effect=RuntimeError("insert failed"))
        mock_session.rollback = AsyncMock()
        app.dependency_overrides[real_get_session] = lambda: mock_session
        try:
            response = await client.post("/integrations/create", json={
                "service_name": "fail", "auth_type": "basic_auth",
                "config": {}, "is_active": True,
            })
            data = response.json()
            assert data["success"] is False
            assert "Error occurred" in data["message"]
        finally:
            app.dependency_overrides[real_get_session] = lambda: session

    @pytest.mark.asyncio
    async def test_delete_integration_db_error(self, admin_client):
        """DB error during delete returns error response (lines 142-144)."""
        client, session, uid = admin_client
        from src.api.main import app
        from src.api.db.session import get_session as real_get_session

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=RuntimeError("delete failed"))
        mock_session.rollback = AsyncMock()
        app.dependency_overrides[real_get_session] = lambda: mock_session
        try:
            response = await client.delete(f"/integrations/delete/{uuid4()}")
            data = response.json()
            assert data["success"] is False
            assert "Error occurred" in data["message"]
        finally:
            app.dependency_overrides[real_get_session] = lambda: session


class TestSyncSSEDeep:
    """Cover remaining sync SSE inner code (lines 270, 303-304, 317-323, 326-332)."""

    @pytest.mark.asyncio
    async def test_sync_ingestion_error_event(self, admin_client):
        """Ingestion error sends SSE error event (lines 303-304, 317-320)."""
        client, session, uid = admin_client
        intg = Integration(
            service_name="ServiceNow", auth_type="basic",
            config={"instance_url": "https://test.service-now.com",
                    "username": "admin", "password": "pass"},
            is_active=True, user_id=uid,
        )
        session.add(intg)
        await session.commit()
        await session.refresh(intg)

        incidents = [{"incident_id": f"INC{i}", "title": f"Inc {i}",
                      "description": f"Desc {i}", "action_taken": f"Fix {i}",
                      "opened_at": "2025-01-01", "updated_at": "2025-01-02",
                      "resolved_at": "2025-01-03", "close_notes": "fixed"}
                     for i in range(2)]

        mock_svc = AsyncMock()
        mock_upload = MagicMock()
        mock_upload.id = uuid4()
        mock_svc.create_upload_session = AsyncMock(return_value=mock_upload)
        mock_svc.confirm_and_ingest = AsyncMock(side_effect=RuntimeError("ingest boom"))

        with patch("src.api.routers.integrations.run_servicenow_ingestion",
                   return_value={"normalized": incidents, "added": 2, "total": 2,
                                 "last_synced": "2025-01-02"}), \
             patch("src.api.routers.integrations.IncidentIngestionService",
                   return_value=mock_svc):
            response = await client.post(f"/integrations/sync/{intg.id}")
        body = response.text
        assert "event: error" in body
