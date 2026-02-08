"""Tests for authentication module."""

import os
import pytest
from unittest.mock import patch


class TestPasswordValidation:
    """Tests for password validation."""

    def test_weak_password_rejected_when_validation_enabled(self):
        """Test that weak passwords are rejected when validation is enabled."""
        with patch.dict(os.environ, {"ENABLE_PASSWORD_VALIDATION": "true"}):
            # Reimport to get fresh validation state
            import importlib
            import src.api.core.config as config_module
            importlib.reload(config_module)

            import src.api.auth.schemas as schemas_module
            importlib.reload(schemas_module)

            from pydantic import ValidationError
            from src.api.auth.schemas import PasswordUpdate

            # Too short
            with pytest.raises(ValidationError) as exc_info:
                PasswordUpdate(password="short")
            assert "at least 12 characters" in str(exc_info.value)

    def test_password_without_uppercase_rejected(self):
        """Test password without uppercase letter is rejected."""
        with patch.dict(os.environ, {"ENABLE_PASSWORD_VALIDATION": "true"}):
            import importlib
            import src.api.core.config as config_module
            importlib.reload(config_module)

            import src.api.auth.schemas as schemas_module
            importlib.reload(schemas_module)

            from pydantic import ValidationError
            from src.api.auth.schemas import PasswordUpdate

            with pytest.raises(ValidationError) as exc_info:
                PasswordUpdate(password="lowercaseonly123!")
            assert "one uppercase letter" in str(exc_info.value)

    def test_password_without_special_char_rejected(self):
        """Test password without special character is rejected."""
        with patch.dict(os.environ, {"ENABLE_PASSWORD_VALIDATION": "true"}):
            import importlib
            import src.api.core.config as config_module
            importlib.reload(config_module)

            import src.api.auth.schemas as schemas_module
            importlib.reload(schemas_module)

            from pydantic import ValidationError
            from src.api.auth.schemas import PasswordUpdate

            with pytest.raises(ValidationError) as exc_info:
                PasswordUpdate(password="NoSpecialChar123")
            assert "one special character" in str(exc_info.value)

    def test_strong_password_accepted(self):
        """Test that a strong password is accepted."""
        with patch.dict(os.environ, {"ENABLE_PASSWORD_VALIDATION": "true"}):
            import importlib
            import src.api.core.config as config_module
            importlib.reload(config_module)

            import src.api.auth.schemas as schemas_module
            importlib.reload(schemas_module)

            from src.api.auth.schemas import PasswordUpdate

            # This should not raise
            update = PasswordUpdate(password="StrongP@ssw0rd!")
            assert update.password == "StrongP@ssw0rd!"

    def test_weak_password_accepted_when_validation_disabled(self):
        """Test that weak passwords are accepted when validation is disabled."""
        with patch.dict(os.environ, {"ENABLE_PASSWORD_VALIDATION": "false"}):
            import importlib
            import src.api.core.config as config_module
            importlib.reload(config_module)

            import src.api.auth.schemas as schemas_module
            importlib.reload(schemas_module)

            from src.api.auth.schemas import PasswordUpdate

            # This should not raise even with weak password
            update = PasswordUpdate(password="weak")
            assert update.password == "weak"


class TestUserSignup:
    """Tests for UserSignup schema."""

    def test_valid_signup(self):
        """Test valid signup data."""
        with patch.dict(os.environ, {"ENABLE_PASSWORD_VALIDATION": "false"}):
            import importlib
            import src.api.core.config as config_module
            importlib.reload(config_module)

            import src.api.auth.schemas as schemas_module
            importlib.reload(schemas_module)

            from src.api.auth.schemas import UserSignup

            signup = UserSignup(
                email="test@example.com",
                password="testpassword"
            )
            assert signup.email == "test@example.com"

    def test_invalid_email_rejected(self):
        """Test that invalid email is rejected."""
        with patch.dict(os.environ, {"ENABLE_PASSWORD_VALIDATION": "false"}):
            import importlib
            import src.api.core.config as config_module
            importlib.reload(config_module)

            import src.api.auth.schemas as schemas_module
            importlib.reload(schemas_module)

            from pydantic import ValidationError
            from src.api.auth.schemas import UserSignup

            with pytest.raises(ValidationError):
                UserSignup(email="not-an-email", password="testpassword")
