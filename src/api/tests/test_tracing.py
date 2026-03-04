"""Tests for tracing.conditional_observation helper."""

from unittest.mock import patch

from src.api.utils.tracing import conditional_observation, DummyObservation


def test_conditional_observation_disabled_uses_dummy():
    """When enabled=False, returns DummyObservation and does not call langfuse."""
    with patch("src.api.utils.tracing.langfuse") as mock_langfuse:
        with conditional_observation(enabled=False, name="test-disabled") as obs:
            assert isinstance(obs, DummyObservation)
            # Should be safe to call update()
            obs.update(output="ignored")

        mock_langfuse.start_as_current_observation.assert_not_called()


def test_conditional_observation_enabled_wraps_langfuse():
    """When enabled=True, delegates to langfuse.start_as_current_observation."""

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

    with patch("src.api.utils.tracing.langfuse") as mock_langfuse:
        mock_langfuse.start_as_current_observation.return_value = dummy_ctx

        with conditional_observation(
            enabled=True, name="test-enabled", input="hello"
        ) as obs:
            # Should be the same object returned by langfuse context manager
            assert obs is dummy_ctx
            obs.update(output="world")

        mock_langfuse.start_as_current_observation.assert_called_once()
        assert dummy_ctx.entered is True
        assert dummy_ctx.updated.get("output") == "world"


def test_dummy_observation_context_manager_noop():
    """DummyObservation acts as a no-op context manager."""
    dummy = DummyObservation()
    with dummy as obs:
        assert obs is dummy