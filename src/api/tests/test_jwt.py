"""Tests for JWT utilities.

Covers token creation, decoding, expiration, security edge cases,
algorithm enforcement, OAuth state replay protection, and tampering detection.
"""

import pytest
import jwt as pyjwt
import uuid
import threading
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException

from src.api.core.jwt import (
    create_access_token,
    decode_token,
    create_oauth_state,
    decode_oauth_state,
    SECRET_KEY,
    ALGORITHM,
    _consumed_state_jtis,
    _consumed_jtis_lock,
)


class TestCreateAccessToken:
    """Tests for create_access_token function."""

    def test_creates_valid_jwt(self):
        """Test that create_access_token creates a valid JWT."""
        token = create_access_token(
            user_id="test-user-id",
            role="user",
            auth_provider="local",
            token_version=1
        )

        payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["user_id"] == "test-user-id"
        assert payload["role"] == "user"
        assert payload["auth_provider"] == "local"
        assert payload["token_version"] == "1"
        assert "exp" in payload
        assert "iat" in payload
        assert "jti" in payload

    def test_custom_expiration(self):
        """Test that custom expiration delta is respected."""
        token = create_access_token(
            user_id="test-user",
            role="admin",
            auth_provider="google",
            token_version=2,
            expires_delta=timedelta(minutes=1)
        )

        payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp = payload["exp"]
        iat = payload["iat"]

        assert 55 <= (exp - iat) <= 65

    def test_all_required_claims_present(self):
        """Token contains all required fields."""
        token = create_access_token("user-1", "admin", "local", 1)
        payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "jti" in payload
        assert "user_id" in payload
        assert "role" in payload
        assert "auth_provider" in payload
        assert "token_version" in payload
        assert "exp" in payload
        assert "iat" in payload

    def test_jti_is_unique_per_token(self):
        """Each token gets a unique jti."""
        t1 = create_access_token("user-1", "admin", "local", 1)
        t2 = create_access_token("user-1", "admin", "local", 1)
        p1 = pyjwt.decode(t1, SECRET_KEY, algorithms=[ALGORITHM])
        p2 = pyjwt.decode(t2, SECRET_KEY, algorithms=[ALGORITHM])
        assert p1["jti"] != p2["jti"]

    def test_token_version_stored_as_string(self):
        """token_version is converted to string in the token."""
        token = create_access_token("user-1", "admin", "local", 42)
        payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["token_version"] == "42"

    def test_negative_expiration_creates_expired_token(self):
        """Negative expiration creates an already-expired token."""
        token = create_access_token(
            "user-1", "admin", "local", 1,
            expires_delta=timedelta(seconds=-60)
        )
        with pytest.raises(HTTPException) as exc_info:
            decode_token(token)
        assert exc_info.value.status_code == 401


class TestDecodeToken:
    """Tests for decode_token function."""

    def test_decodes_valid_token(self):
        """Test that decode_token correctly decodes a valid token."""
        token = create_access_token(
            user_id="test-user",
            role="user",
            auth_provider="local",
            token_version=1
        )

        payload = decode_token(token)
        assert payload["user_id"] == "test-user"
        assert payload["role"] == "user"

    def test_raises_on_invalid_token(self):
        """Test that decode_token raises HTTPException for invalid token."""
        with pytest.raises(HTTPException) as exc_info:
            decode_token("invalid-token")

        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in str(exc_info.value.detail)

    def test_raises_on_expired_token(self):
        """Test that decode_token raises HTTPException for expired token."""
        token = create_access_token(
            user_id="test-user",
            role="user",
            auth_provider="local",
            token_version=1,
            expires_delta=timedelta(seconds=-10)
        )

        with pytest.raises(HTTPException) as exc_info:
            decode_token(token)

        assert exc_info.value.status_code == 401


