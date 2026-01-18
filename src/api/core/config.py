"""Centralized configuration with environment variable validation.

This module provides validated environment variables and configuration constants
used throughout the application. Required variables are validated at startup.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def get_required_env(key: str) -> str:
    """Get a required environment variable or raise an error.

    Args:
        key: The environment variable name.

    Returns:
        The environment variable value.

    Raises:
        RuntimeError: If the environment variable is not set.
    """
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"{key} environment variable must be set")
    return value


# Database configuration
DATABASE_URL = get_required_env("DATABASE_URL")

# JWT configuration
JWT_SECRET_KEY = get_required_env("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRY_DAYS = int(os.getenv("JWT_EXPIRY", "7"))

# CORS configuration
CORS_ORIGINS_STR = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000,https://localhost:5173,https://localhost:3000"
)
CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_STR.split(",") if origin.strip()]

# Password validation toggle (enterprise default: enabled)
ENABLE_PASSWORD_VALIDATION = os.getenv("ENABLE_PASSWORD_VALIDATION", "true").lower() == "true"
