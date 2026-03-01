"""Configuration module for the copilot AI agent.

Loads and validates environment variables required for the agent to function.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

dotenv_path = Path(__file__).parents[2] / ".env"
load_dotenv(dotenv_path)


def _get_required_env(name: str) -> str:
    """Get a required environment variable or raise an error."""
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Required environment variable {name} is not set")
    return value


def _get_optional_env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Get an optional environment variable with a default value."""
    return os.getenv(name, default)


# LLM Service Configuration
OLLAMA_API_URL = _get_optional_env("OLLAMA_API_URL", "http://localhost:11434")

# Model Configuration
DEFAULT_OLLAMA_MODEL = "gpt-oss:20b"

# Database URLs - Required
VECTOR_DATABASE_URL = _get_required_env("VECTOR_DATABASE_URL")

# Qdrant Configuration
QDRANT_URL = _get_optional_env("QDRANT_URL")
QDRANT_API_KEY = _get_optional_env("QDRANT_API_KEY")
QDRANT_COLLECTION_NAME = _get_optional_env("QDRANT_COLLECTION_NAME", "past_issues_v2")

# Default settings
DEFAULT_LLM_TEMPERATURE = 0.33
DEFAULT_LLM_MAX_RETRIES = 2