import os
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple

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

_LANGFUSE_INITIALIZED = False
_LANGFUSE_CONFIG_SIGNATURE: Optional[Tuple[str, str, str]] = None

_SENSITIVE_KEY_SUBSTRINGS = (
    "api_key",
    "apikey",
    "secret_key",
    "secretkey",
    "secret",
    "password",
    "passwd",
    "access_token",
    "refresh_token",
    "authorization",
    "auth_token",
    "bearer",
    "private_key",
    "client_secret",
)

_REDACTED = "[REDACTED]"


def _is_sensitive_key(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    lowered = key.lower()
    return any(token in lowered for token in _SENSITIVE_KEY_SUBSTRINGS)


def mask_sensitive_data(data: Any, **kwargs) -> Any:
    """Recursively redact secrets from trace payloads before export.

    Passed as ``mask`` to the Langfuse client so every input, output, and
    metadata value routed through the SDK is sanitized — including graph
    state captured automatically by the LangChain CallbackHandler.
    """
    try:
        if isinstance(data, dict):
            return {
                k: (_REDACTED if _is_sensitive_key(k) else mask_sensitive_data(v))
                for k, v in data.items()
            }
        if isinstance(data, (list, tuple)):
            masked = [mask_sensitive_data(item) for item in data]
            return type(data)(masked) if isinstance(data, tuple) else masked
        return data
    except Exception as e:
        logger.warning(f"Langfuse masking function failed: {e}")
        return _REDACTED


def get_langfuse_client(langfuse_config: Optional[Dict[str, str]] = None):
    """
    Get a Langfuse client that is shared between observations and LangChain callbacks.

    If explicit credentials are provided, we initialize the global client once via
    Langfuse(...). Subsequent calls (including those from CallbackHandler which uses
    get_client()) will reuse the same client instance.

    If no config is provided, this falls back to env-based configuration.
    """
    from langfuse import Langfuse, get_client

    global _LANGFUSE_INITIALIZED, _LANGFUSE_CONFIG_SIGNATURE

    if langfuse_config:
        cfg_sig = (
            langfuse_config.get("secret_key"),
            langfuse_config.get("public_key"),
            langfuse_config.get("host"),
        )
        if not _LANGFUSE_INITIALIZED or _LANGFUSE_CONFIG_SIGNATURE != cfg_sig:
            Langfuse(
                secret_key=langfuse_config.get("secret_key"),
                public_key=langfuse_config.get("public_key"),
                host=langfuse_config.get("host"),
                mask=mask_sensitive_data,
            )
            _LANGFUSE_INITIALIZED = True
            _LANGFUSE_CONFIG_SIGNATURE = cfg_sig

    return get_client()

def create_langfuse_trace(
    enabled: bool,
    langfuse_config: Optional[Dict[str, str]] = None,
    **kwargs,
) -> Tuple[Any, Optional[Dict[str, str]]]:
    """Create a Langfuse trace and return (span, trace_context).

    Creates a top-level span whose trace_context dict can be passed to
    CallbackHandler(trace_context=...) so that all LangChain observations
    are grouped under a single Langfuse trace as children of this span.

    Args:
        enabled: Whether tracing is enabled.
        langfuse_config: Dict with secret_key, public_key, host.
        **kwargs: Passed to client.start_span() (name, input, metadata, …).

    Returns:
        (span, trace_context) when tracing is enabled and succeeds,
        (None, None) otherwise.
        trace_context is {"trace_id": ..., "parent_span_id": ...}.
    """
    if not enabled:
        return None, None

    try:
        client = get_langfuse_client(langfuse_config)
        span = client.start_span(**kwargs)
        trace_context = {
            "trace_id": span.trace_id,
            "parent_span_id": span.id,
        }
        return span, trace_context
    except Exception as e:
        source = "config" if langfuse_config else "env"
        logger.warning(f"Failed to create Langfuse trace from {source}: {e}")
        return None, None


def update_langfuse_trace_name(
    trace_id: str,
    name: str,
    langfuse_config: Optional[Dict[str, str]] = None,
) -> None:
    """Update a Langfuse trace's name via the v2 ingestion API.

    The OTel-based SDK sets AS_ROOT on every observation created with
    trace_context, so multiple spans compete for the trace name. This
    function sends a v2 trace-create ingestion event (upsert) to
    explicitly set the trace name after all OTel spans are exported.
    """
    try:
        from langfuse.api.resources.ingestion.types import (
            IngestionEvent_TraceCreate,
        )
        from langfuse.api.resources.ingestion.types.trace_body import TraceBody

        client = get_langfuse_client(langfuse_config)
        client.flush()

        client.api.ingestion.batch(
            batch=[
                IngestionEvent_TraceCreate(
                    body=TraceBody(id=trace_id, name=name),
                    id=str(uuid.uuid4()),
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
            ]
        )
    except Exception as e:
        logger.warning(f"Failed to update Langfuse trace name: {e}")
