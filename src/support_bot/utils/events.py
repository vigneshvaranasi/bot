from typing import Callable, Optional, Any

CALLBACKS_AVAILABLE = False

try:
    from crewai.callbacks import BaseCallbackHandler  # type: ignore

    CALLBACKS_AVAILABLE = True

    class CrewAICallbackHandler(BaseCallbackHandler):  # type: ignore
        """Bridges CrewAI task/agent events to an emitter callable."""

        def __init__(self, emitter: Callable[[str, Any], None]):
            self._emit = emitter

        def on_task_start(self, task: Any, **kwargs):  # type: ignore
            try:
                self._emit("status", {"phase": "task:start", "task": getattr(task, "description", str(task))[:120]})
            except Exception:
                pass

        def on_task_end(self, task: Any, result: Any, **kwargs):  # type: ignore
            try:
                self._emit("status", {"phase": "task:end", "task": getattr(task, "description", str(task))[:120]})
            except Exception:
                pass

        def on_agent_start(self, agent: Any, **kwargs):  # type: ignore
            try:
                self._emit("status", {"phase": "agent:start", "agent": getattr(agent, "role", str(agent))})
            except Exception:
                pass

        def on_agent_end(self, agent: Any, result: Any, **kwargs):  # type: ignore
            try:
                self._emit("status", {"phase": "agent:end", "agent": getattr(agent, "role", str(agent))})
            except Exception:
                pass

        def on_tool_start(self, tool: Any, input_str: str = "", **kwargs):  # type: ignore
            try:
                name = getattr(tool, "name", tool.__class__.__name__)
                self._emit("tool:start", {"tool": name, "input": input_str[:200]})
            except Exception:
                pass

        def on_tool_end(self, tool: Any, output: str = "", **kwargs):  # type: ignore
            try:
                name = getattr(tool, "name", tool.__class__.__name__)
                self._emit("tool:end", {"tool": name})
            except Exception:
                pass

        def on_error(self, error: Exception, **kwargs):  # type: ignore
            try:
                self._emit("error", str(error))
            except Exception:
                pass

except Exception:
    CALLBACKS_AVAILABLE = False


def try_kickoff_with_callbacks(crew: Any, inputs: dict, emitter: Callable[[str, Any], None]) -> Any:
    """Attempt to kickoff a Crew with callbacks; if unsupported, fallback to normal kickoff."""
    if CALLBACKS_AVAILABLE:
        try:
            handler = CrewAICallbackHandler(emitter)  # type: ignore
            try:
                return crew.kickoff(inputs=inputs, callbacks=[handler])  # type: ignore[arg-type]
            except TypeError:
                if hasattr(crew, "callbacks"):
                    try:
                        current = getattr(crew, "callbacks") or []
                        setattr(crew, "callbacks", [*current, handler])
                    except Exception:
                        pass
                return crew.kickoff(inputs=inputs)
        except Exception:
            return crew.kickoff(inputs=inputs)
    return crew.kickoff(inputs=inputs)
