"""Tests for tracing helpers (create_langfuse_trace, DummyObservation)."""

from unittest.mock import patch, MagicMock

from src.api.utils.tracing import create_langfuse_trace, DummyObservation


def test_create_langfuse_trace_disabled_returns_none():
    """When enabled=False, returns (None, None) regardless of config."""
    span, trace_ctx = create_langfuse_trace(enabled=False, name="test-disabled")
    assert span is None
    assert trace_ctx is None


def test_create_langfuse_trace_enabled_with_config():
    """When enabled=True with langfuse_config, creates a span and returns trace_context."""
    mock_span = MagicMock()
    mock_span.trace_id = "a" * 32
    mock_span.id = "b" * 16

    mock_client = MagicMock()
    mock_client.start_span.return_value = mock_span

    config = {"secret_key": "sk-test", "public_key": "pk-test", "host": "http://localhost:3000"}

    with patch("src.api.utils.tracing.get_langfuse_client", return_value=mock_client):
        span, trace_ctx = create_langfuse_trace(
            enabled=True, langfuse_config=config, name="test-enabled", input="hello"
        )
        assert span is mock_span
        assert trace_ctx == {"trace_id": "a" * 32, "parent_span_id": "b" * 16}
        mock_client.start_span.assert_called_once_with(name="test-enabled", input="hello")


def test_create_langfuse_trace_enabled_error_returns_none():
    """When Langfuse client creation fails, gracefully returns (None, None)."""
    config = {"secret_key": "bad", "public_key": "bad", "host": "bad"}

    with patch("src.api.utils.tracing.get_langfuse_client", side_effect=Exception("connection error")):
        span, trace_ctx = create_langfuse_trace(
            enabled=True, langfuse_config=config, name="test-error"
        )
        assert span is None
        assert trace_ctx is None


def test_dummy_observation_context_manager_noop():
    """DummyObservation acts as a no-op context manager."""
    dummy = DummyObservation()
    with dummy as obs:
        assert obs is dummy
