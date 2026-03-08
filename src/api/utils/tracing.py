import os
import logging
from contextlib import contextmanager
from typing import Optional, Dict, Any

from src.api.services.encryption_service import decrypt_value

logger = logging.getLogger(__name__)


class DummyObservation:
    def update(self, **kwargs):
        pass
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def resolve_langfuse_config(settings) -> Optional[Dict[str, str]]:
    """Resolve Langfuse config from DB settings, falling back to env vars.

    Args:
        settings: The Setting ORM object (or None).

    Returns:
        Dict with secret_key, public_key, host — or None if not configured.
    """
    secret_key = None
    public_key = None
    host = None

    if settings and getattr(settings, "langfuse_secret_key_encrypted", None):
        try:
            secret_key = decrypt_value(settings.langfuse_secret_key_encrypted)
        except Exception as e:
            logger.warning(f"Failed to decrypt Langfuse secret key: {e}")
        public_key = getattr(settings, "langfuse_public_key", None)
        host = getattr(settings, "langfuse_base_url", None)

    if not secret_key:
        secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    if not public_key:
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    if not host:
        host = os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL")

    if secret_key and public_key and host:
        return {"secret_key": secret_key, "public_key": public_key, "host": host}
    return None

def get_langfuse_client(langfuse_config: Dict[str, str]):
    """Create a Langfuse client from explicit credentials."""
    from langfuse import Langfuse
    return Langfuse(
        secret_key=langfuse_config["secret_key"],
        public_key=langfuse_config["public_key"],
        host=langfuse_config["host"],
    )

def _get_observation_context(enabled: bool, langfuse_config: Optional[Dict[str, str]] = None, **kwargs):
    """Try to create a Langfuse observation context, return None on failure."""
    if not enabled:
        return None

    try:
        if langfuse_config:
            client = get_langfuse_client(langfuse_config)
        else:
            from langfuse import get_client
            client = get_client()
        return client.start_as_current_observation(**kwargs)
    except Exception as e:
        source = "config" if langfuse_config else "env"
        logger.warning(f"Failed to create Langfuse observation from {source}: {e}")
        return None


@contextmanager
def conditional_observation(enabled: bool, langfuse_config: Optional[Dict[str, str]] = None, **kwargs):
    """Context manager that creates a Langfuse observation span if enabled.

    Args:
        enabled: Whether tracing is enabled.
        langfuse_config: Dict with secret_key, public_key, host. If None, falls back to env-based client.
        **kwargs: Passed to langfuse.start_as_current_observation().
    """
    ctx = _get_observation_context(enabled, langfuse_config, **kwargs)
    if ctx is not None:
        with ctx as obs:
            yield obs
    else:
        yield DummyObservation()
