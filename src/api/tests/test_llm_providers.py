"""Comprehensive tests for LLM Providers endpoints (/llm-providers).

Covers:
- CRUD operations (list, get, create, update, delete)
- Input validation (required fields, length limits, enum values)
- Permission/RBAC enforcement
- API key encryption (never exposed in responses)
- Default provider logic (only one at a time)
- Auto-populated models for known provider types
- Health check / test connection (mocked HTTP)
- Model discovery (mocked HTTP)
- Available models aggregation
- Unauthenticated access
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from uuid import uuid4

from sqlalchemy.future import select

from src.api.db.models.llm_provider import LlmProvider
from src.api.schemas.llm_provider_schemas import (
    ANTHROPIC_MODELS,
    OPENAI_MODELS,
    GOOGLE_MODELS,
)


# ============================================================
# Helpers
# ============================================================

def _make_provider(*, name="Test Provider", provider_type="anthropic", **kwargs):
    """Build an LlmProvider ORM instance with sensible defaults."""
    defaults = dict(
        name=name,
        provider_type=provider_type,
        config={},
        models=["claude-3-5-sonnet-20241022"],
        is_active=True,
        is_default=False,
    )
    defaults.update(kwargs)
    return LlmProvider(**defaults)


def _create_payload(*, name="New Provider", provider_type="anthropic", **overrides):
    """Build a JSON payload for POST /llm-providers/."""
    payload = {"name": name, "provider_type": provider_type}
    payload.update(overrides)
    return payload


# ============================================================
# GET /llm-providers/ — List providers
# ============================================================


class TestListProviders:
    """Tests for GET /llm-providers/"""

    @pytest.mark.asyncio
    async def test_list_providers_empty(self, admin_client):
        """Returns empty list when no providers exist."""
        client, session, _ = admin_client
        response = await client.get("/llm-providers/")
        assert response.status_code == 200
        data = response.json()
        assert data["providers"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_providers_returns_all(self, admin_client):
        """Returns all providers."""
        client, session, _ = admin_client
        session.add_all([
            _make_provider(name="Provider A"),
            _make_provider(name="Provider B"),
        ])
        await session.commit()

        response = await client.get("/llm-providers/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        names = {p["name"] for p in data["providers"]}
        assert names == {"Provider A", "Provider B"}

    @pytest.mark.asyncio
    async def test_list_providers_active_only(self, admin_client):
        """active_only=true filters inactive providers."""
        client, session, _ = admin_client
        session.add_all([
            _make_provider(name="Active", is_active=True),
            _make_provider(name="Inactive", is_active=False),
        ])
        await session.commit()

        response = await client.get("/llm-providers/?active_only=true")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["providers"][0]["name"] == "Active"

    @pytest.mark.asyncio
    async def test_list_providers_active_only_false(self, admin_client):
        """active_only=false returns all providers."""
        client, session, _ = admin_client
        session.add_all([
            _make_provider(name="Active", is_active=True),
            _make_provider(name="Inactive", is_active=False),
        ])
        await session.commit()

        response = await client.get("/llm-providers/?active_only=false")
        assert response.status_code == 200
        assert response.json()["total"] == 2

    @pytest.mark.asyncio
    async def test_list_providers_response_format(self, admin_client):
        """Each provider has expected response fields."""
        client, session, _ = admin_client
        session.add(_make_provider(name="Format Test"))
        await session.commit()

        response = await client.get("/llm-providers/")
        data = response.json()
        provider = data["providers"][0]
        expected_fields = {
            "id", "name", "provider_type", "base_url", "has_api_key",
            "config", "models", "is_active", "is_default",
            "last_health_check_at", "last_health_check_status",
            "last_health_check_error", "created_at", "updated_at",
        }
        assert expected_fields.issubset(set(provider.keys()))

    @pytest.mark.asyncio
    async def test_list_providers_api_key_not_exposed(self, admin_client):
        """API key is never returned, only has_api_key flag."""
        client, session, _ = admin_client
        session.add(_make_provider(
            name="Key Test",
            api_key_encrypted="encrypted-value",
        ))
        await session.commit()

        response = await client.get("/llm-providers/")
        provider = response.json()["providers"][0]
        assert "api_key" not in provider
        assert "api_key_encrypted" not in provider
        assert provider["has_api_key"] is True

    @pytest.mark.asyncio
    async def test_list_providers_no_key_has_api_key_false(self, admin_client):
        """Provider without API key returns has_api_key=false."""
        client, session, _ = admin_client
        session.add(_make_provider(name="No Key", api_key_encrypted=None))
        await session.commit()

        response = await client.get("/llm-providers/")
        provider = response.json()["providers"][0]
        assert provider["has_api_key"] is False

    @pytest.mark.asyncio
    async def test_list_providers_requires_permission(self, no_perms_client):
        """Requires llm_provider.view permission."""
        client, _, _ = no_perms_client
        response = await client.get("/llm-providers/")
        assert response.status_code == 403
        assert "Missing permission: llm_provider.view" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_providers_unauthenticated(self, client):
        """Unauthenticated request is rejected."""
        response = await client.get("/llm-providers/")
        assert response.status_code == 403


# ============================================================
# GET /llm-providers/{provider_id} — Get provider by ID
# ============================================================


class TestGetProvider:
    """Tests for GET /llm-providers/{provider_id}"""

    @pytest.mark.asyncio
    async def test_get_provider_success(self, admin_client):
        """Returns correct provider for valid ID."""
        client, session, _ = admin_client
        provider = _make_provider(name="Get Me", provider_type="openai")
        session.add(provider)
        await session.commit()
        await session.refresh(provider)

        response = await client.get(f"/llm-providers/{provider.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Get Me"
        assert data["provider_type"] == "openai"
        assert data["id"] == str(provider.id)

    @pytest.mark.asyncio
    async def test_get_provider_not_found(self, admin_client):
        """Non-existent ID returns 404."""
        client, _, _ = admin_client
        response = await client.get(f"/llm-providers/{uuid4()}")
        assert response.status_code == 404
        assert "Provider not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_provider_invalid_uuid(self, admin_client):
        """Invalid UUID format returns 422."""
        client, _, _ = admin_client
        response = await client.get("/llm-providers/not-a-uuid")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_provider_api_key_hidden(self, admin_client):
        """API key is never exposed in response."""
        client, session, _ = admin_client
        provider = _make_provider(api_key_encrypted="secret-encrypted")
        session.add(provider)
        await session.commit()
        await session.refresh(provider)

        response = await client.get(f"/llm-providers/{provider.id}")
        data = response.json()
        assert "api_key" not in data
        assert "api_key_encrypted" not in data
        assert data["has_api_key"] is True

    @pytest.mark.asyncio
    async def test_get_provider_requires_permission(self, no_perms_client):
        """Requires llm_provider.view permission."""
        client, session, _ = no_perms_client
        provider = _make_provider()
        session.add(provider)
        await session.commit()
        await session.refresh(provider)

        response = await client.get(f"/llm-providers/{provider.id}")
        assert response.status_code == 403


# ============================================================
# POST /llm-providers/ — Create provider
# ============================================================


class TestCreateProvider:
    """Tests for POST /llm-providers/"""

    @pytest.mark.asyncio
    async def test_create_provider_minimal(self, admin_client):
        """Create provider with only required fields."""
        client, _, _ = admin_client
        response = await client.post(
            "/llm-providers/",
            json=_create_payload(name="Minimal Provider"),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal Provider"
        assert data["provider_type"] == "anthropic"
        assert data["is_active"] is True
        assert data["is_default"] is False
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_provider_all_fields(self, admin_client):
        """Create provider with all optional fields."""
        client, _, _ = admin_client
        response = await client.post("/llm-providers/", json={
            "name": "Full Provider",
            "provider_type": "openai",
            "api_key": "sk-test-key",
            "base_url": "https://custom.api.com",
            "config": {"organization_id": "org-123"},
            "models": ["gpt-4o", "gpt-4"],
            "is_active": True,
            "is_default": True,
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Full Provider"
        assert data["provider_type"] == "openai"
        assert data["base_url"] == "https://custom.api.com"
        assert data["has_api_key"] is True
        assert data["config"] == {"organization_id": "org-123"}
        assert data["models"] == ["gpt-4o", "gpt-4"]
        assert data["is_default"] is True

    @pytest.mark.asyncio
    async def test_create_provider_auto_populates_anthropic_models(self, admin_client):
        """Empty models list auto-populates defaults for anthropic."""
        client, _, _ = admin_client
        response = await client.post("/llm-providers/", json={
            "name": "Anthropic Auto",
            "provider_type": "anthropic",
            "models": [],
        })
        assert response.status_code == 201
        data = response.json()
        assert data["models"] == ANTHROPIC_MODELS

    @pytest.mark.asyncio
    async def test_create_provider_auto_populates_openai_models(self, admin_client):
        """Empty models list auto-populates defaults for openai."""
        client, _, _ = admin_client
        response = await client.post("/llm-providers/", json={
            "name": "OpenAI Auto",
            "provider_type": "openai",
            "models": [],
        })
        assert response.status_code == 201
        assert response.json()["models"] == OPENAI_MODELS

    @pytest.mark.asyncio
    async def test_create_provider_auto_populates_google_models(self, admin_client):
        """Empty models list auto-populates defaults for google."""
        client, _, _ = admin_client
        response = await client.post("/llm-providers/", json={
            "name": "Google Auto",
            "provider_type": "google",
            "models": [],
        })
        assert response.status_code == 201
        assert response.json()["models"] == GOOGLE_MODELS

    @pytest.mark.asyncio
    async def test_create_provider_custom_no_auto_models(self, admin_client):
        """Custom provider with empty models stays empty."""
        client, _, _ = admin_client
        response = await client.post("/llm-providers/", json={
            "name": "Custom Empty",
            "provider_type": "custom",
            "models": [],
        })
        assert response.status_code == 201
        assert response.json()["models"] == []

    @pytest.mark.asyncio
    async def test_create_provider_custom_models_override(self, admin_client):
        """Explicit models list overrides auto-population."""
        client, _, _ = admin_client
        response = await client.post("/llm-providers/", json={
            "name": "Custom Models",
            "provider_type": "anthropic",
            "models": ["my-custom-model"],
        })
        assert response.status_code == 201
        assert response.json()["models"] == ["my-custom-model"]

    @pytest.mark.asyncio
    async def test_create_provider_encrypts_api_key(self, admin_client):
        """API key is encrypted before storage."""
        client, session, _ = admin_client
        response = await client.post("/llm-providers/", json={
            "name": "Key Encrypt Test",
            "provider_type": "anthropic",
            "api_key": "sk-my-secret-key",
        })
        assert response.status_code == 201
        provider_id = response.json()["id"]

        # Verify the API key is encrypted in DB (not plaintext)
        result = await session.execute(
            select(LlmProvider).where(LlmProvider.name == "Key Encrypt Test")
        )
        db_provider = result.scalar_one()
        assert db_provider.api_key_encrypted is not None
        assert db_provider.api_key_encrypted != "sk-my-secret-key"
        assert db_provider.api_key_encrypted != ""

    @pytest.mark.asyncio
    async def test_create_provider_no_api_key(self, admin_client):
        """Provider without API key has has_api_key=false."""
        client, _, _ = admin_client
        response = await client.post("/llm-providers/", json={
            "name": "No Key",
            "provider_type": "anthropic",
        })
        assert response.status_code == 201
        assert response.json()["has_api_key"] is False

    @pytest.mark.asyncio
    async def test_create_provider_sets_default_unsets_previous(self, admin_client):
        """Setting is_default=true unsets the previous default."""
        client, session, _ = admin_client

        # Create first default provider
        resp1 = await client.post("/llm-providers/", json={
            "name": "First Default",
            "provider_type": "anthropic",
            "is_default": True,
        })
        assert resp1.status_code == 201
        id1 = resp1.json()["id"]

        # Create second default provider
        resp2 = await client.post("/llm-providers/", json={
            "name": "Second Default",
            "provider_type": "openai",
            "is_default": True,
        })
        assert resp2.status_code == 201

        # Verify first is no longer default
        resp_check = await client.get(f"/llm-providers/{id1}")
        assert resp_check.json()["is_default"] is False

    @pytest.mark.asyncio
    async def test_create_provider_persists_in_db(self, admin_client):
        """Created provider is persisted in the database."""
        client, session, _ = admin_client
        response = await client.post("/llm-providers/", json={
            "name": "Persisted",
            "provider_type": "google",
        })
        assert response.status_code == 201

        result = await session.execute(
            select(LlmProvider).where(LlmProvider.name == "Persisted")
        )
        db_provider = result.scalar_one_or_none()
        assert db_provider is not None
        assert db_provider.provider_type == "google"

    @pytest.mark.asyncio
    async def test_create_provider_missing_name(self, admin_client):
        """Missing name returns 422."""
        client, _, _ = admin_client
        response = await client.post("/llm-providers/", json={
            "provider_type": "anthropic",
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_provider_empty_name(self, admin_client):
        """Empty name returns 422."""
        client, _, _ = admin_client
        response = await client.post("/llm-providers/", json={
            "name": "",
            "provider_type": "anthropic",
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_provider_name_too_long(self, admin_client):
        """Name exceeding 100 chars returns 422."""
        client, _, _ = admin_client
        response = await client.post("/llm-providers/", json={
            "name": "x" * 101,
            "provider_type": "anthropic",
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_provider_name_at_max_length(self, admin_client):
        """Name at exactly 100 chars succeeds."""
        client, _, _ = admin_client
        response = await client.post("/llm-providers/", json={
            "name": "x" * 100,
            "provider_type": "anthropic",
        })
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_create_provider_missing_provider_type(self, admin_client):
        """Missing provider_type returns 422."""
        client, _, _ = admin_client
        response = await client.post("/llm-providers/", json={
            "name": "No Type",
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_provider_invalid_provider_type(self, admin_client):
        """Invalid provider_type returns 422."""
        client, _, _ = admin_client
        response = await client.post("/llm-providers/", json={
            "name": "Bad Type",
            "provider_type": "invalid_type",
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_provider_all_valid_types(self, admin_client):
        """All valid provider types can be created."""
        client, _, _ = admin_client
        for ptype in ["anthropic", "openai", "google", "custom"]:
            response = await client.post("/llm-providers/", json={
                "name": f"Type {ptype}",
                "provider_type": ptype,
            })
            assert response.status_code == 201, f"Failed for type: {ptype}"
            assert response.json()["provider_type"] == ptype

    @pytest.mark.asyncio
    async def test_create_provider_empty_body(self, admin_client):
        """Empty body returns 422."""
        client, _, _ = admin_client
        response = await client.post("/llm-providers/", json={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_provider_requires_permission(self, no_perms_client):
        """Requires llm_provider.create permission."""
        client, _, _ = no_perms_client
        response = await client.post("/llm-providers/", json=_create_payload())
        assert response.status_code == 403
        assert "Missing permission: llm_provider.create" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_provider_duplicate_name_allowed(self, admin_client):
        """Duplicate names are allowed (no unique constraint)."""
        client, _, _ = admin_client
        resp1 = await client.post("/llm-providers/", json=_create_payload(name="Same"))
        resp2 = await client.post("/llm-providers/", json=_create_payload(name="Same"))
        assert resp1.status_code == 201
        assert resp2.status_code == 201


# ============================================================
# PUT /llm-providers/{provider_id} — Update provider
# ============================================================


class TestUpdateProvider:
    """Tests for PUT /llm-providers/{provider_id}"""

    @pytest.mark.asyncio
    async def test_update_provider_name(self, admin_client):
        """Update provider name."""
        client, session, _ = admin_client
        provider = _make_provider(name="Old Name")
        session.add(provider)
        await session.commit()
        await session.refresh(provider)

        response = await client.put(
            f"/llm-providers/{provider.id}", json={"name": "New Name"}
        )
        assert response.status_code == 200
        assert response.json()["name"] == "New Name"

    @pytest.mark.asyncio
    async def test_update_provider_models(self, admin_client):
        """Update provider model list."""
        client, session, _ = admin_client
        provider = _make_provider(models=["old-model"])
        session.add(provider)
        await session.commit()
        await session.refresh(provider)

        response = await client.put(
            f"/llm-providers/{provider.id}",
            json={"models": ["new-model-1", "new-model-2"]},
        )
        assert response.status_code == 200
        assert response.json()["models"] == ["new-model-1", "new-model-2"]

    @pytest.mark.asyncio
    async def test_update_provider_is_active(self, admin_client):
        """Update is_active flag."""
        client, session, _ = admin_client
        provider = _make_provider(is_active=True)
        session.add(provider)
        await session.commit()
        await session.refresh(provider)

        response = await client.put(
            f"/llm-providers/{provider.id}", json={"is_active": False}
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    @pytest.mark.asyncio
    async def test_update_provider_set_default_unsets_previous(self, admin_client):
        """Setting is_default=true unsets previous default."""
        client, session, _ = admin_client
        p1 = _make_provider(name="Default One", is_default=True)
        p2 = _make_provider(name="Not Default")
        session.add_all([p1, p2])
        await session.commit()
        await session.refresh(p1)
        await session.refresh(p2)

        response = await client.put(
            f"/llm-providers/{p2.id}", json={"is_default": True}
        )
        assert response.status_code == 200
        assert response.json()["is_default"] is True

        # Verify first is no longer default
        resp_check = await client.get(f"/llm-providers/{p1.id}")
        assert resp_check.json()["is_default"] is False

    @pytest.mark.asyncio
    async def test_update_provider_api_key(self, admin_client):
        """Update API key encrypts the new value."""
        client, session, _ = admin_client
        provider = _make_provider()
        session.add(provider)
        await session.commit()
        await session.refresh(provider)
        pid = provider.id

        response = await client.put(
            f"/llm-providers/{pid}", json={"api_key": "new-secret-key"}
        )
        assert response.status_code == 200
        assert response.json()["has_api_key"] is True

        # Verify encrypted in DB
        session.expire_all()
        result = await session.execute(
            select(LlmProvider).where(LlmProvider.id == pid)
        )
        db_provider = result.scalar_one()
        assert db_provider.api_key_encrypted is not None
        assert db_provider.api_key_encrypted != "new-secret-key"

    @pytest.mark.asyncio
    async def test_update_provider_clear_api_key(self, admin_client):
        """Passing empty api_key clears the stored key."""
        client, session, _ = admin_client
        provider = _make_provider(api_key_encrypted="old-encrypted")
        session.add(provider)
        await session.commit()
        await session.refresh(provider)

        response = await client.put(
            f"/llm-providers/{provider.id}", json={"api_key": ""}
        )
        assert response.status_code == 200
        assert response.json()["has_api_key"] is False

    @pytest.mark.asyncio
    async def test_update_provider_base_url(self, admin_client):
        """Update base_url."""
        client, session, _ = admin_client
        provider = _make_provider()
        session.add(provider)
        await session.commit()
        await session.refresh(provider)

        response = await client.put(
            f"/llm-providers/{provider.id}",
            json={"base_url": "https://new.endpoint.com"},
        )
        assert response.status_code == 200
        assert response.json()["base_url"] == "https://new.endpoint.com"

    @pytest.mark.asyncio
    async def test_update_provider_config(self, admin_client):
        """Update config dict."""
        client, session, _ = admin_client
        provider = _make_provider(config={})
        session.add(provider)
        await session.commit()
        await session.refresh(provider)

        new_config = {"organization_id": "org-xyz"}
        response = await client.put(
            f"/llm-providers/{provider.id}", json={"config": new_config}
        )
        assert response.status_code == 200
        assert response.json()["config"] == new_config

    @pytest.mark.asyncio
    async def test_update_provider_not_found(self, admin_client):
        """Non-existent ID returns 404."""
        client, _, _ = admin_client
        response = await client.put(
            f"/llm-providers/{uuid4()}", json={"name": "Nope"}
        )
        assert response.status_code == 404
        assert "Provider not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_provider_invalid_uuid(self, admin_client):
        """Invalid UUID returns 422."""
        client, _, _ = admin_client
        response = await client.put(
            "/llm-providers/not-a-uuid", json={"name": "Nope"}
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_provider_empty_name(self, admin_client):
        """Empty name returns 422."""
        client, session, _ = admin_client
        provider = _make_provider()
        session.add(provider)
        await session.commit()
        await session.refresh(provider)

        response = await client.put(
            f"/llm-providers/{provider.id}", json={"name": ""}
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_provider_name_too_long(self, admin_client):
        """Name exceeding 100 chars returns 422."""
        client, session, _ = admin_client
        provider = _make_provider()
        session.add(provider)
        await session.commit()
        await session.refresh(provider)

        response = await client.put(
            f"/llm-providers/{provider.id}", json={"name": "x" * 101}
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_provider_no_changes(self, admin_client):
        """Empty update body succeeds (no-op)."""
        client, session, _ = admin_client
        provider = _make_provider(name="Unchanged")
        session.add(provider)
        await session.commit()
        await session.refresh(provider)

        response = await client.put(f"/llm-providers/{provider.id}", json={})
        assert response.status_code == 200
        assert response.json()["name"] == "Unchanged"

    @pytest.mark.asyncio
    async def test_update_provider_persists_changes(self, admin_client):
        """Changes are persisted in the database."""
        client, session, _ = admin_client
        provider = _make_provider(name="Before")
        session.add(provider)
        await session.commit()
        await session.refresh(provider)
        pid = provider.id

        await client.put(
            f"/llm-providers/{pid}",
            json={"name": "After", "is_active": False},
        )

        session.expire_all()
        result = await session.execute(
            select(LlmProvider).where(LlmProvider.id == pid)
        )
        db_provider = result.scalar_one()
        assert db_provider.name == "After"
        assert db_provider.is_active is False

    @pytest.mark.asyncio
    async def test_update_provider_requires_permission(self, no_perms_client):
        """Requires llm_provider.edit permission."""
        client, session, _ = no_perms_client
        provider = _make_provider()
        session.add(provider)
        await session.commit()
        await session.refresh(provider)

        response = await client.put(
            f"/llm-providers/{provider.id}", json={"name": "Hack"}
        )
        assert response.status_code == 403
        assert "Missing permission: llm_provider.edit" in response.json()["detail"]


# ============================================================
# DELETE /llm-providers/{provider_id} — Delete provider
# ============================================================


class TestDeleteProvider:
    """Tests for DELETE /llm-providers/{provider_id}"""

    @pytest.mark.asyncio
    async def test_delete_provider_success(self, admin_client):
        """Delete returns 204 No Content."""
        client, session, _ = admin_client
        provider = _make_provider(name="To Delete")
        session.add(provider)
        await session.commit()
        await session.refresh(provider)

        response = await client.delete(f"/llm-providers/{provider.id}")
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_provider_hard_delete(self, admin_client):
        """Delete removes provider from database entirely (hard delete)."""
        client, session, _ = admin_client
        provider = _make_provider(name="Hard Delete Test")
        session.add(provider)
        await session.commit()
        await session.refresh(provider)
        pid = provider.id

        await client.delete(f"/llm-providers/{pid}")

        session.expire_all()
        result = await session.execute(
            select(LlmProvider).where(LlmProvider.id == pid)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_delete_provider_not_found(self, admin_client):
        """Non-existent ID returns 404."""
        client, _, _ = admin_client
        response = await client.delete(f"/llm-providers/{uuid4()}")
        assert response.status_code == 404
        assert "Provider not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_provider_invalid_uuid(self, admin_client):
        """Invalid UUID returns 422."""
        client, _, _ = admin_client
        response = await client.delete("/llm-providers/not-a-uuid")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_deleted_provider_not_in_list(self, admin_client):
        """After deletion, provider no longer appears in list."""
        client, session, _ = admin_client
        provider = _make_provider(name="Will Vanish")
        session.add(provider)
        await session.commit()
        await session.refresh(provider)

        await client.delete(f"/llm-providers/{provider.id}")

        response = await client.get("/llm-providers/")
        names = [p["name"] for p in response.json()["providers"]]
        assert "Will Vanish" not in names

    @pytest.mark.asyncio
    async def test_deleted_provider_not_gettable(self, admin_client):
        """After deletion, provider cannot be retrieved by ID."""
        client, session, _ = admin_client
        provider = _make_provider(name="Gone")
        session.add(provider)
        await session.commit()
        await session.refresh(provider)

        await client.delete(f"/llm-providers/{provider.id}")

        response = await client.get(f"/llm-providers/{provider.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_provider_requires_permission(self, no_perms_client):
        """Requires llm_provider.delete permission."""
        client, session, _ = no_perms_client
        provider = _make_provider()
        session.add(provider)
        await session.commit()
        await session.refresh(provider)

        response = await client.delete(f"/llm-providers/{provider.id}")
        assert response.status_code == 403
        assert "Missing permission: llm_provider.delete" in response.json()["detail"]


# ============================================================
# PATCH /llm-providers/{provider_id}/toggle-active — Toggle active
# ============================================================


class TestToggleActive:
    """Tests for PATCH /llm-providers/{provider_id}/toggle-active"""

    @pytest.mark.asyncio
    async def test_toggle_active_deactivate(self, admin_client):
        """Toggle active provider to inactive when multiple active providers exist."""
        client, session, _ = admin_client

        p1 = _make_provider(name="Provider A", is_active=True)
        p2 = _make_provider(name="Provider B", is_active=True)
        session.add_all([p1, p2])
        await session.commit()
        await session.refresh(p1)

        response = await client.put(f"/llm-providers/{p1.id}/toggle-active")
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False

    @pytest.mark.asyncio
    async def test_toggle_active_activate(self, admin_client):
        """Toggle inactive provider to active."""
        client, session, _ = admin_client

        provider = _make_provider(is_active=False)
        session.add(provider)
        await session.commit()
        await session.refresh(provider)

        response = await client.put(f"/llm-providers/{provider.id}/toggle-active")
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_toggle_active_last_provider_rejected(self, admin_client):
        """Cannot deactivate the only active provider."""
        client, session, _ = admin_client

        provider = _make_provider(is_active=True)
        session.add(provider)
        await session.commit()
        await session.refresh(provider)

        response = await client.put(f"/llm-providers/{provider.id}/toggle-active")
        assert response.status_code == 400
        assert "Cannot deactivate the only active provider" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_toggle_active_not_found(self, admin_client):
        """Toggle returns 404 for non-existent provider."""
        client, _, _ = admin_client

        fake_id = uuid4()
        response = await client.put(f"/llm-providers/{fake_id}/toggle-active")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_toggle_active_requires_permission(self, no_perms_client):
        """Toggle requires llm_provider.edit permission."""
        client, session, _ = no_perms_client

        provider = _make_provider(is_active=True)
        session.add(provider)
        await session.commit()
        await session.refresh(provider)

        response = await client.put(f"/llm-providers/{provider.id}/toggle-active")
        assert response.status_code == 403


# ============================================================
# POST /llm-providers/{provider_id}/test — Test connection
# ============================================================


class TestTestConnection:
    """Tests for POST /llm-providers/{provider_id}/test"""

    @pytest.mark.asyncio
    async def test_connection_success(self, admin_client):
        """Successful health check returns success=true."""
        client, session, _ = admin_client
        provider = _make_provider(api_key_encrypted=None)
        session.add(provider)
        await session.commit()
        await session.refresh(provider)
        pid = provider.id

        mock_result = {
            "success": True,
            "status": "success",
            "message": "Connection successful",
            "response_time_ms": 42.5,
        }
        with patch(
            "src.api.routers.llm_providers.LlmProviderService.test_connection",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            response = await client.post(f"/llm-providers/{pid}/test")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "success"
        assert data["provider_id"] == str(pid)
        assert data["response_time_ms"] == 42.5

    @pytest.mark.asyncio
    async def test_connection_failure(self, admin_client):
        """Failed health check returns success=false."""
        client, session, _ = admin_client
        provider = _make_provider()
        session.add(provider)
        await session.commit()
        await session.refresh(provider)

        mock_result = {
            "success": False,
            "status": "error",
            "message": "Connection timed out",
            "response_time_ms": 15000.0,
        }
        with patch(
            "src.api.routers.llm_providers.LlmProviderService.test_connection",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            response = await client.post(
                f"/llm-providers/{provider.id}/test"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["status"] == "error"
        assert data["message"] == "Connection timed out"

    @pytest.mark.asyncio
    async def test_connection_not_found(self, admin_client):
        """Non-existent provider returns 404."""
        client, _, _ = admin_client
        response = await client.post(f"/llm-providers/{uuid4()}/test")
        assert response.status_code == 404
        assert "Provider not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_connection_invalid_uuid(self, admin_client):
        """Invalid UUID returns 422."""
        client, _, _ = admin_client
        response = await client.post("/llm-providers/not-a-uuid/test")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_connection_requires_permission(self, no_perms_client):
        """Requires llm_provider.test permission."""
        client, session, _ = no_perms_client
        provider = _make_provider()
        session.add(provider)
        await session.commit()
        await session.refresh(provider)

        response = await client.post(f"/llm-providers/{provider.id}/test")
        assert response.status_code == 403
        assert "Missing permission: llm_provider.test" in response.json()["detail"]


# ============================================================
# POST /llm-providers/{provider_id}/discover-models — Discover from saved
# ============================================================


class TestDiscoverModels:
    """Tests for POST /llm-providers/{provider_id}/discover-models"""

    @pytest.mark.asyncio
    async def test_discover_models_success(self, admin_client):
        """Successful model discovery returns model list."""
        client, session, _ = admin_client
        provider = _make_provider()
        session.add(provider)
        await session.commit()
        await session.refresh(provider)

        mock_result = {
            "success": True,
            "models": ["claude-3-5-sonnet-20241022", "claude-3-opus-20240229"],
            "message": "Found 2 models",
        }
        with patch(
            "src.api.routers.llm_providers.LlmProviderService.discover_models",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            response = await client.post(
                f"/llm-providers/{provider.id}/discover-models"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["models"]) == 2

    @pytest.mark.asyncio
    async def test_discover_models_failure(self, admin_client):
        """Failed discovery returns success=false."""
        client, session, _ = admin_client
        provider = _make_provider()
        session.add(provider)
        await session.commit()
        await session.refresh(provider)

        mock_result = {
            "success": False,
            "models": [],
            "message": "Connection timed out",
        }
        with patch(
            "src.api.routers.llm_providers.LlmProviderService.discover_models",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            response = await client.post(
                f"/llm-providers/{provider.id}/discover-models"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["models"] == []

    @pytest.mark.asyncio
    async def test_discover_models_not_found(self, admin_client):
        """Non-existent provider returns 404."""
        client, _, _ = admin_client
        response = await client.post(f"/llm-providers/{uuid4()}/discover-models")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_discover_models_requires_permission(self, no_perms_client):
        """Requires llm_provider.view permission."""
        client, session, _ = no_perms_client
        provider = _make_provider()
        session.add(provider)
        await session.commit()
        await session.refresh(provider)

        response = await client.post(
            f"/llm-providers/{provider.id}/discover-models"
        )
        assert response.status_code == 403


# ============================================================
# POST /llm-providers/discover-models — Discover from config
# ============================================================


class TestDiscoverModelsFromConfig:
    """Tests for POST /llm-providers/discover-models"""

    @pytest.mark.asyncio
    async def test_discover_from_config_success(self, admin_client):
        """Successful discovery from config."""
        client, _, _ = admin_client

        mock_result = {
            "success": True,
            "models": ["gpt-4o", "gpt-4"],
            "message": "Found 2 models",
        }
        with patch(
            "src.api.routers.llm_providers.LlmProviderService.discover_models_from_config",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            response = await client.post("/llm-providers/discover-models", json={
                "name": "Test Discovery",
                "provider_type": "openai",
                "api_key": "sk-test",
            })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["models"]) == 2

    @pytest.mark.asyncio
    async def test_discover_from_config_missing_fields(self, admin_client):
        """Missing required fields returns 422."""
        client, _, _ = admin_client
        response = await client.post(
            "/llm-providers/discover-models", json={"name": "Incomplete"}
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_discover_from_config_requires_permission(self, no_perms_client):
        """Requires llm_provider.create permission."""
        client, _, _ = no_perms_client
        response = await client.post("/llm-providers/discover-models", json={
            "name": "Unauthorized",
            "provider_type": "anthropic",
        })
        assert response.status_code == 403


# ============================================================
# GET /llm-providers/models/available — Available models
# ============================================================


class TestAvailableModels:
    """Tests for GET /llm-providers/models/available"""

    @pytest.mark.asyncio
    async def test_available_models_empty(self, admin_client):
        """Returns empty list when no active providers."""
        client, _, _ = admin_client
        response = await client.get("/llm-providers/models/available")
        assert response.status_code == 200
        assert response.json()["models"] == []

    @pytest.mark.asyncio
    async def test_available_models_aggregates_active(self, admin_client):
        """Aggregates models from all active providers."""
        client, session, _ = admin_client
        session.add_all([
            _make_provider(name="P1", models=["model-a", "model-b"], is_active=True),
            _make_provider(name="P2", models=["model-c"], is_active=True),
        ])
        await session.commit()

        response = await client.get("/llm-providers/models/available")
        assert response.status_code == 200
        data = response.json()
        model_ids = {m["model_id"] for m in data["models"]}
        assert model_ids == {"model-a", "model-b", "model-c"}

    @pytest.mark.asyncio
    async def test_available_models_excludes_inactive(self, admin_client):
        """Inactive providers are excluded."""
        client, session, _ = admin_client
        session.add_all([
            _make_provider(name="Active", models=["active-model"], is_active=True),
            _make_provider(name="Inactive", models=["hidden-model"], is_active=False),
        ])
        await session.commit()

        response = await client.get("/llm-providers/models/available")
        data = response.json()
        model_ids = {m["model_id"] for m in data["models"]}
        assert "active-model" in model_ids
        assert "hidden-model" not in model_ids

    @pytest.mark.asyncio
    async def test_available_models_response_format(self, admin_client):
        """Each model has expected fields."""
        client, session, _ = admin_client
        session.add(_make_provider(
            name="Format P",
            models=["model-x"],
            is_default=True,
        ))
        await session.commit()

        response = await client.get("/llm-providers/models/available")
        data = response.json()
        assert len(data["models"]) == 1
        model = data["models"][0]
        assert model["model_id"] == "model-x"
        assert model["provider_name"] == "Format P"
        assert model["display_name"] == "Format P - model-x"
        assert model["is_default_provider"] is True
        assert "provider_id" in model
        assert "provider_type" in model

    @pytest.mark.asyncio
    async def test_available_models_requires_permission(self, no_perms_client):
        """Requires llm_provider.view permission."""
        client, _, _ = no_perms_client
        response = await client.get("/llm-providers/models/available")
        assert response.status_code == 403


# ============================================================
# Unauthenticated access — all endpoints
# ============================================================


class TestLlmProvidersUnauthenticated:
    """Unauthenticated requests to all LLM provider endpoints are rejected."""

    @pytest.mark.asyncio
    async def test_list_unauth(self, client):
        response = await client.get("/llm-providers/")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_unauth(self, client):
        response = await client.get(f"/llm-providers/{uuid4()}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_unauth(self, client):
        response = await client.post(
            "/llm-providers/", json=_create_payload()
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_unauth(self, client):
        response = await client.put(
            f"/llm-providers/{uuid4()}", json={"name": "Test"}
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_unauth(self, client):
        response = await client.delete(f"/llm-providers/{uuid4()}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_test_connection_unauth(self, client):
        response = await client.post(f"/llm-providers/{uuid4()}/test")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_discover_models_unauth(self, client):
        response = await client.post(
            f"/llm-providers/{uuid4()}/discover-models"
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_discover_from_config_unauth(self, client):
        response = await client.post(
            "/llm-providers/discover-models",
            json=_create_payload(),
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_available_models_unauth(self, client):
        response = await client.get("/llm-providers/models/available")
        assert response.status_code == 403

from src.api.db.models import Setting, User
from src.api.services.llm_provider_service import LlmProviderService
from src.api.utils.llm_provider_helper import (
    get_provider_config_for_chat,
    get_provider_config_for_model,
)


async def _ensure_user(session, user_id=None):
    from uuid import uuid4 as _uuid4
    uid = user_id or _uuid4()
    user = User(id=uid, email=f"u-{str(uid)[:8]}@test.com", is_active=True)
    session.add(user)
    await session.flush()
    return uid


def _make_setting(user_id, **overrides):
    defaults = dict(
        user_id=user_id,
        deny_words="",
        langfuse_enabled=False,
        change_type="create",
    )
    defaults.update(overrides)
    return Setting(**defaults)


class TestProviderConnectionMocked:
    """Tests for _test_provider_connection with mocked httpx."""

    @pytest.mark.asyncio
    async def test_anthropic_success(self, test_session):
        svc = LlmProviderService(test_session)
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("src.api.services.llm_provider_service.httpx.AsyncClient") as mock_client:
            mock_ctx = AsyncMock()
            mock_ctx.get = AsyncMock(return_value=mock_resp)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            success, msg = await svc._test_provider_connection(
                "anthropic", None, "test-key", {}
            )
        assert success is True
        assert msg == "OK"

    @pytest.mark.asyncio
    async def test_openai_failure(self, test_session):
        svc = LlmProviderService(test_session)
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"

        with patch("src.api.services.llm_provider_service.httpx.AsyncClient") as mock_client:
            mock_ctx = AsyncMock()
            mock_ctx.get = AsyncMock(return_value=mock_resp)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            success, msg = await svc._test_provider_connection(
                "openai", None, "bad-key", {}
            )
        assert success is False
        assert "401" in msg

    @pytest.mark.asyncio
    async def test_timeout(self, test_session):
        import httpx as httpx_mod
        svc = LlmProviderService(test_session)

        with patch("src.api.services.llm_provider_service.httpx.AsyncClient") as mock_client:
            mock_ctx = AsyncMock()
            mock_ctx.get = AsyncMock(side_effect=httpx_mod.TimeoutException("timed out"))
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            success, msg = await svc._test_provider_connection(
                "anthropic", None, "key", {}
            )
        assert success is False
        assert "timed out" in msg.lower()

    @pytest.mark.asyncio
    async def test_unknown_provider_type(self, test_session):
        svc = LlmProviderService(test_session)

        with patch("src.api.services.llm_provider_service.httpx.AsyncClient") as mock_client:
            mock_ctx = AsyncMock()
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            success, msg = await svc._test_provider_connection(
                "unknown_type", None, "key", {}
            )
        assert success is False
        assert "Unknown provider type" in msg

    @pytest.mark.asyncio
    async def test_custom_no_base_url(self, test_session):
        svc = LlmProviderService(test_session)

        with patch("src.api.services.llm_provider_service.httpx.AsyncClient") as mock_client:
            mock_ctx = AsyncMock()
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            success, msg = await svc._test_provider_connection(
                "custom", None, "key", {}
            )
        assert success is False
        assert "Base URL is required" in msg

    @pytest.mark.asyncio
    async def test_google_success(self, test_session):
        svc = LlmProviderService(test_session)
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("src.api.services.llm_provider_service.httpx.AsyncClient") as mock_client:
            mock_ctx = AsyncMock()
            mock_ctx.get = AsyncMock(return_value=mock_resp)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            success, msg = await svc._test_provider_connection(
                "google", None, "test-key", {}
            )
        assert success is True


class TestProviderConfigForChat:
    """Tests for get_provider_config_for_chat helper."""

    @pytest.mark.asyncio
    async def test_no_settings_returns_defaults(self, test_session):
        config = await get_provider_config_for_chat(test_session)
        assert config["provider_type"] is None
        assert config["temperature"] == 0.33

    @pytest.mark.asyncio
    async def test_with_default_provider(self, test_session):
        uid = await _ensure_user(test_session)
        provider = _make_provider(
            name="Default", provider_type="openai", is_default=True,
            models=["gpt-4"],
        )
        test_session.add(provider)
        await test_session.flush()

        setting = _make_setting(uid)
        test_session.add(setting)
        await test_session.commit()

        with patch("src.api.utils.llm_provider_helper.decrypt_value", return_value="decrypted"):
            config = await get_provider_config_for_chat(test_session)
        assert config["provider_type"] == "openai"
        assert config["model_id"] == "gpt-4"

    @pytest.mark.asyncio
    async def test_no_active_provider(self, test_session):
        uid = await _ensure_user(test_session)
        provider = _make_provider(name="Inactive", is_active=False)
        test_session.add(provider)
        setting = _make_setting(uid)
        test_session.add(setting)
        await test_session.commit()

        config = await get_provider_config_for_chat(test_session)
        assert config["provider_type"] is None

    @pytest.mark.asyncio
    async def test_provider_no_models(self, test_session):
        uid = await _ensure_user(test_session)
        provider = _make_provider(
            name="Empty Models", is_default=True, models=[],
        )
        test_session.add(provider)
        setting = _make_setting(uid)
        test_session.add(setting)
        await test_session.commit()

        config = await get_provider_config_for_chat(test_session)
        assert config["provider_type"] is None


class TestProviderConfigForModel:
    """Tests for get_provider_config_for_model helper."""

    @pytest.mark.asyncio
    async def test_valid_override(self, test_session):
        provider = _make_provider(
            name="Override", provider_type="openai",
            is_active=True, models=["gpt-4"],
        )
        test_session.add(provider)
        await test_session.commit()
        await test_session.refresh(provider)

        with patch("src.api.utils.llm_provider_helper.decrypt_value", return_value="key"):
            config = await get_provider_config_for_model(
                test_session, str(provider.id), "gpt-4"
            )
        assert config["provider_type"] == "openai"
        assert config["model_id"] == "gpt-4"

    @pytest.mark.asyncio
    async def test_model_not_in_provider_falls_back(self, test_session):
        provider = _make_provider(
            name="Limited", provider_type="openai",
            is_active=True, models=["gpt-4"],
        )
        test_session.add(provider)
        await test_session.commit()
        await test_session.refresh(provider)

        config = await get_provider_config_for_model(
            test_session, str(provider.id), "gpt-3.5-turbo"
        )
        # Falls back to default chat config
        assert config["model_id"] != "gpt-3.5-turbo"

    @pytest.mark.asyncio
    async def test_provider_not_found_falls_back(self, test_session):
        config = await get_provider_config_for_model(
            test_session, str(uuid4()), "some-model"
        )
        assert config["provider_type"] is None

    @pytest.mark.asyncio
    async def test_inactive_provider_falls_back(self, test_session):
        provider = _make_provider(
            name="Dead", is_active=False, models=["gpt-4"],
        )
        test_session.add(provider)
        await test_session.commit()
        await test_session.refresh(provider)

        config = await get_provider_config_for_model(
            test_session, str(provider.id), "gpt-4"
        )
        assert config["provider_type"] is None


# ============================================================
# Service-layer CRUD tests — LlmProviderService
# ============================================================

from src.api.schemas.llm_provider_schemas import LlmProviderCreate, LlmProviderUpdate


class TestLlmProviderServiceCRUD:
    """Service-level tests for LlmProviderService CRUD."""

    @pytest.mark.asyncio
    async def test_list_providers_empty(self, test_session):
        svc = LlmProviderService(test_session)
        result = await svc.list_providers()
        assert result == []

    @pytest.mark.asyncio
    async def test_list_providers_returns_all(self, test_session):
        svc = LlmProviderService(test_session)
        test_session.add_all([
            _make_provider(name="A", is_active=True),
            _make_provider(name="B", is_active=False),
        ])
        await test_session.commit()
        result = await svc.list_providers()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_providers_active_only(self, test_session):
        svc = LlmProviderService(test_session)
        test_session.add_all([
            _make_provider(name="Active", is_active=True),
            _make_provider(name="Inactive", is_active=False),
        ])
        await test_session.commit()
        result = await svc.list_providers(active_only=True)
        assert len(result) == 1
        assert result[0].name == "Active"

    @pytest.mark.asyncio
    async def test_get_provider_found(self, test_session):
        svc = LlmProviderService(test_session)
        p = _make_provider(name="Find Me")
        test_session.add(p)
        await test_session.commit()
        await test_session.refresh(p)
        found = await svc.get_provider(p.id)
        assert found is not None
        assert found.name == "Find Me"

    @pytest.mark.asyncio
    async def test_get_provider_not_found(self, test_session):
        svc = LlmProviderService(test_session)
        found = await svc.get_provider(uuid4())
        assert found is None

    @pytest.mark.asyncio
    async def test_get_default_provider(self, test_session):
        svc = LlmProviderService(test_session)
        test_session.add(_make_provider(name="Default", is_default=True, is_active=True))
        test_session.add(_make_provider(name="Other", is_default=False, is_active=True))
        await test_session.commit()
        result = await svc.get_default_provider()
        assert result is not None
        assert result.name == "Default"

    @pytest.mark.asyncio
    async def test_get_default_provider_none(self, test_session):
        svc = LlmProviderService(test_session)
        result = await svc.get_default_provider()
        assert result is None

    @pytest.mark.asyncio
    async def test_create_provider(self, test_session):
        svc = LlmProviderService(test_session)
        data = LlmProviderCreate(
            name="New Provider",
            provider_type="openai",
            api_key="sk-test",
            models=["gpt-4"],
        )
        with patch("src.api.services.llm_provider_service.encrypt_value", return_value="encrypted"):
            provider = await svc.create_provider(data)
        assert provider.name == "New Provider"
        assert provider.provider_type == "openai"
        assert provider.api_key_encrypted == "encrypted"

    @pytest.mark.asyncio
    async def test_create_provider_sets_default(self, test_session):
        svc = LlmProviderService(test_session)
        # Create first provider as default
        test_session.add(_make_provider(name="Old Default", is_default=True))
        await test_session.commit()

        data = LlmProviderCreate(
            name="New Default",
            provider_type="anthropic",
            is_default=True,
        )
        with patch("src.api.services.llm_provider_service.encrypt_value", return_value="enc"):
            provider = await svc.create_provider(data)
        assert provider.is_default is True

    @pytest.mark.asyncio
    async def test_create_provider_auto_models(self, test_session):
        svc = LlmProviderService(test_session)
        data = LlmProviderCreate(
            name="Auto Models",
            provider_type="anthropic",
        )
        with patch("src.api.services.llm_provider_service.encrypt_value", return_value="enc"):
            provider = await svc.create_provider(data)
        # Should auto-populate models for known provider
        assert len(provider.models) > 0

    @pytest.mark.asyncio
    async def test_update_provider(self, test_session):
        svc = LlmProviderService(test_session)
        p = _make_provider(name="Old Name")
        test_session.add(p)
        await test_session.commit()
        await test_session.refresh(p)

        data = LlmProviderUpdate(name="New Name")
        result = await svc.update_provider(p.id, data)
        assert result is not None
        assert result.name == "New Name"

    @pytest.mark.asyncio
    async def test_update_provider_not_found(self, test_session):
        svc = LlmProviderService(test_session)
        data = LlmProviderUpdate(name="X")
        result = await svc.update_provider(uuid4(), data)
        assert result is None

    @pytest.mark.asyncio
    async def test_update_provider_api_key(self, test_session):
        svc = LlmProviderService(test_session)
        p = _make_provider(name="Key Update")
        test_session.add(p)
        await test_session.commit()
        await test_session.refresh(p)

        data = LlmProviderUpdate(api_key="new-secret")
        with patch("src.api.services.llm_provider_service.encrypt_value", return_value="new-enc"):
            result = await svc.update_provider(p.id, data)
        assert result.api_key_encrypted == "new-enc"

    @pytest.mark.asyncio
    async def test_update_provider_becomes_default(self, test_session):
        svc = LlmProviderService(test_session)
        old = _make_provider(name="OldDef", is_default=True)
        new = _make_provider(name="NewDef", is_default=False)
        test_session.add_all([old, new])
        await test_session.commit()
        await test_session.refresh(new)

        data = LlmProviderUpdate(is_default=True)
        result = await svc.update_provider(new.id, data)
        assert result.is_default is True

    @pytest.mark.asyncio
    async def test_delete_provider_success(self, test_session):
        svc = LlmProviderService(test_session)
        p = _make_provider(name="Delete Me")
        test_session.add(p)
        await test_session.commit()
        await test_session.refresh(p)
        pid = p.id

        result = await svc.delete_provider(pid)
        assert result is True
        assert await svc.get_provider(pid) is None

    @pytest.mark.asyncio
    async def test_delete_provider_not_found(self, test_session):
        svc = LlmProviderService(test_session)
        result = await svc.delete_provider(uuid4())
        assert result is False

    @pytest.mark.asyncio
    async def test_toggle_active_deactivate(self, test_session):
        svc = LlmProviderService(test_session)
        p1 = _make_provider(name="P1", is_active=True)
        p2 = _make_provider(name="P2", is_active=True)
        test_session.add_all([p1, p2])
        await test_session.commit()
        await test_session.refresh(p1)

        result = await svc.toggle_active(p1.id)
        assert result.is_active is False

    @pytest.mark.asyncio
    async def test_toggle_active_activate(self, test_session):
        svc = LlmProviderService(test_session)
        p = _make_provider(name="Inactive", is_active=False)
        test_session.add(p)
        await test_session.commit()
        await test_session.refresh(p)

        result = await svc.toggle_active(p.id)
        assert result.is_active is True

    @pytest.mark.asyncio
    async def test_toggle_active_last_raises(self, test_session):
        svc = LlmProviderService(test_session)
        p = _make_provider(name="Only", is_active=True)
        test_session.add(p)
        await test_session.commit()
        await test_session.refresh(p)

        with pytest.raises(ValueError, match="Cannot deactivate the only active provider"):
            await svc.toggle_active(p.id)

    @pytest.mark.asyncio
    async def test_toggle_active_not_found(self, test_session):
        svc = LlmProviderService(test_session)
        result = await svc.toggle_active(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_available_models(self, test_session):
        svc = LlmProviderService(test_session)
        test_session.add_all([
            _make_provider(name="P1", models=["m1", "m2"], is_active=True),
            _make_provider(name="P2", models=["m3"], is_active=True),
            _make_provider(name="P3", models=["m4"], is_active=False),
        ])
        await test_session.commit()

        models = await svc.get_available_models()
        model_ids = [m.model_id for m in models]
        assert "m1" in model_ids
        assert "m2" in model_ids
        assert "m3" in model_ids
        assert "m4" not in model_ids

    @pytest.mark.asyncio
    async def test_get_decrypted_api_key(self, test_session):
        svc = LlmProviderService(test_session)
        p = _make_provider(name="Key", api_key_encrypted="encrypted-val")
        test_session.add(p)
        await test_session.commit()
        await test_session.refresh(p)

        with patch("src.api.services.llm_provider_service.decrypt_value", return_value="secret"):
            key = await svc.get_decrypted_api_key(p.id)
        assert key == "secret"

    @pytest.mark.asyncio
    async def test_get_decrypted_api_key_not_found(self, test_session):
        svc = LlmProviderService(test_session)
        key = await svc.get_decrypted_api_key(uuid4())
        assert key is None

    @pytest.mark.asyncio
    async def test_get_decrypted_api_key_no_key(self, test_session):
        svc = LlmProviderService(test_session)
        p = _make_provider(name="NoKey", api_key_encrypted=None)
        test_session.add(p)
        await test_session.commit()
        await test_session.refresh(p)

        key = await svc.get_decrypted_api_key(p.id)
        assert key is None


class TestTestConnectionService:
    """Service-level tests for test_connection method."""

    @pytest.mark.asyncio
    async def test_connection_not_found(self, test_session):
        svc = LlmProviderService(test_session)
        result = await svc.test_connection(uuid4())
        assert result["success"] is False
        assert result["message"] == "Provider not found"

    @pytest.mark.asyncio
    async def test_connection_success_updates_health(self, test_session):
        svc = LlmProviderService(test_session)
        p = _make_provider(name="HC")
        test_session.add(p)
        await test_session.commit()
        await test_session.refresh(p)

        with patch.object(svc, "_test_provider_connection", new_callable=AsyncMock, return_value=(True, "OK")), \
             patch("src.api.services.llm_provider_service.decrypt_value", return_value="key"):
            result = await svc.test_connection(p.id)
        assert result["success"] is True
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_connection_failure_updates_health(self, test_session):
        svc = LlmProviderService(test_session)
        p = _make_provider(name="FailHC")
        test_session.add(p)
        await test_session.commit()
        await test_session.refresh(p)

        with patch.object(svc, "_test_provider_connection", new_callable=AsyncMock, return_value=(False, "Timeout")), \
             patch("src.api.services.llm_provider_service.decrypt_value", return_value="key"):
            result = await svc.test_connection(p.id)
        assert result["success"] is False
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_connection_exception_updates_health(self, test_session):
        svc = LlmProviderService(test_session)
        p = _make_provider(name="ExcHC")
        test_session.add(p)
        await test_session.commit()
        await test_session.refresh(p)

        with patch.object(svc, "_test_provider_connection", new_callable=AsyncMock, side_effect=RuntimeError("boom")), \
             patch("src.api.services.llm_provider_service.decrypt_value", return_value="key"):
            result = await svc.test_connection(p.id)
        assert result["success"] is False
        assert "boom" in result["message"]


class TestDiscoverModelsService:
    """Service-level tests for discover_models and discover_models_from_config."""

    @pytest.mark.asyncio
    async def test_discover_models_not_found(self, test_session):
        svc = LlmProviderService(test_session)
        result = await svc.discover_models(uuid4())
        assert result["success"] is False
        assert result["message"] == "Provider not found"

    @pytest.mark.asyncio
    async def test_discover_models_delegates_to_config(self, test_session):
        svc = LlmProviderService(test_session)
        p = _make_provider(name="Disc")
        test_session.add(p)
        await test_session.commit()
        await test_session.refresh(p)

        with patch.object(svc, "discover_models_from_config", new_callable=AsyncMock, return_value={"success": True, "models": ["m1"], "message": "ok"}), \
             patch("src.api.services.llm_provider_service.decrypt_value", return_value="key"):
            result = await svc.discover_models(p.id)
        assert result["success"] is True
        assert "m1" in result["models"]

    @pytest.mark.asyncio
    async def test_discover_from_config_success(self, test_session):
        svc = LlmProviderService(test_session)
        with patch.object(svc, "_fetch_models_from_provider", new_callable=AsyncMock, return_value=["m1", "m2"]):
            result = await svc.discover_models_from_config("openai", None, "key", {})
        assert result["success"] is True
        assert len(result["models"]) == 2

    @pytest.mark.asyncio
    async def test_discover_from_config_empty(self, test_session):
        svc = LlmProviderService(test_session)
        with patch.object(svc, "_fetch_models_from_provider", new_callable=AsyncMock, return_value=[]):
            result = await svc.discover_models_from_config("openai", None, "key", {})
        assert result["success"] is False
        assert "No models found" in result["message"]

    @pytest.mark.asyncio
    async def test_discover_from_config_exception(self, test_session):
        svc = LlmProviderService(test_session)
        with patch.object(svc, "_fetch_models_from_provider", new_callable=AsyncMock, side_effect=RuntimeError("fail")):
            result = await svc.discover_models_from_config("openai", None, "key", {})
        assert result["success"] is False
        assert "fail" in result["message"]


class TestFetchModelsFromProvider:
    """Tests for _fetch_models_from_provider with mocked httpx."""

    def _mock_httpx(self, mock_resp):
        """Helper to set up mocked httpx.AsyncClient."""
        mock_client = patch("src.api.services.llm_provider_service.httpx.AsyncClient")
        return mock_client, mock_resp

    @pytest.mark.asyncio
    async def test_anthropic_models(self, test_session):
        svc = LlmProviderService(test_session)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"id": "claude-3"}, {"id": "claude-2"}]}

        with patch("src.api.services.llm_provider_service.httpx.AsyncClient") as mc:
            mock_ctx = AsyncMock()
            mock_ctx.get = AsyncMock(return_value=mock_resp)
            mc.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mc.return_value.__aexit__ = AsyncMock(return_value=False)

            models = await svc._fetch_models_from_provider("anthropic", None, "key", {})
        assert "claude-3" in models
        assert "claude-2" in models

    @pytest.mark.asyncio
    async def test_openai_models_filters_gpt(self, test_session):
        svc = LlmProviderService(test_session)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [
            {"id": "gpt-4"}, {"id": "gpt-3.5-turbo"},
            {"id": "dall-e-3"}, {"id": "whisper-1"},
        ]}

        with patch("src.api.services.llm_provider_service.httpx.AsyncClient") as mc:
            mock_ctx = AsyncMock()
            mock_ctx.get = AsyncMock(return_value=mock_resp)
            mc.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mc.return_value.__aexit__ = AsyncMock(return_value=False)

            models = await svc._fetch_models_from_provider("openai", None, "key", {})
        assert "gpt-4" in models
        assert "gpt-3.5-turbo" in models
        assert "dall-e-3" not in models

    @pytest.mark.asyncio
    async def test_google_models(self, test_session):
        svc = LlmProviderService(test_session)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [
            {"name": "models/gemini-pro"},
            {"name": "models/gemini-1.5-flash"},
            {"name": "models/text-bison-001"},
        ]}

        with patch("src.api.services.llm_provider_service.httpx.AsyncClient") as mc:
            mock_ctx = AsyncMock()
            mock_ctx.get = AsyncMock(return_value=mock_resp)
            mc.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mc.return_value.__aexit__ = AsyncMock(return_value=False)

            models = await svc._fetch_models_from_provider("google", None, "key", {})
        assert "gemini-pro" in models
        assert "gemini-1.5-flash" in models
        assert "text-bison-001" not in models

    @pytest.mark.asyncio
    async def test_custom_ollama_models(self, test_session):
        svc = LlmProviderService(test_session)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [
            {"name": "llama3:latest"},
            {"name": "mistral:7b"},
        ]}

        with patch("src.api.services.llm_provider_service.httpx.AsyncClient") as mc:
            mock_ctx = AsyncMock()
            mock_ctx.get = AsyncMock(return_value=mock_resp)
            mc.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mc.return_value.__aexit__ = AsyncMock(return_value=False)

            models = await svc._fetch_models_from_provider("custom", "http://localhost:11434", None, {})
        assert "llama3:latest" in models
        assert "mistral:7b" in models

    @pytest.mark.asyncio
    async def test_custom_no_base_url(self, test_session):
        svc = LlmProviderService(test_session)
        models = await svc._fetch_models_from_provider("custom", None, None, {})
        assert models == []

    @pytest.mark.asyncio
    async def test_custom_fallback_to_openai_compat(self, test_session):
        import httpx as httpx_mod
        svc = LlmProviderService(test_session)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"id": "custom-model"}]}

        with patch("src.api.services.llm_provider_service.httpx.AsyncClient") as mc:
            mock_ctx = AsyncMock()
            # First call (ollama /api/tags) fails, second call (openai /v1/models) succeeds
            mock_ctx.get = AsyncMock(side_effect=[httpx_mod.RequestError("fail"), mock_resp])
            mc.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mc.return_value.__aexit__ = AsyncMock(return_value=False)

            models = await svc._fetch_models_from_provider("custom", "http://localhost:8080", None, {"auth_type": "bearer"})
        assert "custom-model" in models


class TestCustomProviderConnection:
    """Test _test_provider_connection with custom provider auth types."""

    @pytest.mark.asyncio
    async def test_custom_bearer_auth(self, test_session):
        svc = LlmProviderService(test_session)
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("src.api.services.llm_provider_service.httpx.AsyncClient") as mc:
            mock_ctx = AsyncMock()
            mock_ctx.get = AsyncMock(return_value=mock_resp)
            mc.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mc.return_value.__aexit__ = AsyncMock(return_value=False)

            success, msg = await svc._test_provider_connection(
                "custom", "http://localhost:8080", "my-key",
                {"auth_type": "bearer"}
            )
        assert success is True

    @pytest.mark.asyncio
    async def test_custom_api_key_header(self, test_session):
        svc = LlmProviderService(test_session)
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("src.api.services.llm_provider_service.httpx.AsyncClient") as mc:
            mock_ctx = AsyncMock()
            mock_ctx.get = AsyncMock(return_value=mock_resp)
            mc.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mc.return_value.__aexit__ = AsyncMock(return_value=False)

            success, msg = await svc._test_provider_connection(
                "custom", "http://localhost:8080", "my-key",
                {"auth_type": "api_key_header", "auth_header_name": "X-Custom-Key"}
            )
        assert success is True

    @pytest.mark.asyncio
    async def test_custom_basic_auth(self, test_session):
        svc = LlmProviderService(test_session)
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("src.api.services.llm_provider_service.httpx.AsyncClient") as mc:
            mock_ctx = AsyncMock()
            mock_ctx.get = AsyncMock(return_value=mock_resp)
            mc.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mc.return_value.__aexit__ = AsyncMock(return_value=False)

            success, msg = await svc._test_provider_connection(
                "custom", "http://localhost:8080", "user:pass",
                {"auth_type": "basic"}
            )
        assert success is True

    @pytest.mark.asyncio
    async def test_custom_connect_error(self, test_session):
        import httpx as httpx_mod
        svc = LlmProviderService(test_session)

        with patch("src.api.services.llm_provider_service.httpx.AsyncClient") as mc:
            mock_ctx = AsyncMock()
            mock_ctx.get = AsyncMock(side_effect=httpx_mod.ConnectError("refused"))
            mc.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mc.return_value.__aexit__ = AsyncMock(return_value=False)

            success, msg = await svc._test_provider_connection(
                "custom", "http://localhost:9999", "key",
                {"auth_type": "none"}
            )
        assert success is False
        assert "Connection failed" in msg

    @pytest.mark.asyncio
    async def test_custom_fallback_on_request_error(self, test_session):
        """Custom provider tries /api/tags first, falls back to /v1/models."""
        import httpx as httpx_mod
        svc = LlmProviderService(test_session)
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("src.api.services.llm_provider_service.httpx.AsyncClient") as mc:
            mock_ctx = AsyncMock()
            mock_ctx.get = AsyncMock(side_effect=[httpx_mod.RequestError("fail"), mock_resp])
            mc.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mc.return_value.__aexit__ = AsyncMock(return_value=False)

            success, msg = await svc._test_provider_connection(
                "custom", "http://localhost:8080", None,
                {"auth_type": "none"}
            )
        assert success is True


class TestProviderConfigHelperEdgeCases:
    """Additional edge-case tests for provider config helpers."""

    @pytest.mark.asyncio
    async def test_config_for_chat_with_provider_id_in_setting(self, test_session):
        """Settings with explicit provider_id uses that provider."""
        uid = await _ensure_user(test_session)
        provider = _make_provider(name="Specific", provider_type="anthropic", models=["claude-3"], is_active=True)
        test_session.add(provider)
        await test_session.flush()
        setting = _make_setting(uid, provider_id=provider.id)
        test_session.add(setting)
        await test_session.commit()

        with patch("src.api.utils.llm_provider_helper.decrypt_value", return_value="dec"):
            config = await get_provider_config_for_chat(test_session)
        assert config["provider_type"] == "anthropic"
        assert config["model_id"] == "claude-3"

    @pytest.mark.asyncio
    async def test_config_for_chat_with_temperature(self, test_session):
        uid = await _ensure_user(test_session)
        provider = _make_provider(name="Temp", is_default=True, models=["m1"])
        test_session.add(provider)
        setting = _make_setting(uid, temperature=0.9)
        test_session.add(setting)
        await test_session.commit()

        with patch("src.api.utils.llm_provider_helper.decrypt_value", return_value="dec"):
            config = await get_provider_config_for_chat(test_session)
        assert config["temperature"] == 0.9

    @pytest.mark.asyncio
    async def test_config_for_chat_decrypt_failure(self, test_session):
        uid = await _ensure_user(test_session)
        provider = _make_provider(
            name="BadKey", is_default=True, models=["m1"], api_key_encrypted="encrypted"
        )
        test_session.add(provider)
        setting = _make_setting(uid)
        test_session.add(setting)
        await test_session.commit()

        with patch("src.api.utils.llm_provider_helper.decrypt_value", side_effect=Exception("decrypt fail")):
            config = await get_provider_config_for_chat(test_session)
        assert config["provider_type"] is None

    @pytest.mark.asyncio
    async def test_config_for_chat_exception(self, test_session):
        """General exception in get_provider_config_for_chat returns defaults."""
        from sqlalchemy import text
        uid = await _ensure_user(test_session)
        setting = _make_setting(uid)
        test_session.add(setting)
        await test_session.commit()

        # Provider query will return None -> defaults
        config = await get_provider_config_for_chat(test_session)
        assert config["provider_type"] is None

    @pytest.mark.asyncio
    async def test_config_for_model_with_temperature(self, test_session):
        """Per-model override picks up temperature from settings."""
        uid = await _ensure_user(test_session)
        provider = _make_provider(name="MTemp", provider_type="openai", is_active=True, models=["gpt-4"])
        test_session.add(provider)
        setting = _make_setting(uid, temperature=0.1)
        test_session.add(setting)
        await test_session.commit()
        await test_session.refresh(provider)

        with patch("src.api.utils.llm_provider_helper.decrypt_value", return_value="key"):
            config = await get_provider_config_for_model(test_session, str(provider.id), "gpt-4")
        assert config["temperature"] == 0.1

    @pytest.mark.asyncio
    async def test_config_for_model_decrypt_failure(self, test_session):
        """Decrypt failure falls back to default config."""
        provider = _make_provider(
            name="BadDecrypt",
            provider_type="openai",
            is_active=True,
            models=["gpt-4"],
            api_key_encrypted="encrypted",
        )
        test_session.add(provider)
        await test_session.commit()
        await test_session.refresh(provider)

        with patch("src.api.utils.llm_provider_helper.decrypt_value", side_effect=Exception("fail")):
            config = await get_provider_config_for_model(test_session, str(provider.id), "gpt-4")
        # Falls back to default
        assert config["provider_type"] is None

    @pytest.mark.asyncio
    async def test_config_for_model_general_exception(self, test_session):
        """General exception falls back to default config."""
        config = await get_provider_config_for_model(test_session, "not-a-uuid", "gpt-4")
        assert config["provider_type"] is None

    @pytest.mark.asyncio
    async def test_config_for_chat_model_from_settings(self, test_session):
        """When settings has model field matching provider's models, it's used."""
        uid = await _ensure_user(test_session)
        provider = _make_provider(name="ModelSel", is_default=True, models=["m1", "m2"])
        test_session.add(provider)
        setting = _make_setting(uid, model="m2")
        test_session.add(setting)
        await test_session.commit()

        with patch("src.api.utils.llm_provider_helper.decrypt_value", return_value="key"):
            config = await get_provider_config_for_chat(test_session)
        assert config["model_id"] == "m2"


class TestLlmProviderServiceConnectionErrors:
    """Cover _test_provider_connection error paths"""

    @pytest.mark.asyncio
    async def test_health_check_connect_error(self, test_session):
        """ConnectError returns connection failed message"""
        import httpx
        provider = _make_provider(name="ConnErr", provider_type="openai",
                                  base_url="http://bad.host", api_key_encrypted="enc")
        test_session.add(provider)
        await test_session.commit()

        svc = LlmProviderService(test_session)
        with patch("src.api.services.llm_provider_service.decrypt_value", return_value="key"), \
             patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.side_effect = httpx.ConnectError("refused")
            MockClient.return_value = mock_client
            result = await svc.test_connection(provider.id)
        assert result["status"] == "error"
        assert "Connection failed" in result["message"]

    @pytest.mark.asyncio
    async def test_health_check_generic_exception(self, test_session):
        """Generic exception returns request failed message"""
        import httpx
        provider = _make_provider(name="GenErr", provider_type="openai",
                                  base_url="http://fail.host", api_key_encrypted="enc")
        test_session.add(provider)
        await test_session.commit()

        svc = LlmProviderService(test_session)
        with patch("src.api.services.llm_provider_service.decrypt_value", return_value="key"), \
             patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.side_effect = RuntimeError("weird error")
            MockClient.return_value = mock_client
            result = await svc.test_connection(provider.id)
        assert result["status"] == "error"
        assert "Request failed" in result["message"]

    @pytest.mark.asyncio
    async def test_discover_models_not_found(self, test_session):
        """Discover models for nonexistent provider"""
        svc = LlmProviderService(test_session)
        result = await svc.discover_models(uuid4())
        assert result["success"] is False
        assert result["message"] == "Provider not found"


class TestDiscoverModelsCustomProvider:
    """Cover custom provider discovery with Ollama/OpenAI fallback"""

    @pytest.mark.asyncio
    async def test_discover_custom_ollama_tags(self, test_session):
        """Custom provider tries /api/tags first (Ollama)"""
        provider = _make_provider(name="Custom", provider_type="custom",
                                  base_url="http://ollama:11434",
                                  api_key_encrypted="enc",
                                  config={"auth_type": "bearer"})
        test_session.add(provider)
        await test_session.commit()

        svc = LlmProviderService(test_session)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "llama3:latest"}]}

        with patch("src.api.services.llm_provider_service.decrypt_value", return_value="key"), \
             patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            MockClient.return_value = mock_client
            result = await svc.discover_models(provider.id)
        assert result["success"] is True
        assert "llama3:latest" in result["models"]

    @pytest.mark.asyncio
    async def test_discover_custom_fallback_openai(self, test_session):
        """Custom provider falls back to /v1/models"""
        import httpx
        provider = _make_provider(name="Custom2", provider_type="custom",
                                  base_url="http://custom:8000",
                                  api_key_encrypted="enc",
                                  config={"auth_type": "api_key_header",
                                          "auth_header_name": "X-API-Key"})
        test_session.add(provider)
        await test_session.commit()

        svc = LlmProviderService(test_session)
        # First call (Ollama) raises RequestError; second (OpenAI) succeeds
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": "custom-model-1"}]}

        call_count = 0
        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if "/api/tags" in url:
                raise httpx.RequestError("not ollama")
            return mock_response

        with patch("src.api.services.llm_provider_service.decrypt_value", return_value="key"), \
             patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = mock_get
            MockClient.return_value = mock_client
            result = await svc.discover_models(provider.id)
        assert result["success"] is True
        assert "custom-model-1" in result["models"]

    @pytest.mark.asyncio
    async def test_discover_google_models(self, test_session):
        """Google provider model discovery"""
        provider = _make_provider(name="Google", provider_type="google",
                                  api_key_encrypted="enc")
        test_session.add(provider)
        await test_session.commit()

        svc = LlmProviderService(test_session)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "models/gemini-pro", "supportedGenerationMethods": ["generateContent"]},
            ]
        }

        with patch("src.api.services.llm_provider_service.decrypt_value", return_value="key"), \
             patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            MockClient.return_value = mock_client
            result = await svc.discover_models(provider.id)
        assert result["success"] is True


class TestProviderHelperEdgeCases:
    """Cover remaining llm_provider_helper gaps"""

    @pytest.mark.asyncio
    async def test_config_for_chat_temperature_conversion_error(self, test_session):
        """Invalid temperature in settings is ignored"""
        uid = await _ensure_user(test_session)
        provider = _make_provider(name="TempErr", is_default=True)
        test_session.add(provider)
        setting = _make_setting(uid)
        setting.temperature = "not_a_number"
        test_session.add(setting)
        await test_session.commit()

        with patch("src.api.utils.llm_provider_helper.decrypt_value", return_value="key"):
            config = await get_provider_config_for_chat(test_session)
        # Should not crash, temperature just not set
        assert config["provider_type"] is not None

    @pytest.mark.asyncio
    async def test_config_for_chat_general_exception(self, test_session):
        """General exception in provider fetch returns default config"""
        uid = await _ensure_user(test_session)

        # No provider/settings at all, and break the query
        with patch("src.api.utils.llm_provider_helper.select", side_effect=RuntimeError("query err")):
            config = await get_provider_config_for_chat(test_session)
        assert config.get("provider_type") is None

    @pytest.mark.asyncio
    async def test_config_for_model_temperature_error(self, test_session):
        """Invalid temperature conversion in get_provider_config_for_model"""
        uid = await _ensure_user(test_session)
        provider = _make_provider(name="TmpModel", provider_type="openai",
                                  api_key_encrypted="enc")
        test_session.add(provider)
        setting = _make_setting(uid)
        setting.temperature = "bad"
        test_session.add(setting)
        await test_session.commit()

        with patch("src.api.utils.llm_provider_helper.decrypt_value", return_value="key"):
            config = await get_provider_config_for_model(
                test_session, str(provider.id), "gpt-4"
            )
        # Should not crash; model may fall back to default config
        assert config is not None
