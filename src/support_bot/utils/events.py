from typing import Callable, Any
from queue import Queue
from crewai.utilities.events import crewai_event_bus, LLMStreamChunkEvent

CALLBACKS_AVAILABLE = False

token_queue = Queue()

def stream_token_handler(sender: Any, event: LLMStreamChunkEvent):
    token = event.chunk
    token_queue.put(token)
    # print(f"Received token: {token}")

crewai_event_bus.register_handler(LLMStreamChunkEvent, stream_token_handler)

try:
    from crewai.callbacks import BaseCallbackHandler  # type: ignore
    CALLBACKS_AVAILABLE = True

    class CrewAICallbackHandler(BaseCallbackHandler):  # type: ignore
        """Bridges CrewAI task/agent events to an emitter callable."""

        def __init__(self, emitter: Callable[[str, Any], None], total_tasks: int = 0, total_agents: int = 0):
            self._emit = emitter
            self.total_tasks = total_tasks
            self.total_agents = total_agents
            self.task_index = 0
            self.agent_index = 0
            self._tasks: list[dict[str, Any]] = []
            self._open_task_ids: set[str] = set()

        def _emit_tree(self):
            try:
                if not self._tasks:
                    return
                lines: list[str] = []
                last_task_idx = len(self._tasks) - 1
                for i, t in enumerate(self._tasks):
                    is_last_task = i == last_task_idx
                    branch = "└──" if is_last_task else "├──"
                    status_icon = "Completed" if t.get("status") == "done" else "In progress"
                    task_header = f"{branch} Task: {t.get('id')}" if t.get('id') else f"{branch} Task {i+1}"
                    lines.append(task_header)
                    indent_prefix = "    " if is_last_task else "│   "
                    lines.append(f"{indent_prefix}Assigned to: {t.get('agent') or '—'}")
                    lines.append(f"{indent_prefix}Status: {status_icon}")
                    tool_logs = t.get("tools") or []
                    for j, tool_line in enumerate(tool_logs):
                        is_last_tool = j == len(tool_logs) - 1
                        inner_branch = "└──" if is_last_tool else "├──"
                        lines.append(f"{indent_prefix}{inner_branch} {tool_line}")
                label = "\n".join(lines)
                self._emit("status", {"phase": "progress:tree", "label": label})
            except Exception:
                pass

        # Helper label builders
        def _task_label(self, task: Any) -> str:
            desc = getattr(task, "description", str(task)) or "Task"
            first = desc.strip().splitlines()[0]
            lowered = first.lower()
            if "determine the minimal workflow" in lowered or "minimal workflow" in lowered:
                return "Planning support workflow"
            if "research" in lowered or "historical incidents" in lowered:
                return "Searching incident history"
            if "synthesize" in lowered or "action plan" in lowered:
                return "Creating solution strategy"
            if "produce the final answer" in lowered or "final answer" in lowered or "user query response" in lowered:
                return "Preparing final response"
            if "json summary" in lowered:
                return "Summarizing conversation"
            if "summary title" in lowered:
                return "Generating chat title"
            return first[:70]

        def _agent_label(self, agent: Any) -> str:
            role = getattr(agent, "role", str(agent)) or "Agent"
            mapping = {
                "SupportCoordinator": "Workflow Coordinator",
                "HistoryResearcher": "Incident Researcher",
                "SolutionSynthesizer": "Solution Architect",
                "Responder": "Response Specialist",
                "Conversation Summarizer": "Summary Specialist",
                "Summary Title Generator": "Title Specialist",
            }
            return mapping.get(role, role)

        def _get_tool_friendly_name(self, tool_name: str) -> str:
            """Get user-friendly tool name"""
            name_lower = tool_name.lower()
            if "qdrant" in name_lower:
                return "Incident Database Search"
            elif "analysis" in name_lower:
                return "Pattern Analysis"
            else:
                return tool_name

        def on_task_start(self, task: Any, **kwargs):  # type: ignore
            try:
                self.task_index += 1
                desc = getattr(task, "description", str(task)) or "Task"
                first = desc.strip().splitlines()[0][:60]
                task_id = getattr(task, "id", None) or f"{self.task_index}" 
                agent = getattr(getattr(task, "agent", None), "role", None) or getattr(task, "agent", None)
                entry = {
                    "id": task_id,
                    "title": first,
                    "agent": agent,
                    "status": "in_progress",
                    "tools": []
                }
                self._tasks.append(entry)
                self._open_task_ids.add(task_id)
                self._emit_tree()

                agent_name = self._agent_label(getattr(task, "agent", None))
                task_name = self._task_label(task)
                self._emit("status", {
                    "phase": "agent:assigned",
                    "agent": agent_name,
                    "task": task_name,
                    "label": f"{agent_name} assigned to: {task_name}"
                })

                self._emit("status", {
                    "phase": "task:started",
                    "task_id": task_id,
                    "task_name": task_name,
                    "agent": agent_name,
                    "label": f"Task started: {task_name}"
                })

            except Exception:
                pass

        def on_task_end(self, task: Any = None, result: Any = None, **kwargs):  # type: ignore
            try:
                task_id = getattr(task, "id", None)
                if task_id is None:
                    for t in reversed(self._tasks):
                        if t.get("status") != "done":
                            task_id = t.get("id")
                            break
                for t in self._tasks:
                    if t.get("id") == task_id:
                        t["status"] = "done"
                        break
                if task_id in self._open_task_ids:
                    self._open_task_ids.remove(task_id)
                self._emit_tree()

                task_name = self._task_label(task)
                self._emit("task:completed", {
                    "task_id": task_id,
                    "task_name": task_name,
                    "result": str(result)[:200] if result else "",
                    "label": f"Task completed: {task_name}"
                })

                self._emit("task:evaluation", {
                    "task_id": task_id,
                    "task_name": task_name,
                    "label": f"Task evaluated: {task_name}"
                })

            except Exception:
                pass

        def on_agent_start(self, agent: Any, task: Any, **kwargs):  # type: ignore
            try:
                agent_name = self._agent_label(agent)
                task_name = self._task_label(task)
                self._emit("status", {
                    "phase": "agent:started",
                    "agent": agent_name,
                    "task": task_name,
                    "label": f"Agent started: {agent_name} executing {task_name}"
                })
            except Exception:
                pass

        def on_agent_end(self, agent: Any, task: Any, **kwargs):  # type: ignore
            try:
                agent_name = self._agent_label(agent)
                task_name = self._task_label(task)
                self._emit("status", {
                    "phase": "agent:completed",
                    "agent": agent_name,
                    "task": task_name,
                    "label": f"Agent completed: {agent_name} finished {task_name}"
                })
            except Exception:
                pass

        def on_tool_start(self, tool: Any, input_str: str = "", **kwargs):  # type: ignore
            try:
                name = getattr(tool, "name", tool.__class__.__name__)
                for t in reversed(self._tasks):
                    if t.get("status") != "done":
                        t.setdefault("tools", []).append(f"Using {name}")
                        break
                self._emit_tree()

                tool_label = self._get_tool_friendly_name(name)
                self._emit("tool:start", {
                    "tool": name,
                    "input": input_str[:200],
                    "label": f"Starting {tool_label}..."
                })
            except Exception:
                pass

        def on_tool_end(self, tool: Any, output: str = "", **kwargs):  # type: ignore
            try:
                name = getattr(tool, "name", tool.__class__.__name__)
                for t in reversed(self._tasks):
                    tools_list = t.get("tools") or []
                    for i in range(len(tools_list) - 1, -1, -1):
                        if tools_list[i] == f"Using {name}":
                            tools_list[i] = f"Used {name}"
                            break
                    break
                self._emit_tree()

                tool_label = self._get_tool_friendly_name(name)
                self._emit("tool:end", {
                    "tool": name,
                    "label": f"{tool_label} completed"
                })
            except Exception:
                pass

        def on_error(self, error: Exception, **kwargs):  # type: ignore
            try:
                self._emit("status", {
                    "phase": "agent:error",
                    "error": str(error),
                    "label": f"Agent error: {str(error)[:100]}"
                })
            except Exception:
                pass