class TestDecodeTokenSecurity:
    """Security tests for token decoding."""

    def test_reject_token_signed_with_wrong_key(self):
        """Token signed with a different key is rejected."""
        payload = {
            "user_id": "user-1", "role": "admin", "auth_provider": "local",
            "token_version": "1", "jti": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        token = pyjwt.encode(payload, "wrong-secret-key", algorithm=ALGORITHM)
        with pytest.raises(HTTPException) as exc_info:
            decode_token(token)
        assert exc_info.value.status_code == 401

    def test_reject_none_algorithm_attack(self):
        """Token with 'none' algorithm is rejected."""
        payload = {
            "user_id": "user-1", "role": "admin", "auth_provider": "local",
            "token_version": "1", "jti": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        token = pyjwt.encode(payload, "", algorithm="none")
        with pytest.raises(HTTPException) as exc_info:
            decode_token(token)
        assert exc_info.value.status_code == 401

    def test_reject_token_without_exp(self):
        """Token without exp claim is rejected."""
        payload = {
            "user_id": "user-1", "role": "admin",
            "iat": datetime.now(timezone.utc),
        }
        token = pyjwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        with pytest.raises((HTTPException, pyjwt.exceptions.MissingRequiredClaimError)):
            decode_token(token)

    def test_reject_token_without_iat(self):
        """Token without iat claim is rejected."""
        payload = {
            "user_id": "user-1", "role": "admin",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        token = pyjwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        with pytest.raises(HTTPException) as exc_info:
            decode_token(token)
        assert exc_info.value.status_code == 401

    def test_reject_completely_malformed_token(self):
        """Completely malformed string is rejected."""
        with pytest.raises(HTTPException) as exc_info:
            decode_token("not.a.jwt")
        assert exc_info.value.status_code == 401

    def test_reject_empty_token(self):
        """Empty string token is rejected."""
        with pytest.raises(HTTPException) as exc_info:
            decode_token("")
        assert exc_info.value.status_code == 401

    def test_valid_token_decodes_correctly(self):
        """Valid token decodes to original claims."""
        token = create_access_token("user-1", "admin", "google", 5)
        payload = decode_token(token)
        assert payload["user_id"] == "user-1"
        assert payload["role"] == "admin"
        assert payload["auth_provider"] == "google"
        assert payload["token_version"] == "5"


class TestOAuthState:
    """Tests for OAuth state functions."""

    def test_create_and_decode_oauth_state(self):
        """Test OAuth state creation and decoding."""
        state = create_oauth_state(provider="google", purpose="login")

        payload = decode_oauth_state(state)
        assert payload is not None
        assert payload["provider"] == "google"
        assert payload["purpose"] == "login"
        assert payload["sub"] == "oauth_state"

    def test_decode_invalid_state_returns_none(self):
        """Test that decoding invalid state returns None."""
        result = decode_oauth_state("invalid-state")
        assert result is None

    def test_state_with_user_id(self):
        """Test OAuth state with user_id for linking."""
        state = create_oauth_state(
            provider="github",
            user_id="existing-user-id",
            purpose="link"
        )

        payload = decode_oauth_state(state)
        assert payload["user_id"] == "existing-user-id"
        assert payload["purpose"] == "link"


class TestOAuthStateSingleUse:
    """Tests for OAuth state replay protection."""

    def setup_method(self):
        """Clear consumed states before each test."""
        with _consumed_jtis_lock:
            _consumed_state_jtis.clear()

    def test_state_single_use_rejects_replay(self):
        """Same OAuth state cannot be used twice (replay protection)."""
        state = create_oauth_state(provider="google", purpose="login")
        first = decode_oauth_state(state)
        assert first is not None

        second = decode_oauth_state(state)
        assert second is None

    def test_state_without_user_id_for_login(self):
        """OAuth state for login does not include user_id."""
        state = create_oauth_state(provider="google", purpose="login")
        payload = decode_oauth_state(state)
        assert "user_id" not in payload

    def test_expired_state_rejected(self):
        """Expired OAuth state is rejected."""
        payload = {
            "jti": str(uuid.uuid4()),
            "sub": "oauth_state",
            "provider": "google",
            "purpose": "login",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=10),
            "iat": datetime.now(timezone.utc) - timedelta(minutes=20),
        }
        state = pyjwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        result = decode_oauth_state(state)
        assert result is None

    def test_invalid_sub_claim_rejected(self):
        """State with wrong 'sub' claim is rejected."""
        payload = {
            "jti": str(uuid.uuid4()),
            "sub": "not_oauth_state",
            "provider": "google",
            "purpose": "login",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            "iat": datetime.now(timezone.utc),
        }
        state = pyjwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        result = decode_oauth_state(state)
        assert result is None

    def test_missing_jti_rejected(self):
        """State without jti is rejected."""
        payload = {
            "sub": "oauth_state",
            "provider": "google",
            "purpose": "login",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            "iat": datetime.now(timezone.utc),
        }
        state = pyjwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        result = decode_oauth_state(state)
        assert result is None

    def test_concurrent_replay_protection(self):
        """Replay protection works under concurrent access."""
        state = create_oauth_state(provider="google", purpose="login")
        results = []
        barrier = threading.Barrier(5)

        def try_decode():
            barrier.wait()
            result = decode_oauth_state(state)
            results.append(result)

        threads = [threading.Thread(target=try_decode) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        successes = [r for r in results if r is not None]
        assert len(successes) == 1

    def test_cleanup_expired_consumed_jtis(self):
        """Expired entries are cleaned up from consumed dict."""
        with _consumed_jtis_lock:
            _consumed_state_jtis["expired-jti"] = datetime.now(timezone.utc) - timedelta(hours=1)

        state = create_oauth_state(provider="google", purpose="login")
        decode_oauth_state(state)

        with _consumed_jtis_lock:
            assert "expired-jti" not in _consumed_state_jtis


class TestTokenEdgeCases:
    """Edge cases for token handling."""

    def test_token_with_zero_version(self):
        """Token with version 0 is valid."""
        token = create_access_token("user-1", "admin", "local", 0)
        payload = decode_token(token)
        assert payload["token_version"] == "0"

    def test_token_with_special_chars_in_user_id(self):
        """Token with UUID-format user_id works."""
        uid = str(uuid.uuid4())
        token = create_access_token(uid, "admin", "local", 1)
        payload = decode_token(token)
        assert payload["user_id"] == uid

    def test_token_with_empty_role(self):
        """Token with empty role is technically valid (business logic validates)."""
        token = create_access_token("user-1", "", "local", 1)
        payload = decode_token(token)
        assert payload["role"] == ""

    def test_various_auth_providers(self):
        """Token works with all auth provider types."""
        for provider in ["local", "google", "github", "microsoft"]:
            token = create_access_token("user-1", "admin", provider, 1)
            payload = decode_token(token)
            assert payload["auth_provider"] == provider
