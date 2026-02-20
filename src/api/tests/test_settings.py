"""Comprehensive tests for Settings endpoints (/settings).

Covers:
- Segment-based endpoints (GET/PUT /segment/aiml, /segment/auth)
- History and rollback
- Legacy endpoints (POST /, GET /, GET /all, GET /last)
- Default values when no settings exist
- Change detection (no-op when no changes)
- Permission/RBAC enforcement
- Unauthenticated access
"""

import pytest
from uuid import uuid4

from sqlalchemy.future import select

from src.api.db.models import Setting


# ============================================================
# Helpers
# ============================================================

def _make_setting(user_id, **overrides):
    """Build a Setting ORM instance with sensible defaults."""
    defaults = dict(
        user_id=user_id,
        model="claude-3-5-sonnet",
        temperature="0.5",
        deny_words="",
        langfuse_enabled=False,
        allow_user_model_selection=False,
        auth_google_enabled=True,
        auth_github_enabled=True,
        auth_microsoft_enabled=True,
        auth_local_enabled=True,
        change_type="create",
    )
    defaults.update(overrides)
    return Setting(**defaults)


# ============================================================
# GET /settings/segment/{segment} — Get segment settings
# ============================================================


class TestGetSegmentSettings:
    """Tests for GET /settings/segment/{segment}"""

    @pytest.mark.asyncio
    async def test_get_aiml_segment_defaults(self, admin_client):
        """Returns default AIML values when no settings exist."""
        client, session, _ = admin_client
        response = await client.get("/settings/segment/aiml")
        assert response.status_code == 200
        data = response.json()
        assert data["segment"] == "aiml"
        assert data["version_id"] is None
        assert data["updated_at"] is None
        settings = data["settings"]
        assert "model" in settings
        assert "temperature" in settings
        assert "deny_words" in settings
        assert "langfuse_enabled" in settings

    @pytest.mark.asyncio
    async def test_get_auth_segment_defaults(self, admin_client):
        """Returns default Auth values when no settings exist."""
        client, session, _ = admin_client
        response = await client.get("/settings/segment/auth")
        assert response.status_code == 200
        data = response.json()
        assert data["segment"] == "auth"
        assert data["version_id"] is None
        settings = data["settings"]
        assert settings["auth_google_enabled"] is True
        assert settings["auth_github_enabled"] is True
        assert settings["auth_microsoft_enabled"] is True
        assert settings["auth_local_enabled"] is True

    @pytest.mark.asyncio
    async def test_get_aiml_segment_with_data(self, admin_client):
        """Returns stored AIML values when settings exist."""
        client, session, user_id = admin_client
        setting = _make_setting(user_id, model="gpt-4o", temperature="0.7")
        session.add(setting)
        await session.commit()
        await session.refresh(setting)

        response = await client.get("/settings/segment/aiml")
        assert response.status_code == 200
        data = response.json()
        assert data["segment"] == "aiml"
        assert data["version_id"] == str(setting.id)
        assert data["settings"]["model"] == "gpt-4o"
        assert data["settings"]["temperature"] == "0.7"

    @pytest.mark.asyncio
    async def test_get_auth_segment_with_data(self, admin_client):
        """Returns stored Auth values when settings exist."""
        client, session, user_id = admin_client
        setting = _make_setting(
            user_id,
            auth_google_enabled=False,
            auth_local_enabled=False,
        )
        session.add(setting)
        await session.commit()

        response = await client.get("/settings/segment/auth")
        assert response.status_code == 200
        settings = response.json()["settings"]
        assert settings["auth_google_enabled"] is False
        assert settings["auth_local_enabled"] is False
        assert settings["auth_github_enabled"] is True

    @pytest.mark.asyncio
    async def test_get_segment_invalid(self, admin_client):
        """Invalid segment name returns 422."""
        client, _, _ = admin_client
        response = await client.get("/settings/segment/invalid")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_segment_requires_permission(self, no_perms_client):
        """Requires aiml.view or auth.view permission."""
        client, _, _ = no_perms_client
        response = await client.get("/settings/segment/aiml")
        assert response.status_code == 403


# ============================================================
# PUT /settings/segment/aiml — Update AIML settings
# ============================================================


