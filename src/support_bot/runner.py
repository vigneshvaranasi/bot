import asyncio
from typing import Any, Callable, Dict

from .crew import support_crew
from .utils.events import try_kickoff_with_callbacks
from .tools.qdrant_tool import QdrantIncidentDataTool
from .tools.analysis_tool import IncidentAnalysisTool
from .agents import qdrant_data_tool as AGENT_QDRANT_TOOL, analysis_tool as AGENT_ANALYSIS_TOOL


async def run_support_with_emitter(inputs: Dict[str, Any], emitter: Callable[[str, Any], None]) -> str:
    """
    Run the support crew while emitting live events via `emitter`.
    Tries CrewAI callbacks first; always emits coarse phase events.
    Also injects emitter into tools for truthful tool-level events.
    """

    try:
        try:
            setattr(AGENT_QDRANT_TOOL, "_emit", emitter)
        except Exception:
            pass
        try:
            setattr(AGENT_ANALYSIS_TOOL, "_emit", emitter)
        except Exception:
            pass

        _ = QdrantIncidentDataTool(emitter=emitter)
        _ = IncidentAnalysisTool(emitter=emitter)
    except Exception:
        pass

    def _emit(event: str, data: Any):
        try:
            emitter(event, data)
        except Exception:
            pass

    _emit("status", {"phase": "crew:start"})

    def kickoff():
        return try_kickoff_with_callbacks(support_crew, inputs, _emit)

    result = await asyncio.to_thread(kickoff)

    _emit("status", {"phase": "crew:end"})
    return str(result)
