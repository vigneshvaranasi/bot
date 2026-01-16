from contextlib import contextmanager
from langfuse import get_client

langfuse = get_client()

class DummyObservation:
    def update(self, **kwargs):
        pass
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

@contextmanager
def conditional_observation(enabled: bool, **kwargs):
    if enabled:
        # langfuse.start_as_current_observation returns a context manager
        ctx = langfuse.start_as_current_observation(**kwargs)
        with ctx as obs:
            yield obs
    else:
        yield DummyObservation()
