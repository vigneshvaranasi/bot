"""Tests for tracing.conditional_observation helper."""

from unittest.mock import patch, MagicMock

from src.api.utils.tracing import conditional_observation, DummyObservation


def test_conditional_observation_disabled_uses_dummy():
    """When enabled=False, returns DummyObservation regardless of config."""
    with conditional_observation(enabled=False, name="test-disabled") as obs:
        assert isinstance(obs, DummyObservation)
        # Should be safe to call update()
        obs.update(output="ignored")


def test_conditional_observation_enabled_with_config():
    """When enabled=True with langfuse_config, creates client from config."""

    class DummyCtx:
        def __init__(self):
            self.entered = False
            self.updated = {}

        def __enter__(self):
            self.entered = True
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def update(self, **kwargs):
            self.updated.update(kwargs)

    dummy_ctx = DummyCtx()
    mock_client = MagicMock()
    mock_client.start_as_current_observation.return_value = dummy_ctx

    config = {"secret_key": "sk-test", "public_key": "pk-test", "host": "http://localhost:3000"}

    with patch("src.api.utils.tracing.get_langfuse_client", return_value=mock_client):
        with conditional_observation(
            enabled=True, langfuse_config=config, name="test-enabled", input="hello"
        ) as obs:
            assert obs is dummy_ctx
            obs.update(output="world")

        mock_client.start_as_current_observation.assert_called_once()
        assert dummy_ctx.entered is True
        assert dummy_ctx.updated.get("output") == "world"


def test_conditional_observation_enabled_env_fallback():
    """When enabled=True without config, falls back to env-based client."""

    class DummyCtx:
        def __init__(self):
            self.entered = False

        def __enter__(self):
            self.entered = True
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def update(self, **kwargs):
            pass

    dummy_ctx = DummyCtx()
    mock_client = MagicMock()
    mock_client.start_as_current_observation.return_value = dummy_ctx

    with patch("langfuse.get_client", return_value=mock_client):
        with conditional_observation(enabled=True, name="test-env") as obs:
            assert obs is dummy_ctx

        mock_client.start_as_current_observation.assert_called_once()

def test_conditional_observation_enabled_error_yields_dummy():
    """When Langfuse client creation fails, gracefully returns DummyObservation."""
    config = {"secret_key": "bad", "public_key": "bad", "host": "bad"}

    with patch("src.api.utils.tracing.get_langfuse_client", side_effect=Exception("connection error")):
        with conditional_observation(
            enabled=True, langfuse_config=config, name="test-error"
        ) as obs:
            assert isinstance(obs, DummyObservation)

def test_dummy_observation_context_manager_noop():
    """DummyObservation acts as a no-op context manager."""
    dummy = DummyObservation()
    with dummy as obs:
        assert obs is dummy