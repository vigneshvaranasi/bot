"""Tests for configuration module."""

import os
import pytest
from unittest.mock import patch


class TestGetRequiredEnv:
    """Tests for get_required_env function."""

    def test_returns_value_when_set(self):
        """Test that get_required_env returns the value when env var is set."""
        with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
            # Import fresh to get the function
            from src.api.core.config import get_required_env
            result = get_required_env("TEST_VAR")
            assert result == "test_value"

    def test_raises_when_not_set(self):
        """Test that get_required_env raises RuntimeError when env var is not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Need to reimport to test with cleared env
            import importlib
            import src.api.core.config as config_module

            # Test the function directly
            with pytest.raises(RuntimeError, match="NONEXISTENT_VAR environment variable must be set"):
                config_module.get_required_env("NONEXISTENT_VAR")

    def test_raises_when_empty(self):
        """Test that get_required_env raises RuntimeError when env var is empty."""
        with patch.dict(os.environ, {"EMPTY_VAR": ""}):
            from src.api.core.config import get_required_env
            with pytest.raises(RuntimeError, match="EMPTY_VAR environment variable must be set"):
                get_required_env("EMPTY_VAR")


class TestPasswordValidationToggle:
    """Tests for password validation toggle."""

    def test_validation_enabled_by_default(self):
        """Test that password validation is enabled by default."""
        with patch.dict(os.environ, {
            "JWT_SECRET_KEY": "test",
            "DATABASE_URL": "sqlite:///:memory:",
        }, clear=False):
            # Remove the toggle to test default
            os.environ.pop("ENABLE_PASSWORD_VALIDATION", None)

            import importlib
            import src.api.core.config as config_module
            importlib.reload(config_module)

            # Default should be True
            assert config_module.ENABLE_PASSWORD_VALIDATION is True

    def test_validation_disabled_when_false(self):
        """Test that password validation can be disabled."""
        with patch.dict(os.environ, {
            "JWT_SECRET_KEY": "test",
            "DATABASE_URL": "sqlite:///:memory:",
            "ENABLE_PASSWORD_VALIDATION": "false",
        }):
            import importlib
            import src.api.core.config as config_module
            importlib.reload(config_module)

            assert config_module.ENABLE_PASSWORD_VALIDATION is False


class TestCorsOrigins:
    """Tests for CORS origins configuration."""

    def test_default_origins(self):
        """Test default CORS origins when not specified."""
        with patch.dict(os.environ, {
            "JWT_SECRET_KEY": "test",
            "DATABASE_URL": "sqlite:///:memory:",
        }):
            os.environ.pop("CORS_ORIGINS", None)

            import importlib
            import src.api.core.config as config_module
            importlib.reload(config_module)

            assert "http://localhost:5173" in config_module.CORS_ORIGINS
            assert "http://localhost:3000" in config_module.CORS_ORIGINS

    def test_custom_origins(self):
        """Test custom CORS origins from environment."""
        with patch.dict(os.environ, {
            "JWT_SECRET_KEY": "test",
            "DATABASE_URL": "sqlite:///:memory:",
            "CORS_ORIGINS": "https://example.com,https://app.example.com",
        }):
            import importlib
            import src.api.core.config as config_module
            importlib.reload(config_module)

            assert "https://example.com" in config_module.CORS_ORIGINS
            assert "https://app.example.com" in config_module.CORS_ORIGINS
