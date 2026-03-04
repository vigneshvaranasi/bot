"""Comprehensive tests for Auth endpoints (/auth) and OAuth providers.

Covers:
- Signup (POST /auth/signup)
- Login (POST /auth/login)
- Get current user (GET /auth/me)
- Update password (POST /auth/password)
- Logout (POST /auth/logout)
- List providers (GET /auth/providers)
- OAuth login (GET /auth/oauth/{provider})
- OAuth callback (GET /auth/oauth/{provider}/callback)
- Unauthenticated access
- OAuth provider unit tests (GitHub, Google, Microsoft)
"""

import pytest
from typing import Any, Dict, List
from urllib.parse import urlparse, parse_qs
from uuid import uuid4
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
import httpx
from fastapi import HTTPException

from src.api.db.models import User, Role, AuthIdentity, Setting
from src.api.core.security import get_password_hash


# ============================================================
# Helpers
# ============================================================

async def _create_role(session, name="Basic User"):
    role = Role(name=name)
    session.add(role)
    await session.commit()
    await session.refresh(role)
    return role


async def _create_user_with_password(session, *, email=None, password="TestPass123!", role=None):
    """Create a user with a local auth identity (password)."""
    if email is None:
        email = f"user_{uuid4().hex[:8]}@test.com"
    if role is None:
        role = await _create_role(session)

    user = User(email=email, role_id=role.id, is_active=True)
    session.add(user)
    await session.flush()

    identity = AuthIdentity(
        user_id=user.id,
        provider="local",
        password_hash=get_password_hash(password),
    )
    session.add(identity)
    await session.commit()
    await session.refresh(user)
    return user, role


async def _create_setting_with_auth(session, *, auth_local=True, auth_google=True,
                                     auth_github=True, auth_microsoft=True):
    """Create a Setting row with the given auth flags.

    A User is created as the owner since Setting.user_id is NOT NULL.
    """
    owner = User(email=f"settings_owner_{uuid4().hex[:6]}@test.com", is_active=True)
    session.add(owner)
    await session.flush()
    setting = Setting(
        user_id=owner.id,
        auth_local_enabled=auth_local,
        auth_google_enabled=auth_google,
        auth_github_enabled=auth_github,
        auth_microsoft_enabled=auth_microsoft,
        change_type="create",
    )
    session.add(setting)
    await session.commit()
    return setting


# ============================================================
# POST /auth/signup — Signup
# ============================================================


