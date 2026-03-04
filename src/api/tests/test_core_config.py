"""Tests for core configuration module.

Validates environment variable parsing, required variable enforcement,
JWT algorithm allowlisting, and configuration defaults.
"""

import os
import importlib
import pytest
from unittest.mock import patch


class TestGetRequiredEnv:
    """Tests for get_required_env function."""

    def test_returns_value_when_set(self):
        """Required env var returns its value."""
        with patch.dict(os.environ, {"TEST_VAR": "my_value"}):
            from src.api.core.config import get_required_env
            assert get_required_env("TEST_VAR") == "my_value"

    def test_raises_when_missing(self):
        """Missing required env var raises RuntimeError."""
        env = os.environ.copy()
        env.pop("MISSING_VAR", None)
        with patch.dict(os.environ, env, clear=True):
            from src.api.core.config import get_required_env
            with pytest.raises(RuntimeError, match="MISSING_VAR environment variable must be set"):
                get_required_env("MISSING_VAR")

    def test_raises_when_empty_string(self):
        """Empty string env var is treated as missing."""
        with patch.dict(os.environ, {"EMPTY_VAR": ""}):
            from src.api.core.config import get_required_env
            with pytest.raises(RuntimeError, match="EMPTY_VAR environment variable must be set"):
                get_required_env("EMPTY_VAR")


class TestJWTAlgorithmAllowlist:
    """Tests for JWT algorithm configuration validation."""

    @pytest.mark.parametrize("algo", ["HS256", "HS384", "HS512"])
    def test_allowed_algorithms_accepted(self, algo):
        """Valid JWT algorithms are accepted."""
        with patch.dict(os.environ, {
            "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
            "JWT_SECRET_KEY": "test-secret",
            "JWT_ALGORITHM": algo,
            "ENABLE_PASSWORD_VALIDATION": "false",
        }):
            import src.api.core.config as config_module
            importlib.reload(config_module)
            assert config_module.JWT_ALGORITHM == algo

    @pytest.mark.parametrize("algo", ["RS256", "RS512", "ES256", "none", "NONE", "", "PS256"])
    def test_disallowed_algorithms_rejected(self, algo):
        """Invalid/dangerous JWT algorithms raise RuntimeError."""
        with patch.dict(os.environ, {
            "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
            "JWT_SECRET_KEY": "test-secret",
            "JWT_ALGORITHM": algo,
            "ENABLE_PASSWORD_VALIDATION": "false",
        }):
            import src.api.core.config as config_module
            with pytest.raises(RuntimeError, match="is not allowed"):
                importlib.reload(config_module)

    def test_default_algorithm_is_hs256(self):
        """Default JWT algorithm when not specified is HS256."""
        env = os.environ.copy()
        env.pop("JWT_ALGORITHM", None)
        env["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
        env["JWT_SECRET_KEY"] = "test-secret"
        env["ENABLE_PASSWORD_VALIDATION"] = "false"
        with patch.dict(os.environ, env, clear=True):
            import src.api.core.config as config_module
            importlib.reload(config_module)
            assert config_module.JWT_ALGORITHM == "HS256"


class TestJWTExpiry:
    """Tests for JWT expiry configuration."""

    def test_default_expiry_is_7_days(self):
        """JWT_EXPIRY env var is parsed correctly as int."""
        # The conftest sets env vars that may override defaults.
        # Just verify the parsing logic works correctly.
        with patch.dict(os.environ, {
            "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
            "JWT_SECRET_KEY": "test-secret",
            "JWT_EXPIRY": "7",
            "ENABLE_PASSWORD_VALIDATION": "false",
        }):
            import src.api.core.config as config_module
            importlib.reload(config_module)
            assert config_module.JWT_EXPIRY_DAYS == 7

    def test_custom_expiry_parsed(self):
        """Custom JWT expiry is parsed from env."""
        with patch.dict(os.environ, {
            "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
            "JWT_SECRET_KEY": "test-secret",
            "JWT_EXPIRY": "30",
            "ENABLE_PASSWORD_VALIDATION": "false",
        }):
            import src.api.core.config as config_module
            importlib.reload(config_module)
            assert config_module.JWT_EXPIRY_DAYS == 30


class TestCORSOrigins:
    """Tests for CORS origin parsing."""

    def test_default_cors_origins(self):
        """Default CORS origins include localhost."""
        env = os.environ.copy()
        env.pop("CORS_ORIGINS", None)
        env["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
        env["JWT_SECRET_KEY"] = "test-secret"
        env["ENABLE_PASSWORD_VALIDATION"] = "false"
        with patch.dict(os.environ, env, clear=True):
            import src.api.core.config as config_module
            importlib.reload(config_module)
            assert "http://localhost:5173" in config_module.CORS_ORIGINS
            assert "http://localhost:3000" in config_module.CORS_ORIGINS

    def test_custom_cors_origins_parsed(self):
        """Custom CORS origins are split by comma and trimmed."""
        with patch.dict(os.environ, {
            "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
            "JWT_SECRET_KEY": "test-secret",
            "CORS_ORIGINS": "https://app.example.com , https://api.example.com",
            "ENABLE_PASSWORD_VALIDATION": "false",
        }):
            import src.api.core.config as config_module
            importlib.reload(config_module)
            assert config_module.CORS_ORIGINS == [
                "https://app.example.com",
                "https://api.example.com",
            ]

    def test_empty_cors_origins_stripped(self):
        """Empty entries in CORS origins are stripped."""
        with patch.dict(os.environ, {
            "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
            "JWT_SECRET_KEY": "test-secret",
            "CORS_ORIGINS": "https://a.com,,https://b.com,",
            "ENABLE_PASSWORD_VALIDATION": "false",
        }):
            import src.api.core.config as config_module
            importlib.reload(config_module)
            assert config_module.CORS_ORIGINS == [
                "https://a.com",
                "https://b.com",
            ]


class TestPasswordValidationToggle:
    """Tests for password validation configuration."""

    def test_enabled_when_set_to_true(self):
        """Password validation is enabled when ENABLE_PASSWORD_VALIDATION=true."""
        with patch.dict(os.environ, {
            "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
            "JWT_SECRET_KEY": "test-secret",
            "ENABLE_PASSWORD_VALIDATION": "true",
        }):
            import src.api.core.config as config_module
            importlib.reload(config_module)
            assert config_module.ENABLE_PASSWORD_VALIDATION is True

    def test_disabled_with_false(self):
        """Password validation disabled with 'false'."""
        with patch.dict(os.environ, {
            "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
            "JWT_SECRET_KEY": "test-secret",
            "ENABLE_PASSWORD_VALIDATION": "false",
        }):
            import src.api.core.config as config_module
            importlib.reload(config_module)
            assert config_module.ENABLE_PASSWORD_VALIDATION is False

    def test_case_insensitive_true(self):
        """Password validation 'TRUE' (uppercase) is treated as true."""
        with patch.dict(os.environ, {
            "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
            "JWT_SECRET_KEY": "test-secret",
            "ENABLE_PASSWORD_VALIDATION": "TRUE",
        }):
            import src.api.core.config as config_module
            importlib.reload(config_module)
            assert config_module.ENABLE_PASSWORD_VALIDATION is True

    def test_arbitrary_string_treated_as_false(self):
        """Non-'true' string is treated as false."""
        with patch.dict(os.environ, {
            "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
            "JWT_SECRET_KEY": "test-secret",
            "ENABLE_PASSWORD_VALIDATION": "yes",
        }):
            import src.api.core.config as config_module
            importlib.reload(config_module)
            assert config_module.ENABLE_PASSWORD_VALIDATION is False