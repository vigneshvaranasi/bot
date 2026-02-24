"""Comprehensive tests for Auth endpoints (/auth).

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
"""

import pytest
from uuid import uuid4

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
