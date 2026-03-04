"""Tests for encryption service (Fernet symmetric encryption).

Validates encrypt/decrypt round-trips, empty value handling,
key management, and error conditions.
"""

import os
import pytest
from unittest.mock import patch
from cryptography.fernet import Fernet, InvalidToken


class TestEncryptDecryptRoundTrip:
    """Tests for encrypt_value and decrypt_value."""

    def test_round_trip_basic_string(self):
        """Encrypted value decrypts back to original."""
        from src.api.services.encryption_service import encrypt_value, decrypt_value
        original = "sk-abc123-test-api-key"
        encrypted = encrypt_value(original)
        decrypted = decrypt_value(encrypted)
        assert decrypted == original

    def test_encrypted_value_differs_from_plaintext(self):
        """Encrypted value is not the same as plaintext."""
        from src.api.services.encryption_service import encrypt_value
        original = "my-secret-key"
        encrypted = encrypt_value(original)
        assert encrypted != original

    def test_same_plaintext_produces_different_ciphertext(self):
        """Same plaintext encrypted twice produces different ciphertext (Fernet uses random IV)."""
        from src.api.services.encryption_service import encrypt_value
        original = "duplicate-test"
        e1 = encrypt_value(original)
        e2 = encrypt_value(original)
        assert e1 != e2  # Different IVs

    def test_round_trip_unicode(self):
        """Unicode content survives encrypt/decrypt."""
        from src.api.services.encryption_service import encrypt_value, decrypt_value
        original = "API-KEY-\u00fc\u00f1\u00ee\u00e7\u00f6de-\U0001f511"
        encrypted = encrypt_value(original)
        assert decrypt_value(encrypted) == original

    def test_round_trip_long_string(self):
        """Long strings (e.g., PEM keys) survive round-trip."""
        from src.api.services.encryption_service import encrypt_value, decrypt_value
        original = "A" * 10000
        encrypted = encrypt_value(original)
        assert decrypt_value(encrypted) == original

    def test_round_trip_special_characters(self):
        """Special characters survive round-trip."""
        from src.api.services.encryption_service import encrypt_value, decrypt_value
        original = '{"key": "value", "special": "!@#$%^&*()"}'
        encrypted = encrypt_value(original)
        assert decrypt_value(encrypted) == original


class TestEmptyValues:
    """Tests for empty/None value handling."""

    def test_encrypt_empty_string_returns_empty(self):
        """Encrypting empty string returns empty string."""
        from src.api.services.encryption_service import encrypt_value
        assert encrypt_value("") == ""

    def test_decrypt_empty_string_returns_empty(self):
        """Decrypting empty string returns empty string."""
        from src.api.services.encryption_service import decrypt_value
        assert decrypt_value("") == ""

    def test_encrypt_none_returns_empty(self):
        """Encrypting None returns empty string."""
        from src.api.services.encryption_service import encrypt_value
        assert encrypt_value(None) == ""

    def test_decrypt_none_returns_empty(self):
        """Decrypting None returns empty string."""
        from src.api.services.encryption_service import decrypt_value
        assert decrypt_value(None) == ""


class TestInvalidCiphertext:
    """Tests for invalid decryption scenarios."""

    def test_decrypt_garbage_raises(self):
        """Decrypting invalid ciphertext raises InvalidToken."""
        from src.api.services.encryption_service import decrypt_value
        with pytest.raises(InvalidToken):
            decrypt_value("this-is-not-valid-ciphertext")

    def test_decrypt_tampered_ciphertext_raises(self):
        """Tampered ciphertext raises InvalidToken."""
        from src.api.services.encryption_service import encrypt_value, decrypt_value
        encrypted = encrypt_value("original-secret")
        # Tamper with the ciphertext
        tampered = encrypted[:-5] + "XXXXX"
        with pytest.raises((InvalidToken, Exception)):
            decrypt_value(tampered)

    def test_decrypt_truncated_ciphertext_raises(self):
        """Truncated ciphertext raises error."""
        from src.api.services.encryption_service import encrypt_value, decrypt_value
        encrypted = encrypt_value("test-secret")
        truncated = encrypted[:10]
        with pytest.raises((InvalidToken, Exception)):
            decrypt_value(truncated)


class TestEncryptionKeyManagement:
    """Tests for encryption key handling."""

    def test_missing_encryption_key_raises(self):
        """Missing ENCRYPTION_KEY env var raises RuntimeError."""
        from src.api.services.encryption_service import get_fernet
        # Clear the lru_cache
        get_fernet.cache_clear()
        with patch.dict(os.environ, {}, clear=False):
            env = os.environ.copy()
            env.pop("ENCRYPTION_KEY", None)
            with patch.dict(os.environ, env, clear=True):
                with pytest.raises(RuntimeError, match="ENCRYPTION_KEY"):
                    get_fernet()
        # Restore cache
        get_fernet.cache_clear()

    def test_invalid_fernet_key_raises(self):
        """Invalid Fernet key raises ValueError."""
        from src.api.services.encryption_service import get_fernet
        get_fernet.cache_clear()
        with patch.dict(os.environ, {"ENCRYPTION_KEY": "not-a-valid-fernet-key"}):
            with pytest.raises(Exception):  # ValueError or binascii.Error
                get_fernet()
        get_fernet.cache_clear()

    def test_wrong_key_cannot_decrypt(self):
        """Ciphertext encrypted with one key cannot be decrypted with another."""
        key1 = Fernet.generate_key()
        key2 = Fernet.generate_key()
        f1 = Fernet(key1)
        f2 = Fernet(key2)
        encrypted = f1.encrypt(b"secret").decode()
        with pytest.raises(InvalidToken):
            f2.decrypt(encrypted.encode())


class TestEncryptionErrorPaths:
    """Tests for generic error branches in encrypt/decrypt."""

    def test_encrypt_value_logs_and_raises_on_error(self, caplog):
        """If underlying Fernet.encrypt raises, encrypt_value logs and re-raises."""
        from src.api.services.encryption_service import encrypt_value

        class BadFernet:
            def encrypt(self, data: bytes):
                raise RuntimeError("boom")

        with patch(
            "src.api.services.encryption_service.get_fernet",
            return_value=BadFernet(),
        ):
            with pytest.raises(RuntimeError):
                encrypt_value("secret")

        assert any("Encryption failed" in msg for _, _, msg in caplog.record_tuples)

    def test_decrypt_value_logs_and_raises_on_generic_error(self, caplog):
        """If underlying Fernet.decrypt raises non-InvalidToken, decrypt_value logs and re-raises."""
        from src.api.services.encryption_service import decrypt_value

        class BadFernet:
            def decrypt(self, data: bytes):
                raise ValueError("generic failure")

        with patch(
            "src.api.services.encryption_service.get_fernet",
            return_value=BadFernet(),
        ):
            with pytest.raises(ValueError):
                decrypt_value("ciphertext")

        assert any("Decryption failed" in msg for _, _, msg in caplog.record_tuples)