class TestSignup:
    """Tests for POST /auth/signup"""

    @pytest.mark.asyncio
    async def test_signup_success(self, client, test_session):
        """Create a new user via signup."""
        # Need a default role
        await _create_role(test_session, "Basic User")

        response = await client.post("/auth/signup", json={
            "email": "newuser@test.com",
            "password": "testpassword",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "User created successfully"

    @pytest.mark.asyncio
    async def test_signup_duplicate_email(self, client, test_session):
        """Signup with existing email fails."""
        role = await _create_role(test_session)
        await _create_user_with_password(test_session, email="dup@test.com", role=role)

        response = await client.post("/auth/signup", json={
            "email": "dup@test.com",
            "password": "testpassword",
        })
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_signup_invalid_email(self, client):
        """Signup with invalid email is rejected."""
        response = await client.post("/auth/signup", json={
            "email": "not-an-email",
            "password": "testpassword",
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_signup_disabled_local_auth(self, client, test_session):
        """Signup fails when local auth is disabled."""
        await _create_setting_with_auth(test_session, auth_local=False)

        response = await client.post("/auth/signup", json={
            "email": "new@test.com",
            "password": "testpassword",
        })
        assert response.status_code == 403
        assert "disabled" in response.json()["detail"].lower()


# ============================================================
# POST /auth/login — Login
# ============================================================


class TestLogin:
    """Tests for POST /auth/login"""

    @pytest.mark.asyncio
    async def test_login_success(self, client, test_session):
        """Login with valid credentials returns a token."""
        user, role = await _create_user_with_password(
            test_session, email="login@test.com", password="mypassword"
        )

        response = await client.post("/auth/login", json={
            "email": "login@test.com",
            "password": "mypassword",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["email"] == "login@test.com"
        assert data["role"] == role.name

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client, test_session):
        """Login with wrong password fails."""
        await _create_user_with_password(
            test_session, email="wrongpw@test.com", password="correct"
        )

        response = await client.post("/auth/login", json={
            "email": "wrongpw@test.com",
            "password": "incorrect",
        })
        assert response.status_code == 400
        assert "Invalid" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client):
        """Login with non-existent email fails."""
        response = await client.post("/auth/login", json={
            "email": "nobody@test.com",
            "password": "whatever",
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_login_inactive_user(self, client, test_session):
        """Login with inactive user fails."""
        role = await _create_role(test_session)
        user = User(email="inactive@test.com", role_id=role.id, is_active=False)
        test_session.add(user)
        await test_session.flush()

        identity = AuthIdentity(
            user_id=user.id,
            provider="local",
            password_hash=get_password_hash("password"),
        )
        test_session.add(identity)
        await test_session.commit()

        response = await client.post("/auth/login", json={
            "email": "inactive@test.com",
            "password": "password",
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_login_disabled_local_auth(self, client, test_session):
        """Login fails when local auth is disabled."""
        await _create_setting_with_auth(test_session, auth_local=False)

        response = await client.post("/auth/login", json={
            "email": "test@test.com",
            "password": "testpassword",
        })
        assert response.status_code == 403


# ============================================================
# GET /auth/me — Current user profile
# ============================================================


class TestGetMe:
    """Tests for GET /auth/me"""

    @pytest.mark.asyncio
    async def test_get_me_success(self, admin_client):
        """Authenticated user can get their profile."""
        client, session, user_id = admin_client
        # Create the user + role in DB (admin_client overrides auth but /me reads from DB)
        role = await _create_role(session, "admin")
        user = User(id=user_id, email="me@test.com", role_id=role.id, is_active=True)
        session.add(user)
        await session.flush()
        identity = AuthIdentity(user_id=user.id, provider="local")
        session.add(identity)
        await session.commit()

        response = await client.get("/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "me@test.com"
        assert data["is_active"] is True
        assert "local" in data["auth_identities"]

    @pytest.mark.asyncio
    async def test_get_me_unauthenticated(self, client):
        """Unauthenticated request to /me returns 403."""
        response = await client.get("/auth/me")
        assert response.status_code == 403


# ============================================================
# POST /auth/password — Update password
# ============================================================


class TestUpdatePassword:
    """Tests for POST /auth/password"""

    @pytest.mark.asyncio
    async def test_update_password_creates_local_identity(self, admin_client):
        """Setting password for user without local identity creates one."""
        client, session, user_id = admin_client
        # Create user in DB without local identity
        role = await _create_role(session)
        user = User(id=user_id, email="nolocal@test.com", role_id=role.id, is_active=True)
        session.add(user)
        await session.commit()

        response = await client.post("/auth/password", json={
            "password": "newpassword123",
        })
        assert response.status_code == 200
        assert response.json()["message"] == "Password updated successfully"

    @pytest.mark.asyncio
    async def test_update_password_updates_existing(self, admin_client):
        """Setting password for user with existing local identity updates it."""
        client, session, user_id = admin_client
        role = await _create_role(session)
        user = User(id=user_id, email="haslocal@test.com", role_id=role.id, is_active=True)
        session.add(user)
        await session.flush()
        identity = AuthIdentity(
            user_id=user.id, provider="local",
            password_hash=get_password_hash("oldpassword"),
        )
        session.add(identity)
        await session.commit()

        response = await client.post("/auth/password", json={
            "password": "updatedpassword",
        })
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_password_unauthenticated(self, client):
        """Unauthenticated request to update password returns 403."""
        response = await client.post("/auth/password", json={
            "password": "whatever",
        })
        assert response.status_code == 403


# ============================================================
# POST /auth/logout — Logout
# ============================================================


class TestLogout:
    """Tests for POST /auth/logout"""

    @pytest.mark.asyncio
    async def test_logout_success(self, admin_client):
        """Authenticated user can logout."""
        client, _, _ = admin_client
        response = await client.post("/auth/logout")
        assert response.status_code == 200
        assert response.json()["message"] == "Logged out successfully"

    @pytest.mark.asyncio
    async def test_logout_unauthenticated(self, client):
        """Unauthenticated request to logout returns 403."""
        response = await client.post("/auth/logout")
        assert response.status_code == 403


# ============================================================
# GET /auth/providers — List enabled auth providers
# ============================================================


class TestListProviders:
    """Tests for GET /auth/providers"""

    @pytest.mark.asyncio
    async def test_list_providers_defaults(self, client):
        """No settings = all providers enabled."""
        response = await client.get("/auth/providers")
        assert response.status_code == 200
        providers = response.json()["providers"]
        assert "local" in providers
        assert "google" in providers
        assert "github" in providers
        assert "microsoft" in providers

    @pytest.mark.asyncio
    async def test_list_providers_some_disabled(self, client, test_session):
        """When settings disable some providers, they're excluded."""
        await _create_setting_with_auth(
            test_session, auth_local=True, auth_google=False,
            auth_github=True, auth_microsoft=False,
        )

        response = await client.get("/auth/providers")
        providers = response.json()["providers"]
        assert "local" in providers
        assert "github" in providers
        assert "google" not in providers
        assert "microsoft" not in providers

    @pytest.mark.asyncio
    async def test_list_providers_all_disabled(self, client, test_session):
        """All providers disabled returns empty list."""
        await _create_setting_with_auth(
            test_session, auth_local=False, auth_google=False,
            auth_github=False, auth_microsoft=False,
        )

        response = await client.get("/auth/providers")
        assert response.json()["providers"] == []


# ============================================================
# GET /auth/oauth/{provider} — OAuth login (requires provider setup)
# ============================================================


class TestOAuthLogin:
    """Tests for GET /auth/oauth/{provider}"""

    @pytest.mark.asyncio
    async def test_oauth_login_provider_not_enabled(self, client, test_session):
        """OAuth login for non-configured provider fails."""
        # No AuthProvider records exist, so get_provider_instance raises
        response = await client.get("/auth/oauth/google")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_oauth_login_disabled_provider(self, client, test_session):
        """OAuth login for disabled provider returns 403."""
        await _create_setting_with_auth(test_session, auth_google=False)

        response = await client.get("/auth/oauth/google")
        assert response.status_code == 403


# ============================================================
# GET /auth/oauth/{provider}/callback — OAuth callback
# ============================================================


class TestOAuthCallback:
    """Tests for GET /auth/oauth/{provider}/callback"""

    @pytest.mark.asyncio
    async def test_oauth_callback_invalid_state(self, client):
        """OAuth callback with invalid state fails."""
        response = await client.get(
            "/auth/oauth/google/callback",
            params={"code": "fake_code", "state": "invalid_state"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_oauth_callback_disabled_provider(self, client, test_session):
        """OAuth callback for disabled provider returns 403."""
        await _create_setting_with_auth(test_session, auth_google=False)

        response = await client.get(
            "/auth/oauth/google/callback",
            params={"code": "fake_code", "state": "fake_state"},
        )
        assert response.status_code == 403


# ============================================================
# Edge cases & hardening — Auth endpoints
# ============================================================


class TestLoginTokenClaims:
    """Verify JWT token claims after successful login."""

    @pytest.mark.asyncio
    async def test_login_token_contains_expected_claims(self, client, test_session):
        """Token returned from login should be a valid JWT with correct claims."""
        import jwt as pyjwt
        user, role = await _create_user_with_password(
            test_session, email="claims@test.com", password="mypassword"
        )

        response = await client.post("/auth/login", json={
            "email": "claims@test.com",
            "password": "mypassword",
        })
        assert response.status_code == 200
        token = response.json()["access_token"]

        # Decode without verification to inspect claims
        payload = pyjwt.decode(
            token, "test-secret-key-for-testing-only", algorithms=["HS256"]
        )
        assert payload["user_id"] == str(user.id)
        assert payload["role"] == role.name
        assert payload["auth_provider"] == "local"
        assert "exp" in payload
        assert "iat" in payload
        assert "jti" in payload

    @pytest.mark.asyncio
    async def test_login_response_user_id_matches_db(self, client, test_session):
        """Login response user_id matches the DB user."""
        user, _ = await _create_user_with_password(
            test_session, email="matchid@test.com", password="pw123"
        )

        response = await client.post("/auth/login", json={
            "email": "matchid@test.com",
            "password": "pw123",
        })
        assert response.status_code == 200
        assert response.json()["user_id"] == str(user.id)


class TestSignupEdgeCases:
    """Edge cases for signup endpoint."""

    @pytest.mark.asyncio
    async def test_signup_case_sensitive_email(self, client, test_session):
        """Email comparison — signup with different casing."""
        role = await _create_role(test_session)
        await _create_user_with_password(
            test_session, email="Case@Test.com", role=role
        )
        # Try same email in different case — Pydantic EmailStr normalises to lowercase,
        # so "Case@Test.com" becomes "case@test.com". They should coexist or collide
        # depending on the original stored value.
        response = await client.post("/auth/signup", json={
            "email": "case@test.com",
            "password": "testpassword",
        })
        # If original was stored normalised, this is a duplicate
        assert response.status_code in (200, 400)

    @pytest.mark.asyncio
    async def test_signup_very_long_email(self, client, test_session):
        """Signup with extremely long email."""
        await _create_role(test_session, "Basic User")
        long_local = "a" * 200
        response = await client.post("/auth/signup", json={
            "email": f"{long_local}@test.com",
            "password": "testpassword",
        })
        # Should either succeed or fail validation, not crash
        assert response.status_code in (200, 422)

    @pytest.mark.asyncio
    async def test_signup_empty_password(self, client, test_session):
        """Signup with empty password."""
        await _create_role(test_session, "Basic User")
        response = await client.post("/auth/signup", json={
            "email": "empty_pw@test.com",
            "password": "",
        })
        # Empty password may or may not be accepted depending on validation config
        assert response.status_code in (200, 422)

    @pytest.mark.asyncio
    async def test_signup_missing_password_field(self, client):
        """Signup without password field returns 422."""
        response = await client.post("/auth/signup", json={
            "email": "no_pw@test.com",
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_signup_extra_fields_ignored(self, client, test_session):
        """Extra fields in signup body are ignored."""
        await _create_role(test_session, "Basic User")
        response = await client.post("/auth/signup", json={
            "email": "extra@test.com",
            "password": "testpassword",
            "is_admin": True,
            "role": "admin",
        })
        assert response.status_code == 200


class TestLoginEdgeCases:
    """Edge cases for login endpoint."""

    @pytest.mark.asyncio
    async def test_login_sql_injection_in_email(self, client):
        """SQL injection attempt in email field."""
        response = await client.post("/auth/login", json={
            "email": "admin@test.com' OR '1'='1",
            "password": "password",
        })
        # Should fail email validation
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_login_with_user_having_no_local_identity(self, client, test_session):
        """Login fails if user has no local auth identity (e.g., OAuth-only user)."""
        role = await _create_role(test_session)
        user = User(email="oauthonly@test.com", role_id=role.id, is_active=True)
        test_session.add(user)
        await test_session.commit()

        response = await client.post("/auth/login", json={
            "email": "oauthonly@test.com",
            "password": "anypassword",
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_login_empty_password(self, client, test_session):
        """Login with empty password."""
        await _create_user_with_password(
            test_session, email="emptylogin@test.com", password="realpassword"
        )

        response = await client.post("/auth/login", json={
            "email": "emptylogin@test.com",
            "password": "",
        })
        assert response.status_code == 400


class TestPasswordUpdateEdgeCases:
    """Edge cases for password update endpoint."""

    @pytest.mark.asyncio
    async def test_password_update_token_revocation(self, admin_client):
        """Password update revokes all user tokens (increments token_version)."""
        client, session, user_id = admin_client
        role = await _create_role(session)
        user = User(id=user_id, email="pwrevoke@test.com", role_id=role.id,
                     is_active=True, token_version=0)
        session.add(user)
        await session.commit()

        response = await client.post("/auth/password", json={
            "password": "brandnewpassword",
        })
        assert response.status_code == 200

        # Verify token_version was incremented
        session.expire_all()
        from sqlalchemy.future import select
        result = await session.execute(select(User).where(User.id == user_id))
        db_user = result.scalar_one()
        assert db_user.token_version == 1


class TestProvidersEdgeCases:
    """Edge cases for /auth/providers endpoint."""

    @pytest.mark.asyncio
    async def test_providers_with_null_enabled_fields(self, client, test_session):
        """Settings row with NULL boolean fields treats them as enabled."""
        # The code checks `is not False`, so NULL means enabled
        owner = User(email="owner@test.com", is_active=True)
        test_session.add(owner)
        await test_session.flush()
        setting = Setting(
            user_id=owner.id,
            auth_local_enabled=None,
            auth_google_enabled=None,
            auth_github_enabled=None,
            auth_microsoft_enabled=None,
            change_type="create",
        )
        test_session.add(setting)
        await test_session.commit()

        response = await client.get("/auth/providers")
        assert response.status_code == 200
        providers = response.json()["providers"]
        # None is not False, so all should be enabled
        assert "local" in providers
        assert "google" in providers
        assert "github" in providers
        assert "microsoft" in providers

    @pytest.mark.asyncio
    async def test_providers_returns_latest_settings(self, client, test_session):
        """When multiple settings exist, uses the latest (by updated_at)."""
        from datetime import datetime, timedelta, UTC
        owner = User(email="multi@test.com", is_active=True)
        test_session.add(owner)
        await test_session.flush()

        now = datetime.now(UTC).replace(tzinfo=None)

        # First setting: all enabled (older timestamp)
        s1 = Setting(
            user_id=owner.id,
            auth_local_enabled=True, auth_google_enabled=True,
            auth_github_enabled=True, auth_microsoft_enabled=True,
            change_type="create",
            updated_at=now - timedelta(seconds=10),
        )
        test_session.add(s1)
        await test_session.commit()

        # Second setting: google disabled (newer timestamp)
        s2 = Setting(
            user_id=owner.id,
            auth_local_enabled=True, auth_google_enabled=False,
            auth_github_enabled=True, auth_microsoft_enabled=True,
            change_type="update",
            updated_at=now,
        )
        test_session.add(s2)
        await test_session.commit()

        response = await client.get("/auth/providers")
        providers = response.json()["providers"]
        assert "google" not in providers


class TestOAuthEdgeCases:
    """Edge cases for OAuth endpoints."""

    @pytest.mark.asyncio
    async def test_oauth_login_unsupported_provider(self, client):
        """OAuth login with unsupported provider."""
        response = await client.get("/auth/oauth/facebook")
        # Should fail (no AuthProvider record exists)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_oauth_callback_missing_params(self, client):
        """OAuth callback without required query params."""
        response = await client.get("/auth/oauth/google/callback")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_oauth_callback_provider_mismatch(self, client, test_session):
        """OAuth callback with state for different provider."""
        from src.api.core.jwt import create_oauth_state
        # Create a valid state for "github" but call the "google" callback
        state = create_oauth_state(provider="github", purpose="login")
        response = await client.get(
            "/auth/oauth/google/callback",
            params={"code": "fake_code", "state": state},
        )
        # Should fail: provider in state doesn't match URL path
        assert response.status_code == 400
        assert "mismatch" in response.json()["detail"].lower() or "not enabled" in response.json()["detail"].lower()


class TestOAuthCallbackDeepErrors:
    """Deep error branches for /auth/oauth/{provider}/callback."""

    @pytest.mark.asyncio
    async def test_oauth_callback_token_exchange_http_error(self, client):
        """HTTP error during token exchange returns 400."""
        request = httpx.Request("POST", "https://example.com/token")
        response = httpx.Response(400, request=request)
        http_error = httpx.HTTPStatusError("bad token", request=request, response=response)

        class FakeProvider:
            async def exchange_code_for_token(self, code: str):
                raise http_error

        with patch(
            "src.api.auth.router.check_auth_enabled", new_callable=AsyncMock
        ) as mock_check, patch(
            "src.api.auth.router.decode_oauth_state",
            return_value={"provider": "google", "purpose": "login"},
        ), patch(
            "src.api.auth.router.get_provider_instance",
            new_callable=AsyncMock,
            return_value=FakeProvider(),
        ):
            resp = await client.get(
                "/auth/oauth/google/callback",
                params={"code": "fake_code", "state": "dummy"},
            )

        assert resp.status_code == 400
        assert "exchange code" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_oauth_callback_profile_fetch_error_returns_500(self, client):
        """Failure while fetching user profile returns 500."""

        class FakeProvider:
            async def exchange_code_for_token(self, code: str):
                return {"access_token": "ok"}

            async def fetch_user_profile(self, token_data):
                raise RuntimeError("profile boom")

        with patch(
            "src.api.auth.router.check_auth_enabled", new_callable=AsyncMock
        ), patch(
            "src.api.auth.router.decode_oauth_state",
            return_value={"provider": "google", "purpose": "login"},
        ), patch(
            "src.api.auth.router.get_provider_instance",
            new_callable=AsyncMock,
            return_value=FakeProvider(),
        ):
            resp = await client.get(
                "/auth/oauth/google/callback",
                params={"code": "fake_code", "state": "dummy"},
            )

        assert resp.status_code == 500
        assert "authentication failed" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_oauth_callback_inactive_user_rejected(self, client):
        """User resolved as inactive results in 400."""

        class FakeProvider:
            async def exchange_code_for_token(self, code: str):
                return {"access_token": "ok"}

            async def fetch_user_profile(self, token_data):
                return {"some": "profile"}

        inactive_user = SimpleNamespace(is_active=False)

        with patch(
            "src.api.auth.router.check_auth_enabled", new_callable=AsyncMock
        ), patch(
            "src.api.auth.router.decode_oauth_state",
            return_value={"provider": "google", "purpose": "login"},
        ), patch(
            "src.api.auth.router.get_provider_instance",
            new_callable=AsyncMock,
            return_value=FakeProvider(),
        ), patch(
            "src.api.auth.router.resolve_oauth_user",
            new_callable=AsyncMock,
            return_value=inactive_user,
        ):
            resp = await client.get(
                "/auth/oauth/google/callback",
                params={"code": "fake_code", "state": "dummy"},
            )

        assert resp.status_code == 400
        assert "inactive" in resp.json()["detail"].lower()


class TestLinkEndpoints:
    """Tests for /auth/link and /auth/identities endpoints."""

    @pytest.mark.asyncio
    async def test_initiate_link_returns_auth_url(self, admin_client):
        """GET /auth/link/{provider} returns authorization_url and state."""
        client, session, user_id = admin_client

        class FakeProvider:
            async def get_authorization_url(self, state: str) -> str:
                return "https://provider.example.com/link?state=" + state

        with patch(
            "src.api.auth.router.get_provider_instance",
            new_callable=AsyncMock,
            return_value=FakeProvider(),
        ):
            resp = await client.get("/auth/link/google")

        assert resp.status_code == 200
        data = resp.json()
        assert data["authorization_url"].startswith("https://provider.example.com/link")
        assert isinstance(data["state"], str) and data["state"]

    @pytest.mark.asyncio
    async def test_link_callback_success(self, client):
        """Successful link callback delegates to link_oauth_identity."""

        class FakeProvider:
            async def exchange_code_for_token(self, code: str):
                return {"access_token": "ok"}

            async def fetch_user_profile(self, token_data):
                return {"provider": "google", "provider_user_id": "123"}

        result_payload = {"message": "google account linked successfully"}

        with patch(
            "src.api.auth.router.check_auth_enabled", new_callable=AsyncMock
        ), patch(
            "src.api.auth.router.decode_oauth_state",
            return_value={
                "provider": "google",
                "purpose": "link",
                "user_id": str(uuid4()),
            },
        ), patch(
            "src.api.auth.router.get_provider_instance",
            new_callable=AsyncMock,
            return_value=FakeProvider(),
        ), patch(
            "src.api.auth.router.link_oauth_identity",
            new_callable=AsyncMock,
            return_value=result_payload,
        ):
            resp = await client.get(
                "/auth/link/google/callback",
                params={"code": "fake_code", "state": "dummy"},
            )

        assert resp.status_code == 200
        assert resp.json() == result_payload

    @pytest.mark.asyncio
    async def test_link_callback_invalid_state(self, client):
        """Invalid/expired state for link callback returns 400."""
        with patch(
            "src.api.auth.router.check_auth_enabled", new_callable=AsyncMock
        ), patch("src.api.auth.router.decode_oauth_state", return_value=None):
            resp = await client.get(
                "/auth/link/google/callback",
                params={"code": "fake_code", "state": "bad"},
            )

        assert resp.status_code == 400
        assert "invalid or expired state" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_link_callback_wrong_purpose(self, client):
        """State with wrong purpose is rejected."""
        with patch(
            "src.api.auth.router.check_auth_enabled", new_callable=AsyncMock
        ), patch(
            "src.api.auth.router.decode_oauth_state",
            return_value={"provider": "google", "purpose": "login", "user_id": str(uuid4())},
        ):
            resp = await client.get(
                "/auth/link/google/callback",
                params={"code": "fake_code", "state": "dummy"},
            )

        assert resp.status_code == 400
        assert "purpose" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_link_callback_provider_mismatch(self, client):
        """Provider in state not matching path param is rejected."""
        with patch(
            "src.api.auth.router.check_auth_enabled", new_callable=AsyncMock
        ), patch(
            "src.api.auth.router.decode_oauth_state",
            return_value={"provider": "github", "purpose": "link", "user_id": str(uuid4())},
        ):
            resp = await client.get(
                "/auth/link/google/callback",
                params={"code": "fake_code", "state": "dummy"},
            )

        assert resp.status_code == 400
        assert "mismatch" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_link_callback_missing_user_id(self, client):
        """Missing user_id in state is rejected."""
        with patch(
            "src.api.auth.router.check_auth_enabled", new_callable=AsyncMock
        ), patch(
            "src.api.auth.router.decode_oauth_state",
            return_value={"provider": "google", "purpose": "link"},
        ):
            resp = await client.get(
                "/auth/link/google/callback",
                params={"code": "fake_code", "state": "dummy"},
            )

        assert resp.status_code == 400
        assert "user_id" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_link_callback_token_exchange_http_error(self, client):
        """HTTP error during token exchange in link callback returns 400."""
        request = httpx.Request("POST", "https://example.com/token")
        response = httpx.Response(400, request=request)
        http_error = httpx.HTTPStatusError("bad token", request=request, response=response)

        class FakeProvider:
            async def exchange_code_for_token(self, code: str):
                raise http_error

        with patch(
            "src.api.auth.router.check_auth_enabled", new_callable=AsyncMock
        ), patch(
            "src.api.auth.router.decode_oauth_state",
            return_value={"provider": "google", "purpose": "link", "user_id": str(uuid4())},
        ), patch(
            "src.api.auth.router.get_provider_instance",
            new_callable=AsyncMock,
            return_value=FakeProvider(),
        ):
            resp = await client.get(
                "/auth/link/google/callback",
                params={"code": "fake_code", "state": "dummy"},
            )

        assert resp.status_code == 400
        assert "exchange code" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_link_callback_profile_fetch_error_returns_500(self, client):
        """Failure while fetching profile in link callback returns 500."""

        class FakeProvider:
            async def exchange_code_for_token(self, code: str):
                return {"access_token": "ok"}

            async def fetch_user_profile(self, token_data):
                raise RuntimeError("profile boom")

        with patch(
            "src.api.auth.router.check_auth_enabled", new_callable=AsyncMock
        ), patch(
            "src.api.auth.router.decode_oauth_state",
            return_value={"provider": "google", "purpose": "link", "user_id": str(uuid4())},
        ), patch(
            "src.api.auth.router.get_provider_instance",
            new_callable=AsyncMock,
            return_value=FakeProvider(),
        ):
            resp = await client.get(
                "/auth/link/google/callback",
                params={"code": "fake_code", "state": "dummy"},
            )

        assert resp.status_code == 500
        assert "failed to fetch user profile" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_unlink_provider_endpoint_calls_service(self, admin_client):
        """DELETE /auth/identities/{provider} delegates to unlink_identity."""
        client, session, user_id = admin_client

        with patch(
            "src.api.auth.router.unlink_identity",
            new_callable=AsyncMock,
            return_value={"message": "github account unlinked successfully"},
        ) as mock_unlink:
            resp = await client.delete("/auth/identities/github")

        assert resp.status_code == 200
        assert "unlinked" in resp.json()["message"].lower()
        mock_unlink.assert_awaited()

class _DummyResponse:
    def __init__(self, data: Any):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        if isinstance(self._data, Exception):
            raise self._data
        return self._data


class _DummyAsyncClient:
    """Simple async context manager that returns predefined responses."""

    def __init__(self, responses: List[_DummyResponse]):
        self._responses = list(responses)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    async def post(self, url: str, **kwargs):
        return self._responses.pop(0)

    async def get(self, url: str, **kwargs):
        return self._responses.pop(0)


class TestGitHubProvider:
    """Unit tests for the GitHub OAuth provider."""

    @pytest.fixture
    def github_config(self) -> Dict[str, str]:
        return {
            "client_id": "cid",
            "client_secret": "secret",
            "redirect_uri": "https://app.example.com/callback/github",
        }

    @pytest.mark.asyncio
    async def test_get_authorization_url_builds_expected_query(self, github_config):
        from src.api.auth.providers.github import GithubProvider
        provider = GithubProvider(github_config)
        url = await provider.get_authorization_url("state123")

        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        assert parsed.scheme in {"http", "https"}
        assert qs["client_id"] == [github_config["client_id"]]
        assert qs["redirect_uri"] == [github_config["redirect_uri"]]
        assert qs["state"] == ["state123"]
        assert qs["scope"] == ["user:email"]

    @pytest.mark.asyncio
    async def test_exchange_code_for_token_happy_path(self, github_config):
        from src.api.auth.providers.github import GithubProvider
        provider = GithubProvider(github_config)
        token_payload = {"access_token": "github-token"}

        with patch(
            "src.api.auth.providers.github.httpx.AsyncClient",
            return_value=_DummyAsyncClient([_DummyResponse(token_payload)]),
        ):
            result = await provider.exchange_code_for_token("code123")

        assert result == token_payload

    @pytest.mark.asyncio
    async def test_exchange_code_json_error_raises_http_exc(self, github_config):
        from src.api.auth.providers.github import GithubProvider
        provider = GithubProvider(github_config)

        with patch(
            "src.api.auth.providers.github.httpx.AsyncClient",
            return_value=_DummyAsyncClient([_DummyResponse(ValueError("bad json"))]),
        ):
            with pytest.raises(HTTPException) as exc:
                await provider.exchange_code_for_token("code123")
        assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_fetch_user_profile_with_public_email(self, github_config):
        from src.api.auth.providers.github import GithubProvider
        provider = GithubProvider(github_config)
        token = {"access_token": "token"}
        user_info = {
            "id": 123, "email": "user@example.com",
            "name": "Test User", "avatar_url": "https://avatar.example.com/1.png",
        }

        with patch(
            "src.api.auth.providers.github.httpx.AsyncClient",
            return_value=_DummyAsyncClient([_DummyResponse(user_info)]),
        ):
            profile = await provider.fetch_user_profile(token)

        assert profile["provider"] == "github"
        assert profile["provider_user_id"] == "123"
        assert profile["email"] == "user@example.com"
        assert profile["name"] == "Test User"

    @pytest.mark.asyncio
    async def test_fetch_user_profile_fetches_emails_when_missing(self, github_config):
        from src.api.auth.providers.github import GithubProvider
        provider = GithubProvider(github_config)
        token = {"access_token": "token"}
        user_info = {"id": 123, "email": None, "login": "login-name", "avatar_url": "https://avatar.example.com/1.png"}
        emails = [
            {"email": "secondary@example.com", "primary": False, "verified": True},
            {"email": "primary@example.com", "primary": True, "verified": True},
        ]

        with patch(
            "src.api.auth.providers.github.httpx.AsyncClient",
            return_value=_DummyAsyncClient([_DummyResponse(user_info), _DummyResponse(emails)]),
        ):
            profile = await provider.fetch_user_profile(token)

        assert profile["email"] == "primary@example.com"
        assert profile["name"] == "login-name"

    @pytest.mark.asyncio
    async def test_fetch_user_profile_no_verified_email_raises(self, github_config):
        from src.api.auth.providers.github import GithubProvider
        provider = GithubProvider(github_config)
        token = {"access_token": "token"}
        user_info = {"id": 123, "email": None}
        emails: list[dict] = []

        with patch(
            "src.api.auth.providers.github.httpx.AsyncClient",
            return_value=_DummyAsyncClient([_DummyResponse(user_info), _DummyResponse(emails)]),
        ):
            with pytest.raises(HTTPException) as exc:
                await provider.fetch_user_profile(token)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_fetch_user_profile_json_error_on_user_raises(self, github_config):
        from src.api.auth.providers.github import GithubProvider
        provider = GithubProvider(github_config)
        token = {"access_token": "token"}

        with patch(
            "src.api.auth.providers.github.httpx.AsyncClient",
            return_value=_DummyAsyncClient([_DummyResponse(ValueError("bad user json"))]),
        ):
            with pytest.raises(HTTPException) as exc:
                await provider.fetch_user_profile(token)
        assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_fetch_user_profile_json_error_on_emails_raises(self, github_config):
        from src.api.auth.providers.github import GithubProvider
        provider = GithubProvider(github_config)
        token = {"access_token": "token"}
        user_info = {"id": 123, "email": None}

        with patch(
            "src.api.auth.providers.github.httpx.AsyncClient",
            return_value=_DummyAsyncClient([_DummyResponse(user_info), _DummyResponse(ValueError("bad emails json"))]),
        ):
            with pytest.raises(HTTPException) as exc:
                await provider.fetch_user_profile(token)
        assert exc.value.status_code == 500


class TestGoogleProvider:
    """Unit tests for the Google OAuth provider."""

    @pytest.fixture
    def google_config(self) -> Dict[str, str]:
        from src.api.auth.providers.google import _discovery_cache
        _discovery_cache["doc"] = None
        _discovery_cache["expires"] = 0
        return {
            "client_id": "gid",
            "client_secret": "secret",
            "redirect_uri": "https://app.example.com/callback/google",
        }

    @pytest.mark.asyncio
    async def test_get_authorization_url_uses_discovery(self, google_config):
        from src.api.auth.providers.google import GoogleProvider
        provider = GoogleProvider(google_config)
        discovery = {"authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth"}

        with patch.object(provider, "_get_discovery_document", return_value=discovery):
            url = await provider.get_authorization_url("state456")

        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        assert qs["client_id"] == [google_config["client_id"]]
        assert qs["state"] == ["state456"]
        assert qs["response_type"] == ["code"]

    @pytest.mark.asyncio
    async def test_exchange_code_for_token_happy_path(self, google_config):
        from src.api.auth.providers.google import GoogleProvider
        provider = GoogleProvider(google_config)
        discovery = {"token_endpoint": "https://oauth2.googleapis.com/token"}
        token_payload = {"access_token": "google-token"}

        with patch.object(provider, "_get_discovery_document", return_value=discovery), \
             patch("src.api.auth.providers.google.httpx.AsyncClient",
                   return_value=_DummyAsyncClient([_DummyResponse(token_payload)])):
            result = await provider.exchange_code_for_token("code456")

        assert result == token_payload

    @pytest.mark.asyncio
    async def test_fetch_user_profile_email_verified(self, google_config):
        from src.api.auth.providers.google import GoogleProvider
        provider = GoogleProvider(google_config)
        discovery = {"userinfo_endpoint": "https://openidconnect.googleapis.com/v1/userinfo"}
        token = {"access_token": "g-token"}
        user_info = {
            "sub": "sub123", "email": "user@gmail.com",
            "email_verified": True, "name": "G User",
            "picture": "https://example.com/pic.png",
        }

        with patch.object(provider, "_get_discovery_document", return_value=discovery), \
             patch("src.api.auth.providers.google.httpx.AsyncClient",
                   return_value=_DummyAsyncClient([_DummyResponse(user_info)])):
            profile = await provider.fetch_user_profile(token)

        assert profile["provider"] == "google"
        assert profile["provider_user_id"] == "sub123"
        assert profile["email"] == "user@gmail.com"

    @pytest.mark.asyncio
    async def test_fetch_user_profile_unverified_email_raises(self, google_config):
        from src.api.auth.providers.google import GoogleProvider
        provider = GoogleProvider(google_config)
        discovery = {"userinfo_endpoint": "https://openidconnect.googleapis.com/v1/userinfo"}
        token = {"access_token": "g-token"}
        user_info = {"sub": "sub123", "email": "user@gmail.com", "email_verified": False}

        with patch.object(provider, "_get_discovery_document", return_value=discovery), \
             patch("src.api.auth.providers.google.httpx.AsyncClient",
                   return_value=_DummyAsyncClient([_DummyResponse(user_info)])):
            with pytest.raises(HTTPException) as exc:
                await provider.fetch_user_profile(token)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_discovery_document_is_cached(self, google_config):
        """_get_discovery_document should cache results until TTL expires."""
        from src.api.auth.providers.google import GoogleProvider
        provider = GoogleProvider(google_config)
        doc = {"authorization_endpoint": "https://accounts.google.com/auth"}

        with patch("src.api.auth.providers.google.httpx.AsyncClient",
                   return_value=_DummyAsyncClient([_DummyResponse(doc)])):
            first = await provider._get_discovery_document()
            second = await provider._get_discovery_document()

        assert first is second is doc


class TestMicrosoftProvider:
    """Unit tests for the Microsoft OAuth provider."""

    @pytest.fixture
    def microsoft_config(self) -> Dict[str, str]:
        return {
            "client_id": "mid",
            "client_secret": "secret",
            "redirect_uri": "https://app.example.com/callback/microsoft",
            "tenant": "common",
        }

    @pytest.mark.asyncio
    async def test_get_authorization_url_builds_query(self, microsoft_config):
        from src.api.auth.providers.microsoft import MicrosoftProvider
        provider = MicrosoftProvider(microsoft_config)
        url = await provider.get_authorization_url("state789")

        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        assert qs["client_id"] == [microsoft_config["client_id"]]
        assert qs["state"] == ["state789"]
        assert qs["response_type"] == ["code"]

    @pytest.mark.asyncio
    async def test_exchange_code_for_token_happy_path(self, microsoft_config):
        from src.api.auth.providers.microsoft import MicrosoftProvider
        provider = MicrosoftProvider(microsoft_config)
        token_payload = {"access_token": "ms-token"}

        with patch("src.api.auth.providers.microsoft.httpx.AsyncClient",
                   return_value=_DummyAsyncClient([_DummyResponse(token_payload)])):
            result = await provider.exchange_code_for_token("code789")

        assert result == token_payload

    @pytest.mark.asyncio
    async def test_fetch_user_profile_with_mail(self, microsoft_config):
        from src.api.auth.providers.microsoft import MicrosoftProvider
        provider = MicrosoftProvider(microsoft_config)
        token = {"access_token": "ms-token"}
        user_info = {"id": "user-id", "mail": "user@contoso.com", "displayName": "MS User"}

        with patch("src.api.auth.providers.microsoft.httpx.AsyncClient",
                   return_value=_DummyAsyncClient([_DummyResponse(user_info)])):
            profile = await provider.fetch_user_profile(token)

        assert profile["provider"] == "microsoft"
        assert profile["email"] == "user@contoso.com"

    @pytest.mark.asyncio
    async def test_fetch_user_profile_falls_back_to_upn(self, microsoft_config):
        from src.api.auth.providers.microsoft import MicrosoftProvider
        provider = MicrosoftProvider(microsoft_config)
        token = {"access_token": "ms-token"}
        user_info = {"id": "user-id", "mail": None, "userPrincipalName": "upn@contoso.com"}

        with patch("src.api.auth.providers.microsoft.httpx.AsyncClient",
                   return_value=_DummyAsyncClient([_DummyResponse(user_info)])):
            profile = await provider.fetch_user_profile(token)

        assert profile["email"] == "upn@contoso.com"

    @pytest.mark.asyncio
    async def test_fetch_user_profile_missing_email_raises(self, microsoft_config):
        from src.api.auth.providers.microsoft import MicrosoftProvider
        provider = MicrosoftProvider(microsoft_config)
        token = {"access_token": "ms-token"}
        user_info = {"id": "user-id"}

        with patch("src.api.auth.providers.microsoft.httpx.AsyncClient",
                   return_value=_DummyAsyncClient([_DummyResponse(user_info)])):
            with pytest.raises(HTTPException) as exc:
                await provider.fetch_user_profile(token)
        assert exc.value.status_code == 400

from datetime import datetime, timezone, timedelta
from src.api.db.models import RevokedToken, UserRole, AuthProvider
from src.api.auth.service import (
    revoke_token,
    revoke_all_user_tokens,
    get_default_role,
    signup_user,
    login_user,
    resolve_oauth_user,
    update_user_password,
    link_oauth_identity,
    unlink_identity,
)
from src.api.auth.schemas import UserSignup, UserLogin
from sqlalchemy.future import select


async def _make_user_with_password(session, email="test@example.com", password="testpass"):
    """Create User + Role + AuthIdentity for login testing."""
    role = Role(name=f"role_{uuid4().hex[:6]}")
    session.add(role)
    await session.flush()

    user = User(email=email, role_id=role.id, is_active=True)
    session.add(user)
    await session.flush()

    hashed = get_password_hash(password)
    identity = AuthIdentity(user_id=user.id, provider="local", password_hash=hashed)
    session.add(identity)

    user_role = UserRole(user_id=user.id, role_id=role.id)
    session.add(user_role)
    await session.commit()
    return user, role


class TestRevokeToken:
    """Tests for revoke_token()."""

    @pytest.mark.asyncio
    async def test_revoke_token_creates_record(self, test_session):
        jti = str(uuid4())
        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        await revoke_token(jti, expires, test_session)

        result = await test_session.execute(
            select(RevokedToken).where(RevokedToken.jti == jti)
        )
        record = result.scalar_one_or_none()
        assert record is not None
        assert record.jti == jti

    @pytest.mark.asyncio
    async def test_revoke_token_strips_timezone(self, test_session):
        """Timezone-aware datetime is stored as naive UTC."""
        jti = str(uuid4())
        expires = datetime.now(timezone.utc) + timedelta(hours=2)
        await revoke_token(jti, expires, test_session)

        result = await test_session.execute(
            select(RevokedToken).where(RevokedToken.jti == jti)
        )
        record = result.scalar_one()
        assert record.expires_at.tzinfo is None


class TestRevokeAllUserTokens:
    """Tests for revoke_all_user_tokens()."""

    @pytest.mark.asyncio
    async def test_increments_token_version(self, test_session):
        user = User(email="rev@test.com", is_active=True, token_version=0)
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        await revoke_all_user_tokens(user.id, test_session)
        await test_session.refresh(user)
        assert user.token_version == 1

    @pytest.mark.asyncio
    async def test_nonexistent_user_no_error(self, test_session):
        """Revoking tokens for nonexistent user doesn't error."""
        await revoke_all_user_tokens(uuid4(), test_session)


class TestGetDefaultRole:
    """Tests for get_default_role()."""

    @pytest.mark.asyncio
    async def test_returns_basic_user_role(self, test_session):
        role = Role(name="Basic User")
        test_session.add(role)
        await test_session.commit()

        result = await get_default_role(test_session)
        assert result.name == "Basic User"

    @pytest.mark.asyncio
    async def test_falls_back_to_user_role(self, test_session):
        role = Role(name="user")
        test_session.add(role)
        await test_session.commit()

        result = await get_default_role(test_session)
        assert result.name == "user"

    @pytest.mark.asyncio
    async def test_creates_basic_user_when_none_exist(self, test_session):
        result = await get_default_role(test_session)
        assert result.name == "Basic User"
        assert result.id is not None


class TestSignupService:
    """Tests for signup_user() service function."""

    @pytest.mark.asyncio
    async def test_new_user_creation(self, test_session):
        data = UserSignup(email="new@test.com", password="testpass")
        result = await signup_user(data, test_session)
        assert result["message"] == "User created successfully"

        db_user = (await test_session.execute(
            select(User).where(User.email == "new@test.com")
        )).scalar_one()
        assert db_user.is_active is True

    @pytest.mark.asyncio
    async def test_duplicate_email_raises(self, test_session):
        data = UserSignup(email="dup@test.com", password="testpass")
        await signup_user(data, test_session)

        with pytest.raises(HTTPException) as exc:
            await signup_user(data, test_session)
        assert exc.value.status_code == 400
        assert "already exists" in exc.value.detail

    @pytest.mark.asyncio
    async def test_reactivation_of_deleted_user(self, test_session):
        """Soft-deleted user is reactivated on signup with same email."""
        data = UserSignup(email="reactivate@test.com", password="old")
        await signup_user(data, test_session)

        user = (await test_session.execute(
            select(User).where(User.email == "reactivate@test.com")
        )).scalar_one()
        user.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        user.is_active = False
        await test_session.commit()

        result = await signup_user(
            UserSignup(email="reactivate@test.com", password="newpass"),
            test_session,
        )
        assert result["message"] == "User created successfully"

        await test_session.refresh(user)
        assert user.is_active is True
        assert user.deleted_at is None

    @pytest.mark.asyncio
    async def test_creates_auth_identity(self, test_session):
        data = UserSignup(email="identity@test.com", password="pass123")
        await signup_user(data, test_session)

        user = (await test_session.execute(
            select(User).where(User.email == "identity@test.com")
        )).scalar_one()

        identity = (await test_session.execute(
            select(AuthIdentity).where(
                AuthIdentity.user_id == user.id,
                AuthIdentity.provider == "local",
            )
        )).scalar_one()
        assert identity.password_hash is not None

    @pytest.mark.asyncio
    async def test_creates_user_role_entry(self, test_session):
        data = UserSignup(email="userrole@test.com", password="pass123")
        await signup_user(data, test_session)

        user = (await test_session.execute(
            select(User).where(User.email == "userrole@test.com")
        )).scalar_one()

        ur = (await test_session.execute(
            select(UserRole).where(UserRole.user_id == user.id)
        )).scalar_one_or_none()
        assert ur is not None


class TestLoginService:
    """Tests for login_user() service function."""

    @pytest.mark.asyncio
    async def test_login_success(self, test_session):
        user, _ = await _make_user_with_password(test_session, "login@test.com", "correct")
        creds = UserLogin(email="login@test.com", password="correct")
        result = await login_user(creds, test_session)
        assert result.access_token is not None
        assert result.email == "login@test.com"

    @pytest.mark.asyncio
    async def test_wrong_password(self, test_session):
        await _make_user_with_password(test_session, "wp@test.com", "correct")
        with pytest.raises(HTTPException) as exc:
            await login_user(UserLogin(email="wp@test.com", password="wrong"), test_session)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_nonexistent_user(self, test_session):
        with pytest.raises(HTTPException) as exc:
            await login_user(UserLogin(email="ghost@test.com", password="x"), test_session)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_inactive_user(self, test_session):
        user, _ = await _make_user_with_password(test_session, "inactive@test.com", "pass")
        user.is_active = False
        await test_session.commit()

        with pytest.raises(HTTPException) as exc:
            await login_user(UserLogin(email="inactive@test.com", password="pass"), test_session)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_no_local_identity(self, test_session):
        """User with only OAuth identity can't login with password."""
        role = Role(name=f"r_{uuid4().hex[:6]}")
        test_session.add(role)
        await test_session.flush()
        user = User(email="oauth_only@test.com", role_id=role.id, is_active=True)
        test_session.add(user)
        await test_session.flush()
        test_session.add(AuthIdentity(user_id=user.id, provider="google", provider_user_id="g123"))
        test_session.add(UserRole(user_id=user.id, role_id=role.id))
        await test_session.commit()

        with pytest.raises(HTTPException) as exc:
            await login_user(UserLogin(email="oauth_only@test.com", password="x"), test_session)
        assert exc.value.status_code == 400


class TestResolveOAuthUser:
    """Tests for resolve_oauth_user()."""

    @pytest.mark.asyncio
    async def test_creates_new_user(self, test_session):
        profile = {
            "provider": "github",
            "provider_user_id": "gh-123",
            "email": "oauth_new@test.com",
        }
        user = await resolve_oauth_user(profile, test_session)
        assert user.email == "oauth_new@test.com"
        assert user.is_active is True

    @pytest.mark.asyncio
    async def test_returns_existing_user(self, test_session):
        profile = {
            "provider": "github",
            "provider_user_id": "gh-existing",
            "email": "existing_oauth@test.com",
        }
        first = await resolve_oauth_user(profile, test_session)
        second = await resolve_oauth_user(profile, test_session)
        assert first.id == second.id

    @pytest.mark.asyncio
    async def test_email_conflict_raises_409(self, test_session):
        """Email already used by different account raises 409."""
        role = Role(name=f"r_{uuid4().hex[:6]}")
        test_session.add(role)
        await test_session.flush()
        existing = User(email="conflict@test.com", role_id=role.id, is_active=True)
        test_session.add(existing)
        await test_session.commit()

        profile = {
            "provider": "google",
            "provider_user_id": "g-new",
            "email": "conflict@test.com",
        }
        with pytest.raises(HTTPException) as exc:
            await resolve_oauth_user(profile, test_session)
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_reactivates_deleted_user(self, test_session):
        profile = {
            "provider": "github",
            "provider_user_id": "gh-del",
            "email": "deleted_oauth@test.com",
        }
        user = await resolve_oauth_user(profile, test_session)
        user.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        user.is_active = False
        await test_session.commit()

        reactivated = await resolve_oauth_user(profile, test_session)
        assert reactivated.is_active is True
        assert reactivated.deleted_at is None


class TestUpdateUserPassword:
    """Tests for update_user_password()."""

    @pytest.mark.asyncio
    async def test_update_existing_identity(self, test_session):
        user, _ = await _make_user_with_password(test_session, "upd@test.com", "old")
        result = await update_user_password(user.id, "newpass", test_session)
        assert result["message"] == "Password updated successfully"

    @pytest.mark.asyncio
    async def test_creates_identity_if_missing(self, test_session):
        """OAuth-only user gets a local identity on password set."""
        role = Role(name=f"r_{uuid4().hex[:6]}")
        test_session.add(role)
        await test_session.flush()
        user = User(email="oauth_pw@test.com", role_id=role.id, is_active=True)
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        await update_user_password(user.id, "newpass", test_session)

        identity = (await test_session.execute(
            select(AuthIdentity).where(
                AuthIdentity.user_id == user.id,
                AuthIdentity.provider == "local",
            )
        )).scalar_one()
        assert identity.password_hash is not None

    @pytest.mark.asyncio
    async def test_revokes_all_tokens(self, test_session):
        user, _ = await _make_user_with_password(test_session, "revoke@test.com", "old")
        old_version = user.token_version

        await update_user_password(user.id, "newpass", test_session)
        await test_session.refresh(user)
        assert user.token_version > old_version


class TestLinkOAuthIdentity:
    """Tests for link_oauth_identity()."""

    @pytest.mark.asyncio
    async def test_link_success(self, test_session):
        user, _ = await _make_user_with_password(test_session, "link@test.com", "pass")
        profile = {"provider": "github", "provider_user_id": "gh-link"}
        result = await link_oauth_identity(user.id, profile, test_session)
        assert "linked successfully" in result["message"]

    @pytest.mark.asyncio
    async def test_already_linked_same_user(self, test_session):
        user, _ = await _make_user_with_password(test_session, "already@test.com", "pass")
        profile = {"provider": "github", "provider_user_id": "gh-already"}
        await link_oauth_identity(user.id, profile, test_session)
        result = await link_oauth_identity(user.id, profile, test_session)
        assert "already linked" in result["message"]

    @pytest.mark.asyncio
    async def test_conflict_different_user(self, test_session):
        user1, _ = await _make_user_with_password(test_session, "u1@test.com", "pass")
        user2, _ = await _make_user_with_password(test_session, "u2@test.com", "pass")
        profile = {"provider": "github", "provider_user_id": "gh-shared"}

        await link_oauth_identity(user1.id, profile, test_session)
        with pytest.raises(HTTPException) as exc:
            await link_oauth_identity(user2.id, profile, test_session)
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_user_already_has_provider(self, test_session):
        user, _ = await _make_user_with_password(test_session, "dualprov@test.com", "pass")
        await link_oauth_identity(
            user.id,
            {"provider": "github", "provider_user_id": "gh-1"},
            test_session,
        )
        with pytest.raises(HTTPException) as exc:
            await link_oauth_identity(
                user.id,
                {"provider": "github", "provider_user_id": "gh-2"},
                test_session,
            )
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_user_not_found(self, test_session):
        with pytest.raises(HTTPException) as exc:
            await link_oauth_identity(
                uuid4(),
                {"provider": "github", "provider_user_id": "x"},
                test_session,
            )
        assert exc.value.status_code == 404


class TestUnlinkIdentity:
    """Tests for unlink_identity()."""

    @pytest.mark.asyncio
    async def test_unlink_success(self, test_session):
        user, _ = await _make_user_with_password(test_session, "unlink@test.com", "pass")
        test_session.add(AuthIdentity(
            user_id=user.id, provider="github", provider_user_id="gh-ul"
        ))
        await test_session.commit()

        result = await unlink_identity(user.id, "github", test_session)
        assert "unlinked successfully" in result["message"]

    @pytest.mark.asyncio
    async def test_cannot_remove_last_identity(self, test_session):
        role = Role(name=f"r_{uuid4().hex[:6]}")
        test_session.add(role)
        await test_session.flush()
        user = User(email="solo@test.com", role_id=role.id, is_active=True)
        test_session.add(user)
        await test_session.flush()
        test_session.add(AuthIdentity(
            user_id=user.id, provider="github", provider_user_id="gh-solo"
        ))
        await test_session.commit()

        with pytest.raises(HTTPException) as exc:
            await unlink_identity(user.id, "github", test_session)
        assert exc.value.status_code == 400
        assert "last authentication" in exc.value.detail

    @pytest.mark.asyncio
    async def test_provider_not_linked(self, test_session):
        """Trying to unlink a provider that isn't linked returns 404."""
        user, _ = await _make_user_with_password(test_session, "nolink@test.com", "pass")
        # Add a second identity so the "last identity" check doesn't trigger
        test_session.add(AuthIdentity(
            user_id=user.id, provider="github", provider_user_id="gh-nolink"
        ))
        await test_session.commit()

        with pytest.raises(HTTPException) as exc:
            await unlink_identity(user.id, "microsoft", test_session)
        assert exc.value.status_code == 404