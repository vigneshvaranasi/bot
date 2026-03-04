"""Security tests for the backend.

Tests OWASP Top 10 vulnerabilities: injection, broken auth, JWT tampering,
privilege escalation, IDOR, oversized payloads, and malformed inputs.
"""

import uuid
import pytest
import pytest_asyncio
import jwt as pyjwt
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, AsyncMock

from src.api.core.jwt import SECRET_KEY, ALGORITHM


class TestSQLInjection:
    """SQL injection attempts on various endpoints."""

    @pytest.mark.asyncio
    async def test_sql_injection_in_signup_email(self, client):
        """SQL injection in email field is rejected by Pydantic validation."""
        payloads = [
            "'; DROP TABLE users; --",
            "admin@example.com' OR '1'='1",
            "user@test.com'; DELETE FROM users WHERE ''='",
        ]
        for payload in payloads:
            resp = await client.post("/auth/signup", json={
                "email": payload,
                "password": "testpassword"
            })
            # Pydantic should reject invalid emails
            assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_sql_injection_in_login_email(self, client):
        """SQL injection in login email field is rejected."""
        resp = await client.post("/auth/login", json={
            "email": "admin@test.com' OR '1'='1",
            "password": "anything"
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_sql_injection_in_search_params(self, admin_client):
        """SQL injection in query parameters is handled safely."""
        ac, session, user_id = admin_client
        injection = "'; DROP TABLE users; --"

        resp = await ac.get(f"/admin/users?search={injection}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_sql_injection_in_chat_title(self, admin_client):
        """SQL injection in chat rename is safely stored."""
        ac, session, user_id = admin_client
        from src.api.db.models import Chat

        chat = Chat(user_id=user_id, title="Original")
        session.add(chat)
        await session.commit()

        injection_title = "'; DROP TABLE chats; --"
        resp = await ac.put(f"/chats/rename/{chat.id}", json={"title": injection_title})
        assert resp.status_code == 200

        await session.refresh(chat)
        assert chat.title == injection_title  # Stored as literal string, not executed


class TestJWTTampering:
    """JWT security tests."""

    @pytest.mark.asyncio
    async def test_none_algorithm_rejected(self, client):
        """Token with 'none' algorithm is rejected."""
        payload = {
            "user_id": str(uuid.uuid4()),
            "role": "admin",
            "auth_provider": "local",
            "token_version": "1",
            "jti": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        token = pyjwt.encode(payload, "", algorithm="none")
        resp = await client.get("/chats/", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_secret_rejected(self, client):
        """Token signed with wrong secret is rejected."""
        payload = {
            "user_id": str(uuid.uuid4()),
            "role": "admin",
            "auth_provider": "local",
            "token_version": "1",
            "jti": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        token = pyjwt.encode(payload, "attacker-secret-key", algorithm=ALGORITHM)
        resp = await client.get("/chats/", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_forged_admin_role_still_requires_db_user(self, test_session):
        """Forging admin role in JWT still requires valid DB user."""
        from httpx import AsyncClient, ASGITransport
        from src.api.main import app
        from src.api.db.session import get_session
        from src.api.core.jwt import create_access_token

        fake_user_id = str(uuid.uuid4())  # Not in DB
        token = create_access_token(fake_user_id, "admin", "local", 0)

        async def override_get_session():
            yield test_session

        app.dependency_overrides[get_session] = override_get_session
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as ac:
            resp = await ac.get("/chats/", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403  # User not found in DB
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_expired_token_rejected(self, client):
        """Expired JWT is rejected."""
        from src.api.core.jwt import create_access_token

        token = create_access_token(
            str(uuid.uuid4()), "admin", "local", 1,
            expires_delta=timedelta(seconds=-60)
        )
        resp = await client.get("/chats", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_malformed_bearer_token(self, client):
        """Malformed Bearer token strings are rejected."""
        malformed = [
            "Bearer ",
            "Bearer not.valid",
            "Bearer eyJ",  # Truncated
            "Basic dXNlcjpwYXNz",  # Wrong scheme
            "",
        ]
        for auth in malformed:
            resp = await client.get("/chats", headers={"Authorization": auth})
            assert resp.status_code in [401, 403, 422]


class TestIDOR:
    """Insecure Direct Object Reference tests."""

    @pytest.mark.asyncio
    async def test_cannot_access_other_users_chats(self, admin_client):
        """User cannot access another user's chats."""
        ac, session, user_id = admin_client
        from src.api.db.models import Chat, Message

        # Create chat owned by a different user
        other_user_id = uuid.uuid4()
        other_chat = Chat(user_id=other_user_id, title="Other user chat")
        session.add(other_chat)
        await session.commit()

        # Admin client (different user_id) should get their own chats, not other's
        resp = await ac.get("/chats")
        assert resp.status_code == 200
        data = resp.json()
        chat_ids = [c["id"] for c in data.get("chats", data.get("items", []))]
        assert str(other_chat.id) not in chat_ids

    @pytest.mark.asyncio
    async def test_cannot_rename_other_users_chat(self, admin_client):
        """User cannot rename another user's chat."""
        ac, session, user_id = admin_client
        from src.api.db.models import Chat

        other_chat = Chat(user_id=uuid.uuid4(), title="Not yours")
        session.add(other_chat)
        await session.commit()

        resp = await ac.put(f"/chats/rename/{other_chat.id}", json={"title": "Stolen!"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_cannot_archive_other_users_chat(self, admin_client):
        """User cannot archive another user's chat."""
        ac, session, user_id = admin_client
        from src.api.db.models import Chat

        other_chat = Chat(user_id=uuid.uuid4(), title="Not yours")
        session.add(other_chat)
        await session.commit()

        resp = await ac.delete(f"/chats/archive/{other_chat.id}")
        assert resp.status_code == 404


class TestMalformedUUIDs:
    """Tests for malformed UUID handling in path parameters."""

    @pytest.mark.asyncio
    async def test_invalid_uuid_in_chat_rename(self, admin_client):
        """Invalid UUID in chat rename returns error."""
        ac, session, user_id = admin_client
        resp = await ac.put("/chats/rename/not-a-uuid", json={"title": "test"})
        assert resp.status_code in [404, 422, 500]

    @pytest.mark.asyncio
    async def test_invalid_uuid_in_message_retrieval(self, admin_client):
        """Invalid UUID in message retrieval returns error."""
        ac, session, user_id = admin_client
        resp = await ac.get("/chats/messages/not-a-uuid")
        assert resp.status_code in [404, 422, 500]

    @pytest.mark.asyncio
    async def test_empty_uuid_in_path(self, admin_client):
        """Empty UUID in path returns error."""
        ac, session, user_id = admin_client
        resp = await ac.get("/chats/messages/")
        assert resp.status_code in [404, 405, 307]


class TestOversizedPayloads:
    """Tests for oversized and malformed request bodies."""

    @pytest.mark.asyncio
    async def test_very_long_email(self, client):
        """Extremely long email is rejected."""
        long_email = "a" * 5000 + "@example.com"
        resp = await client.post("/auth/signup", json={
            "email": long_email,
            "password": "testpassword"
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_very_long_chat_title(self, admin_client):
        """Very long chat title is handled (stored or rejected)."""
        ac, session, user_id = admin_client
        from src.api.db.models import Chat

        chat = Chat(user_id=user_id, title="Original")
        session.add(chat)
        await session.commit()

        long_title = "X" * 10000
        resp = await ac.put(f"/chats/rename/{chat.id}", json={"title": long_title})
        # Should either succeed or return 422, never 500
        assert resp.status_code in [200, 422]

    @pytest.mark.asyncio
    async def test_empty_request_body(self, client):
        """Empty request body on POST endpoints returns 422."""
        resp = await client.post("/auth/signup")
        assert resp.status_code == 422

        resp = await client.post("/auth/login")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_null_values_in_required_fields(self, client):
        """Null values in required fields returns 422."""
        resp = await client.post("/auth/signup", json={
            "email": None,
            "password": None,
        })
        assert resp.status_code == 422


class TestXSSPayloads:
    """Test that XSS payloads are safely handled."""

    @pytest.mark.asyncio
    async def test_xss_in_feedback_reason(self, admin_client):
        """XSS in feedback reason is stored as literal string."""
        ac, session, user_id = admin_client
        from src.api.db.models import Chat, Message

        chat = Chat(user_id=user_id, title="Test")
        session.add(chat)
        await session.flush()

        message = Message(chat_id=chat.id, human="test query", bot="test response")
        session.add(message)
        await session.commit()

        xss_reason = '<script>alert("xss")</script>'
        resp = await ac.post("/feedback/", json={
            "message_id": str(message.id),
            "feedback_type": "negative",
            "reason": xss_reason,
        })
        # Should store, not execute
        assert resp.status_code in [200, 201]

    @pytest.mark.asyncio
    async def test_xss_in_integration_service_name(self, admin_client):
        """XSS in integration name is stored safely."""
        ac, session, user_id = admin_client
        xss_name = '<img src=x onerror=alert("xss")>'
        resp = await ac.post("/integrations/create", json={
            "service_name": xss_name,
            "auth_type": "basic_auth",
            "config": {"url": "https://test.com"},
            "is_active": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        # Response wraps integration under \"integration\" key
        assert data["integration"]["service_name"] == xss_name  # Stored as literal, not sanitized away


class TestPrivilegeEscalation:
    """Tests for privilege escalation attempts."""

    @pytest.mark.asyncio
    async def test_normal_user_cannot_access_admin_routes(self, no_perms_client):
        """User without permissions cannot access admin routes."""
        ac, session, user_id = no_perms_client

        # Admin endpoints
        endpoints = [
            ("GET", "/admin/users"),
            ("GET", "/settings/segment/aiml"),
            ("GET", "/llm-providers/"),
            ("GET", "/permissions/sets"),
            ("GET", "/integrations/all"),
            ("GET", "/feedback/admin/list"),
            ("GET", "/feedback/admin/stats"),
        ]
        for method, path in endpoints:
            if method == "GET":
                resp = await ac.get(path)
            assert resp.status_code == 403, f"Expected 403 for {method} {path}, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_normal_user_cannot_create_providers(self, no_perms_client):
        """User without permissions cannot create LLM providers."""
        ac, session, user_id = no_perms_client
        resp = await ac.post("/llm-providers/", json={
            "name": "evil-provider",
            "provider_type": "openai",
        })
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_normal_user_cannot_create_roles(self, no_perms_client):
        """User without permissions cannot create roles."""
        ac, session, user_id = no_perms_client
        resp = await ac.post("/permissions/roles", json={
            "name": "Super Admin",
            "permission_set_codes": [],
        })
        assert resp.status_code == 403


class TestContentTypeValidation:
    """Tests for content-type validation."""

    @pytest.mark.asyncio
    async def test_non_json_content_type_rejected(self, client):
        """Non-JSON content type is rejected on JSON endpoints."""
        resp = await client.post(
            "/auth/signup",
            content="email=test@test.com&password=test",
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        assert resp.status_code == 422
