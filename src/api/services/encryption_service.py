"""Encryption service for sensitive data using Fernet symmetric encryption.

This service provides functions to encrypt and decrypt sensitive data like API keys
stored in the database. Uses Fernet symmetric encryption with a key from environment.
"""

import os
import logging
from functools import lru_cache
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


@lru_cache()
def get_fernet() -> Fernet:
    """Get Fernet instance with key from environment.

    The key is cached for performance. Generate a new key with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

    Raises:
        RuntimeError: If ENCRYPTION_KEY environment variable is not set.
    """
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise RuntimeError(
            "ENCRYPTION_KEY environment variable must be set. "
            "Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode())


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value using Fernet.

    Args:
        plaintext: The string to encrypt.

    Returns:
        The encrypted string, or empty string if input is empty/None.
    """
    if not plaintext:
        return ""
    try:
        return get_fernet().encrypt(plaintext.encode()).decode()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise


def decrypt_value(ciphertext: str) -> str:
    """Decrypt an encrypted string value.

    Args:
        ciphertext: The encrypted string to decrypt.

    Returns:
        The decrypted plaintext string, or empty string if input is empty/None.

    Raises:
        InvalidToken: If the ciphertext is invalid or corrupted.
    """
    if not ciphertext:
        return ""
    try:
        return get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        logger.error("Failed to decrypt value - invalid token")
        raise
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise
