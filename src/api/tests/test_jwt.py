"""Tests for JWT utilities."""

import pytest
from datetime import timedelta
from jose import jwt
from fastapi import HTTPException


class TestCreateAccessToken:
    """Tests for create_access_token function."""

    def test_creates_valid_jwt(self):
        """Test that create_access_token creates a valid JWT."""
        from src.api.core.jwt import create_access_token, SECRET_KEY, ALGORITHM

        token = create_access_token(
            user_id="test-user-id",
            role="user",
            auth_provider="local",
            token_version=1
        )

        # Verify it's a valid JWT
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["user_id"] == "test-user-id"
        assert payload["role"] == "user"
        assert payload["auth_provider"] == "local"
        assert payload["token_version"] == "1"
        assert "exp" in payload
        assert "iat" in payload
        assert "jti" in payload

    def test_custom_expiration(self):
        """Test that custom expiration delta is respected."""
        from src.api.core.jwt import create_access_token, SECRET_KEY, ALGORITHM
        from datetime import datetime, timezone

        # Create token with 1 minute expiration
        token = create_access_token(
            user_id="test-user",
            role="admin",
            auth_provider="google",
            token_version=2,
            expires_delta=timedelta(minutes=1)
        )

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp = payload["exp"]
        iat = payload["iat"]

        # Expiration should be about 60 seconds after issued at
        assert 55 <= (exp - iat) <= 65


class TestDecodeToken:
    """Tests for decode_token function."""

    def test_decodes_valid_token(self):
        """Test that decode_token correctly decodes a valid token."""
        from src.api.core.jwt import create_access_token, decode_token

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
        from src.api.core.jwt import decode_token

        with pytest.raises(HTTPException) as exc_info:
            decode_token("invalid-token")

        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in str(exc_info.value.detail)

    def test_raises_on_expired_token(self):
        """Test that decode_token raises HTTPException for expired token."""
        from src.api.core.jwt import create_access_token, decode_token

        # Create token that's already expired
        token = create_access_token(
            user_id="test-user",
            role="user",
            auth_provider="local",
            token_version=1,
            expires_delta=timedelta(seconds=-10)  # Expired 10 seconds ago
        )

        with pytest.raises(HTTPException) as exc_info:
            decode_token(token)

        assert exc_info.value.status_code == 401


class TestOAuthState:
    """Tests for OAuth state functions."""

    def test_create_and_decode_oauth_state(self):
        """Test OAuth state creation and decoding."""
        from src.api.core.jwt import create_oauth_state, decode_oauth_state

        state = create_oauth_state(provider="google", purpose="login")

        payload = decode_oauth_state(state)
        assert payload is not None
        assert payload["provider"] == "google"
        assert payload["purpose"] == "login"
        assert payload["sub"] == "oauth_state"

    def test_decode_invalid_state_returns_none(self):
        """Test that decoding invalid state returns None."""
        from src.api.core.jwt import decode_oauth_state

        result = decode_oauth_state("invalid-state")
        assert result is None

    def test_state_with_user_id(self):
        """Test OAuth state with user_id for linking."""
        from src.api.core.jwt import create_oauth_state, decode_oauth_state

        state = create_oauth_state(
            provider="github",
            user_id="existing-user-id",
            purpose="link"
        )

        payload = decode_oauth_state(state)
        assert payload["user_id"] == "existing-user-id"
        assert payload["purpose"] == "link"