except Exception:
    CALLBACKS_AVAILABLE = False


def try_kickoff_with_callbacks(crew: Any, inputs: dict, emitter: Callable[[str, Any], None]) -> Any:
    """Kickoff with callbacks if possible; otherwise emit a manual fallback so UI still shows progress."""
    tasks = []
    agents = []
    try:
        tasks = getattr(crew, "tasks", []) or []  # type: ignore
    except Exception:
        tasks = []
    try:
        agents = getattr(crew, "agents", []) or []  # type: ignore
    except Exception:
        agents = []

    if CALLBACKS_AVAILABLE:
        try:
            handler = CrewAICallbackHandler(emitter, total_tasks=len(tasks), total_agents=len(agents))  # type: ignore
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
            pass

    try:
        emitter("status", {"phase": "crew:start", "label": "Initializing support team..."})
        for idx, task in enumerate(tasks, start=1):
            desc = getattr(task, "description", str(task))
            short = (desc or "Step").strip().splitlines()[0][:70]
            lowered = short.lower()
            if "plan" in lowered or "workflow" in lowered:
                short = "Planning optimal support workflow"
                agent_name = "Workflow Coordinator"
            elif "research" in lowered or "search" in lowered:
                short = "Searching incident history database"
                agent_name = "Incident Researcher"
            elif "synth" in lowered or "solution" in lowered:
                short = "Creating comprehensive solution strategy"
                agent_name = "Solution Architect"
            elif "final" in lowered or "answer" in lowered or "response" in lowered:
                short = "Preparing detailed response"
                agent_name = "Response Specialist"
            else:
                agent_name = "Support Specialist"

            emitter("status", {
                "phase": "agent:assigned",
                "agent": agent_name,
                "task": short,
                "label": f"{agent_name} assigned to: {short}"
            })

            emitter("status", {
                "phase": "task:started",
                "task_name": short,
                "agent": agent_name,
                "label": f"Task started: {short}"
            })

            emitter("status", {
                "phase": "agent:started",
                "agent": agent_name,
                "task": short,
                "label": f"Agent started: {agent_name} executing {short}"
            })
    except Exception:
        pass

    try:
        result = crew.kickoff(inputs=inputs)
    except Exception as e:
        try:
            emitter("status", {"phase": "agent:error", "error": str(e), "label": f"Agent error: {str(e)[:100]}"})
        except Exception:
            pass
        raise

    try:
        emitter("status", {"phase": "crew:end", "label": "Support analysis complete"})
    except Exception:
        pass

    try:
        for idx, task in enumerate(tasks, start=1):
            desc = getattr(task, "description", str(task))
            short = (desc or "Step").strip().splitlines()[0][:70]
            lowered = short.lower()
            if "plan" in lowered or "workflow" in lowered:
                short = "Planning optimal support workflow"
                agent_name = "Workflow Coordinator"
            elif "research" in lowered or "search" in lowered:
                short = "Searching incident history database"
                agent_name = "Incident Researcher"
            elif "synth" in lowered or "solution" in lowered:
                short = "Creating comprehensive solution strategy"
                agent_name = "Solution Architect"
            elif "final" in lowered or "answer" in lowered or "response" in lowered:
                short = "Preparing detailed response"
                agent_name = "Response Specialist"
            else:
                agent_name = "Support Specialist"

            emitter("status", {
                "phase": "task:completed",
                "task_name": short,
                "agent": agent_name,
                "label": f"Task completed: {short}"
            })

            emitter("status", {
                "phase": "agent:completed",
                "agent": agent_name,
                "task": short,
                "label": f"Agent completed: {agent_name} finished {short}"
            })

            emitter("status", {
                "phase": "task:evaluation",
                "task_name": short,
                "label": f"Task evaluated: {short}"
            })
    except Exception:
        pass

    return result