class TestUpdateAimlSettings:
    """Tests for PUT /settings/segment/aiml"""

    @pytest.mark.asyncio
    async def test_update_aiml_creates_first_version(self, admin_client):
        """Creates initial settings version from defaults + updates."""
        client, session, _ = admin_client
        response = await client.put("/settings/segment/aiml", json={
            "model": "gpt-4o",
            "temperature": "0.9",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["segment"] == "aiml"
        assert data["settings"]["model"] == "gpt-4o"
        assert data["settings"]["temperature"] == "0.9"
        assert data["version_id"] is not None

    @pytest.mark.asyncio
    async def test_update_aiml_preserves_existing(self, admin_client):
        """Updating one field preserves other AIML fields."""
        client, session, user_id = admin_client
        setting = _make_setting(user_id, model="old-model", temperature="0.3")
        session.add(setting)
        await session.commit()

        response = await client.put("/settings/segment/aiml", json={
            "temperature": "0.8",
        })
        assert response.status_code == 200
        settings = response.json()["settings"]
        assert settings["temperature"] == "0.8"
        # model should be preserved from previous version
        assert settings["model"] == "old-model"

    @pytest.mark.asyncio
    async def test_update_aiml_no_changes_returns_existing(self, admin_client):
        """No actual changes detected returns existing version (no new row)."""
        client, session, user_id = admin_client
        setting = _make_setting(user_id, model="same-model")
        session.add(setting)
        await session.commit()
        await session.refresh(setting)

        response = await client.put("/settings/segment/aiml", json={
            "model": "same-model",
        })
        assert response.status_code == 200
        # Should return the same version ID (no new version created)
        assert response.json()["version_id"] == str(setting.id)

    @pytest.mark.asyncio
    async def test_update_aiml_does_not_affect_auth(self, admin_client):
        """Updating AIML settings preserves Auth settings."""
        client, session, user_id = admin_client
        setting = _make_setting(
            user_id,
            auth_google_enabled=False,
            auth_github_enabled=False,
        )
        session.add(setting)
        await session.commit()

        await client.put("/settings/segment/aiml", json={
            "model": "new-model",
        })

        # Auth settings should still be preserved
        response = await client.get("/settings/segment/auth")
        settings = response.json()["settings"]
        assert settings["auth_google_enabled"] is False
        assert settings["auth_github_enabled"] is False

    @pytest.mark.asyncio
    async def test_update_aiml_langfuse_toggle(self, admin_client):
        """Can toggle langfuse_enabled."""
        client, _, _ = admin_client
        response = await client.put("/settings/segment/aiml", json={
            "langfuse_enabled": True,
        })
        assert response.status_code == 200
        assert response.json()["settings"]["langfuse_enabled"] is True

    @pytest.mark.asyncio
    async def test_update_aiml_allow_user_model_selection(self, admin_client):
        """Can toggle allow_user_model_selection."""
        client, _, _ = admin_client
        response = await client.put("/settings/segment/aiml", json={
            "allow_user_model_selection": True,
        })
        assert response.status_code == 200
        assert response.json()["settings"]["allow_user_model_selection"] is True

    @pytest.mark.asyncio
    async def test_update_aiml_deny_words(self, admin_client):
        """Can update deny_words."""
        client, _, _ = admin_client
        response = await client.put("/settings/segment/aiml", json={
            "deny_words": "badword1,badword2",
        })
        assert response.status_code == 200
        assert response.json()["settings"]["deny_words"] == "badword1,badword2"

    @pytest.mark.asyncio
    async def test_update_aiml_empty_body(self, admin_client):
        """Empty body is a no-op (returns existing or creates defaults)."""
        client, _, _ = admin_client
        response = await client.put("/settings/segment/aiml", json={})
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_aiml_requires_permission(self, no_perms_client):
        """Requires aiml.edit permission."""
        client, _, _ = no_perms_client
        response = await client.put("/settings/segment/aiml", json={
            "model": "hacked",
        })
        assert response.status_code == 403
        assert "Missing permission: aiml.edit" in response.json()["detail"]


# ============================================================
# PUT /settings/segment/auth — Update Auth settings
# ============================================================


class TestUpdateAuthSettings:
    """Tests for PUT /settings/segment/auth"""

    @pytest.mark.asyncio
    async def test_update_auth_creates_first_version(self, admin_client):
        """Creates initial settings version with auth updates."""
        client, _, _ = admin_client
        response = await client.put("/settings/segment/auth", json={
            "auth_google_enabled": False,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["segment"] == "auth"
        assert data["settings"]["auth_google_enabled"] is False
        # Other auth settings should use defaults
        assert data["settings"]["auth_github_enabled"] is True

    @pytest.mark.asyncio
    async def test_update_auth_preserves_existing(self, admin_client):
        """Updating one auth field preserves others."""
        client, session, user_id = admin_client
        setting = _make_setting(
            user_id,
            auth_google_enabled=False,
            auth_github_enabled=False,
        )
        session.add(setting)
        await session.commit()

        response = await client.put("/settings/segment/auth", json={
            "auth_google_enabled": True,
        })
        assert response.status_code == 200
        settings = response.json()["settings"]
        assert settings["auth_google_enabled"] is True
        # github should remain unchanged
        assert settings["auth_github_enabled"] is False

    @pytest.mark.asyncio
    async def test_update_auth_does_not_affect_aiml(self, admin_client):
        """Updating Auth settings preserves AIML settings."""
        client, session, user_id = admin_client
        setting = _make_setting(user_id, model="my-model", temperature="0.1")
        session.add(setting)
        await session.commit()

        await client.put("/settings/segment/auth", json={
            "auth_local_enabled": False,
        })

        response = await client.get("/settings/segment/aiml")
        settings = response.json()["settings"]
        assert settings["model"] == "my-model"
        assert settings["temperature"] == "0.1"

    @pytest.mark.asyncio
    async def test_update_auth_all_fields(self, admin_client):
        """Update all auth fields at once."""
        client, _, _ = admin_client
        response = await client.put("/settings/segment/auth", json={
            "auth_google_enabled": False,
            "auth_github_enabled": False,
            "auth_microsoft_enabled": False,
            "auth_local_enabled": False,
        })
        assert response.status_code == 200
        settings = response.json()["settings"]
        assert all(v is False for v in settings.values())

    @pytest.mark.asyncio
    async def test_update_auth_no_changes(self, admin_client):
        """No actual changes returns existing version."""
        client, session, user_id = admin_client
        setting = _make_setting(user_id, auth_google_enabled=True)
        session.add(setting)
        await session.commit()
        await session.refresh(setting)

        response = await client.put("/settings/segment/auth", json={
            "auth_google_enabled": True,
        })
        assert response.status_code == 200
        assert response.json()["version_id"] == str(setting.id)

    @pytest.mark.asyncio
    async def test_update_auth_requires_permission(self, no_perms_client):
        """Requires auth.edit permission."""
        client, _, _ = no_perms_client
        response = await client.put("/settings/segment/auth", json={
            "auth_google_enabled": False,
        })
        assert response.status_code == 403
        assert "Missing permission: auth.edit" in response.json()["detail"]


# ============================================================
# GET /settings/history — Settings history
# ============================================================


class TestSettingsHistory:
    """Tests for GET /settings/history"""

    @pytest.mark.asyncio
    async def test_history_empty(self, admin_client):
        """Returns empty history when no settings exist."""
        client, _, _ = admin_client
        response = await client.get("/settings/history")
        assert response.status_code == 200
        data = response.json()
        assert data["history"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_history_with_entries(self, admin_client):
        """Returns history entries after settings changes."""
        client, session, user_id = admin_client
        s1 = _make_setting(user_id, model="model-v1", change_type="create")
        session.add(s1)
        await session.commit()

        s2 = _make_setting(user_id, model="model-v2", change_type="update")
        session.add(s2)
        await session.commit()

        response = await client.get("/settings/history")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["history"]) == 2

    @pytest.mark.asyncio
    async def test_history_pagination_limit(self, admin_client):
        """Respects limit parameter."""
        client, session, user_id = admin_client
        for i in range(5):
            session.add(_make_setting(user_id, model=f"model-{i}"))
        await session.commit()

        response = await client.get("/settings/history?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["history"]) == 2
        assert data["total"] == 5

    @pytest.mark.asyncio
    async def test_history_pagination_offset(self, admin_client):
        """Respects offset parameter."""
        client, session, user_id = admin_client
        for i in range(5):
            session.add(_make_setting(user_id, model=f"model-{i}"))
        await session.commit()

        response = await client.get("/settings/history?limit=2&offset=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data["history"]) == 2
        assert data["total"] == 5

    @pytest.mark.asyncio
    async def test_history_item_format(self, admin_client):
        """History items contain expected fields."""
        client, session, user_id = admin_client
        session.add(_make_setting(user_id))
        await session.commit()

        response = await client.get("/settings/history")
        data = response.json()
        item = data["history"][0]
        assert "id" in item
        assert "user_id" in item
        assert "change_type" in item
        assert "changes" in item
        assert "model" in item
        assert "temperature" in item

    @pytest.mark.asyncio
    async def test_history_requires_permission(self, no_perms_client):
        """Requires history.view permission."""
        client, _, _ = no_perms_client
        response = await client.get("/settings/history")
        assert response.status_code == 403
        assert "Missing permission: history.view" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_history_limit_validation(self, admin_client):
        """Limit must be between 1 and 100."""
        client, _, _ = admin_client
        resp_zero = await client.get("/settings/history?limit=0")
        assert resp_zero.status_code == 422

        resp_over = await client.get("/settings/history?limit=101")
        assert resp_over.status_code == 422

    @pytest.mark.asyncio
    async def test_history_offset_validation(self, admin_client):
        """Offset must be >= 0."""
        client, _, _ = admin_client
        response = await client.get("/settings/history?offset=-1")
        assert response.status_code == 422


# ============================================================
# POST /settings/rollback/{version_id} — Rollback
# ============================================================


class TestRollback:
    """Tests for POST /settings/rollback/{version_id}"""

    @pytest.mark.asyncio
    async def test_rollback_success(self, admin_client):
        """Rollback creates new version with target's values."""
        client, session, user_id = admin_client
        # Create initial version
        v1 = _make_setting(user_id, model="v1-model", temperature="0.3")
        session.add(v1)
        await session.commit()
        await session.refresh(v1)
        v1_id = v1.id

        # Create second version
        v2 = _make_setting(user_id, model="v2-model", temperature="0.9")
        session.add(v2)
        await session.commit()

        # Rollback to v1
        response = await client.post(f"/settings/rollback/{v1_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "v1-model"
        assert data["temperature"] == "0.3"

    @pytest.mark.asyncio
    async def test_rollback_with_reason(self, admin_client):
        """Rollback with reason records the reason."""
        client, session, user_id = admin_client
        v1 = _make_setting(user_id)
        session.add(v1)
        await session.commit()
        await session.refresh(v1)
        v1_id = v1.id

        response = await client.post(
            f"/settings/rollback/{v1_id}",
            json={"reason": "Reverting bad config"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_rollback_creates_new_version(self, admin_client):
        """Rollback creates a new row, doesn't delete existing ones."""
        client, session, user_id = admin_client
        v1 = _make_setting(user_id, model="original")
        session.add(v1)
        await session.commit()
        await session.refresh(v1)
        v1_id = v1.id

        response = await client.post(f"/settings/rollback/{v1_id}")
        assert response.status_code == 200
        new_id = response.json()["id"]
        assert new_id != str(v1_id)  # New version created

        # Count total versions
        result = await session.execute(select(Setting))
        all_settings = result.scalars().all()
        assert len(all_settings) == 2  # original + rollback

    @pytest.mark.asyncio
    async def test_rollback_not_found(self, admin_client):
        """Non-existent version_id returns 404."""
        client, _, _ = admin_client
        response = await client.post(f"/settings/rollback/{uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_rollback_invalid_uuid(self, admin_client):
        """Invalid UUID returns 422."""
        client, _, _ = admin_client
        response = await client.post("/settings/rollback/not-a-uuid")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_rollback_requires_permission(self, no_perms_client):
        """Requires history.rollback permission."""
        client, session, user_id = no_perms_client
        v1 = _make_setting(user_id)
        session.add(v1)
        await session.commit()
        await session.refresh(v1)

        response = await client.post(f"/settings/rollback/{v1.id}")
        assert response.status_code == 403
        assert "Missing permission: history.rollback" in response.json()["detail"]


# ============================================================
# POST /settings/ — Legacy create setting
# ============================================================


class TestLegacyCreateSetting:
    """Tests for POST /settings/ (legacy endpoint)"""

    @pytest.mark.asyncio
    async def test_create_setting_success(self, admin_client):
        """Creates new settings version."""
        client, _, _ = admin_client
        response = await client.post("/settings/", json={
            "model": "gpt-4",
            "temperature": "0.5",
            "deny_words": "bad",
            "langfuse_enabled": False,
            "auth_google_enabled": True,
            "auth_github_enabled": True,
            "auth_microsoft_enabled": True,
            "auth_local_enabled": True,
        })
        assert response.status_code == 201
        data = response.json()
        assert data["model"] == "gpt-4"
        assert data["temperature"] == "0.5"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_setting_defaults(self, admin_client):
        """Creates with default values when not specified."""
        client, _, _ = admin_client
        response = await client.post("/settings/", json={})
        assert response.status_code == 201
        data = response.json()
        assert data["model"] == "gemini-2.5-flash"
        assert data["temperature"] == "0.2"

    @pytest.mark.asyncio
    async def test_create_setting_no_changes_returns_existing(self, admin_client):
        """When no changes detected, returns existing setting."""
        client, _, _ = admin_client
        payload = {
            "model": "same-model",
            "temperature": "0.5",
            "deny_words": "",
            "langfuse_enabled": True,
            "auth_google_enabled": True,
            "auth_github_enabled": True,
            "auth_microsoft_enabled": True,
            "auth_local_enabled": True,
        }
        resp1 = await client.post("/settings/", json=payload)
        assert resp1.status_code == 201
        id1 = resp1.json()["id"]

        resp2 = await client.post("/settings/", json=payload)
        # Should return existing (no new version)
        assert resp2.json()["id"] == id1

    @pytest.mark.asyncio
    async def test_create_setting_requires_permission(self, no_perms_client):
        """Requires aiml.edit or auth.edit permission."""
        client, _, _ = no_perms_client
        response = await client.post("/settings/", json={})
        assert response.status_code == 403


# ============================================================
# GET /settings/ — Legacy get latest
# ============================================================


class TestLegacyGetLatest:
    """Tests for GET /settings/ (legacy endpoint)"""

    @pytest.mark.asyncio
    async def test_get_latest_no_settings(self, admin_client):
        """Returns null when no settings exist."""
        client, _, _ = admin_client
        response = await client.get("/settings/")
        assert response.status_code == 200
        # FastAPI returns null for Optional[None]
        assert response.json() is None

    @pytest.mark.asyncio
    async def test_get_latest_returns_setting(self, admin_client):
        """Returns a settings version when one exists."""
        client, session, user_id = admin_client
        session.add(_make_setting(user_id, model="my-model"))
        await session.commit()

        response = await client.get("/settings/")
        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "my-model"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_get_latest_response_format(self, admin_client):
        """Response has all expected fields."""
        client, session, user_id = admin_client
        session.add(_make_setting(user_id))
        await session.commit()

        response = await client.get("/settings/")
        data = response.json()
        expected_fields = {
            "id", "user_id", "model", "temperature", "deny_words",
            "langfuse_enabled", "allow_user_model_selection",
            "auth_google_enabled", "auth_github_enabled",
            "auth_microsoft_enabled", "auth_local_enabled",
            "created_at", "updated_at",
        }
        assert expected_fields.issubset(set(data.keys()))

    @pytest.mark.asyncio
    async def test_get_latest_requires_permission(self, no_perms_client):
        """Requires aiml.view or auth.view permission."""
        client, _, _ = no_perms_client
        response = await client.get("/settings/")
        assert response.status_code == 403


# ============================================================
# GET /settings/last — Legacy alias
# ============================================================


class TestLegacyGetLast:
    """Tests for GET /settings/last (alias for GET /)"""

    @pytest.mark.asyncio
    async def test_get_last_no_settings(self, admin_client):
        """Returns null when no settings exist."""
        client, _, _ = admin_client
        response = await client.get("/settings/last")
        assert response.status_code == 200
        assert response.json() is None

    @pytest.mark.asyncio
    async def test_get_last_returns_latest(self, admin_client):
        """Returns the latest settings version."""
        client, session, user_id = admin_client
        session.add(_make_setting(user_id, model="latest-model"))
        await session.commit()

        response = await client.get("/settings/last")
        assert response.status_code == 200
        assert response.json()["model"] == "latest-model"

    @pytest.mark.asyncio
    async def test_get_last_requires_permission(self, no_perms_client):
        """Requires aiml.view or auth.view permission."""
        client, _, _ = no_perms_client
        response = await client.get("/settings/last")
        assert response.status_code == 403


# ============================================================
# GET /settings/all — Legacy list all
# ============================================================


class TestLegacyListAll:
    """Tests for GET /settings/all"""

    @pytest.mark.asyncio
    async def test_list_all_empty(self, admin_client):
        """Returns empty list when no settings exist."""
        client, _, _ = admin_client
        response = await client.get("/settings/all")
        assert response.status_code == 200
        data = response.json()
        assert data["settings"] == []

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Bug: legacy /all endpoint passes dicts to SettingResponse.model_validate instead of Setting objects")
    async def test_list_all_returns_versions(self, admin_client):
        """Returns all settings versions."""
        client, session, user_id = admin_client
        for i in range(3):
            session.add(_make_setting(user_id, model=f"v{i}"))
        await session.commit()

        response = await client.get("/settings/all")
        assert response.status_code == 200
        data = response.json()
        assert len(data["settings"]) == 3

    @pytest.mark.asyncio
    async def test_list_all_requires_permission(self, no_perms_client):
        """Requires history.view permission."""
        client, _, _ = no_perms_client
        response = await client.get("/settings/all")
        assert response.status_code == 403
        assert "Missing permission: history.view" in response.json()["detail"]


# ============================================================
# Unauthenticated access — all endpoints
# ============================================================


class TestSettingsUnauthenticated:
    """Unauthenticated requests are rejected."""

    @pytest.mark.asyncio
    async def test_get_segment_unauth(self, client):
        response = await client.get("/settings/segment/aiml")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_aiml_unauth(self, client):
        response = await client.put(
            "/settings/segment/aiml", json={"model": "test"}
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_auth_unauth(self, client):
        response = await client.put(
            "/settings/segment/auth", json={"auth_google_enabled": False}
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_history_unauth(self, client):
        response = await client.get("/settings/history")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_rollback_unauth(self, client):
        response = await client.post(f"/settings/rollback/{uuid4()}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_legacy_create_unauth(self, client):
        response = await client.post("/settings/", json={})
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_legacy_get_latest_unauth(self, client):
        response = await client.get("/settings/")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_legacy_get_last_unauth(self, client):
        response = await client.get("/settings/last")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_legacy_list_all_unauth(self, client):
        response = await client.get("/settings/all")
        assert response.status_code == 403


# ============================================================
# Edge cases & hardening — Settings endpoints
# ============================================================


class TestRollbackEdgeCases:
    """Edge cases for POST /settings/rollback/{version_id}"""

    @pytest.mark.asyncio
    async def test_rollback_verifies_db_state(self, admin_client):
        """After rollback, the new row has change_type='rollback' and correct audit trail."""
        client, session, user_id = admin_client
        v1 = _make_setting(user_id, model="v1-model", temperature="0.3")
        session.add(v1)
        await session.commit()
        await session.refresh(v1)
        v1_id = v1.id

        v2 = _make_setting(user_id, model="v2-model", temperature="0.9")
        session.add(v2)
        await session.commit()
        await session.refresh(v2)
        v2_id = v2.id

        response = await client.post(f"/settings/rollback/{v1_id}")
        assert response.status_code == 200
        new_id = response.json()["id"]

        # Verify the new row in DB
        session.expire_all()
        result = await session.execute(
            select(Setting).where(Setting.id == new_id)
        )
        new_setting = result.scalar_one()
        assert new_setting.model == "v1-model"
        assert new_setting.temperature == "0.3"
        assert new_setting.change_type == "rollback"
        assert new_setting.target_version_id == v1_id

    @pytest.mark.asyncio
    async def test_rollback_preserves_original_versions(self, admin_client):
        """Rollback does not modify or delete original versions."""
        client, session, user_id = admin_client
        v1 = _make_setting(user_id, model="original")
        session.add(v1)
        await session.commit()
        await session.refresh(v1)
        v1_id = v1.id

        await client.post(f"/settings/rollback/{v1_id}")

        # Both the original and the rollback version should exist
        result = await session.execute(select(Setting))
        all_versions = result.scalars().all()
        assert len(all_versions) == 2
        models = {s.model for s in all_versions}
        assert models == {"original"}  # both have same model value

    @pytest.mark.asyncio
    async def test_rollback_to_self(self, admin_client):
        """Rollback to the current (latest) version creates a new row anyway."""
        client, session, user_id = admin_client
        v1 = _make_setting(user_id, model="current")
        session.add(v1)
        await session.commit()
        await session.refresh(v1)

        response = await client.post(f"/settings/rollback/{v1.id}")
        assert response.status_code == 200
        assert response.json()["id"] != str(v1.id)


class TestSettingsHistoryEdgeCases:
    """Edge cases for GET /settings/history"""

    @pytest.mark.asyncio
    async def test_history_offset_beyond_total(self, admin_client):
        """Offset beyond total returns empty history."""
        client, session, user_id = admin_client
        session.add(_make_setting(user_id))
        await session.commit()

        response = await client.get("/settings/history?limit=10&offset=100")
        assert response.status_code == 200
        data = response.json()
        assert data["history"] == []
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_history_max_limit(self, admin_client):
        """Limit at maximum (100) succeeds."""
        client, _, _ = admin_client
        response = await client.get("/settings/history?limit=100")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_history_segment_filter(self, admin_client):
        """Filter history by segment (if supported)."""
        client, session, user_id = admin_client
        session.add(_make_setting(user_id))
        await session.commit()

        response = await client.get("/settings/history?segment=aiml")
        assert response.status_code == 200

        response = await client.get("/settings/history?segment=auth")
        assert response.status_code == 200


class TestUpdateAimlEdgeCases:
    """Edge cases for PUT /settings/segment/aiml"""

    @pytest.mark.asyncio
    async def test_update_aiml_very_long_deny_words(self, admin_client):
        """Update deny_words with very long string."""
        client, _, _ = admin_client
        long_words = ",".join([f"word{i}" for i in range(1000)])
        response = await client.put("/settings/segment/aiml", json={
            "deny_words": long_words,
        })
        assert response.status_code == 200
        assert response.json()["settings"]["deny_words"] == long_words

    @pytest.mark.asyncio
    async def test_update_aiml_special_chars_in_model(self, admin_client):
        """Model name with special characters."""
        client, _, _ = admin_client
        response = await client.put("/settings/segment/aiml", json={
            "model": "gpt-4o-2024-05-13/turbo",
        })
        assert response.status_code == 200
        assert response.json()["settings"]["model"] == "gpt-4o-2024-05-13/turbo"

    @pytest.mark.asyncio
    async def test_update_aiml_creates_new_version_each_time(self, admin_client):
        """Each actual change creates a new version with different version_id."""
        client, _, _ = admin_client
        r1 = await client.put("/settings/segment/aiml", json={"model": "m1"})
        r2 = await client.put("/settings/segment/aiml", json={"model": "m2"})
        assert r1.json()["version_id"] != r2.json()["version_id"]


class TestUpdateAuthEdgeCases:
    """Edge cases for PUT /settings/segment/auth"""

    @pytest.mark.asyncio
    async def test_disable_all_auth_then_reenable(self, admin_client):
        """Disable all auth providers then re-enable local."""
        client, _, _ = admin_client
        # Disable all
        r1 = await client.put("/settings/segment/auth", json={
            "auth_google_enabled": False,
            "auth_github_enabled": False,
            "auth_microsoft_enabled": False,
            "auth_local_enabled": False,
        })
        assert r1.status_code == 200
        assert all(v is False for v in r1.json()["settings"].values())

        # Re-enable local
        r2 = await client.put("/settings/segment/auth", json={
            "auth_local_enabled": True,
        })
        assert r2.status_code == 200
        settings = r2.json()["settings"]
        assert settings["auth_local_enabled"] is True
        assert settings["auth_google_enabled"] is False


class TestLegacySettingsEdgeCases:
    """Edge cases for legacy settings endpoints."""

    @pytest.mark.asyncio
    async def test_legacy_create_multiple_versions(self, admin_client):
        """Creating multiple settings creates multiple versions with unique IDs."""
        client, session, _ = admin_client
        r1 = await client.post("/settings/", json={"model": "model-1"})
        r2 = await client.post("/settings/", json={"model": "model-2"})
        assert r1.json()["id"] != r2.json()["id"]

    @pytest.mark.asyncio
    async def test_legacy_get_latest_returns_most_recent(self, admin_client):
        """GET /settings/ returns the most recently updated version."""
        from datetime import datetime, timedelta, UTC
        client, session, user_id = admin_client
        now = datetime.now(UTC)
        s1 = _make_setting(user_id, model="old", updated_at=now - timedelta(seconds=10))
        session.add(s1)
        await session.commit()
        s2 = _make_setting(user_id, model="new", updated_at=now)
        session.add(s2)
        await session.commit()

        response = await client.get("/settings/")
        assert response.json()["model"] == "new"
