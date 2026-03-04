"""Tests for authentication module.

Covers password validation schemas, signup schemas, and core
security functions (bcrypt hashing and verification).
"""

import os
import pytest
from unittest.mock import patch

from src.api.core.security import get_password_hash, verify_password


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

class TestPasswordHashing:
    """Tests for get_password_hash function."""

    def test_returns_bcrypt_hash(self):
        """Hash output starts with bcrypt prefix."""
        hashed = get_password_hash("mypassword")
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    def test_different_passwords_produce_different_hashes(self):
        """Different passwords produce different hashes."""
        h1 = get_password_hash("password1")
        h2 = get_password_hash("password2")
        assert h1 != h2

    def test_same_password_produces_different_hashes_due_to_salt(self):
        """Same password hashed twice produces different results (salting)."""
        h1 = get_password_hash("same_password")
        h2 = get_password_hash("same_password")
        assert h1 != h2

    def test_empty_string_can_be_hashed(self):
        """Empty string password can be hashed (validation is a separate layer)."""
        hashed = get_password_hash("")
        assert hashed and len(hashed) > 0

    def test_unicode_password_hashed(self):
        """Unicode password can be hashed."""
        hashed = get_password_hash("P@$$w0rd_\u00fc\u00f1\u00ee\u00e7\u00f6de!")
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    def test_very_long_password(self):
        """Very long password can be hashed (bcrypt truncates at 72 bytes)."""
        long_password = "A" * 200
        hashed = get_password_hash(long_password)
        assert verify_password(long_password, hashed)


class TestPasswordVerification:
    """Tests for verify_password function."""

    def test_correct_password_verifies(self):
        """Correct password passes verification."""
        hashed = get_password_hash("correct_password")
        assert verify_password("correct_password", hashed) is True

    def test_wrong_password_fails(self):
        """Wrong password fails verification."""
        hashed = get_password_hash("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_case_sensitive(self):
        """Password verification is case-sensitive."""
        hashed = get_password_hash("Password")
        assert verify_password("password", hashed) is False
        assert verify_password("PASSWORD", hashed) is False
        assert verify_password("Password", hashed) is True

    def test_whitespace_significant(self):
        """Leading/trailing whitespace is significant in passwords."""
        hashed = get_password_hash("password")
        assert verify_password(" password", hashed) is False
        assert verify_password("password ", hashed) is False

    def test_special_characters_in_password(self):
        """Special characters are handled correctly."""
        special_pw = "P@$$w0rd!#%^&*(){}[]|\\:\";<>?/"
        hashed = get_password_hash(special_pw)
        assert verify_password(special_pw, hashed) is True

    def test_unicode_password_round_trip(self):
        """Unicode password verifies after round-trip."""
        unicode_pw = "\u0422\u0435\u0441\u0442\u041f\u0430\u0440\u043e\u043b\u044c123!"
        hashed = get_password_hash(unicode_pw)
        assert verify_password(unicode_pw, hashed) is True

    def test_null_bytes_in_password_rejected(self):
        """Password with null bytes is rejected by bcrypt."""
        from passlib.exc import PasswordValueError
        pw_with_null = "pass\x00word"
        with pytest.raises(PasswordValueError):
            get_password_hash(pw_with_null)
