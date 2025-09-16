import asyncio
import os
import time
from typing import Any, Callable, Dict

from .crew import create_support_crew
from .utils.events import try_kickoff_with_callbacks
from .tools.qdrant_tool import QdrantIncidentDataTool
from .agents import qdrant_data_tool as AGENT_QDRANT_TOOL, configure_agents_llm
from .utils.models import get_gemini_api_key

async def run_support_with_emitter(inputs: Dict[str, Any], emitter: Callable[[str, Any], None], model: str = "gemma3:4b", temperature: float = 0.7) -> str:
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

        _ = QdrantIncidentDataTool(emitter=emitter)
    except Exception:
        pass

    def _emit(event: str, data: Any):
        try:
            emitter(event, data)
        except Exception:
            pass

    _emit("status", {"phase": "crew:start"})
    
    
    # Configure agents with the provided LLM settings
    configure_agents_llm(model, temperature)

    # Create crew with configured agents
    support_crew = create_support_crew()

    def kickoff():
        return try_kickoff_with_callbacks(support_crew, inputs, _emit)

    result = await asyncio.to_thread(kickoff)

    if hasattr(result, 'content'):
        answer = result.content
    else:
        answer = str(result)
    
    # Stream line-by-line
    lines = answer.splitlines(True)
    for line in lines:
        _emit("answer_stream", {"text": line})
        await asyncio.sleep(0.1)
    
    _emit("status", {"phase": "crew:end"})
    return answer


# runner with fallbacks
async def run_support_with_emitter_with_fallback(inputs: Dict[str, Any], emitter: Callable[[str, Any], None], model: str = "gemma3:4b", temperature: float = 0.7) -> str:
    """
    Run the support crew while emitting live events via `emitter`.
    Implements failover and retry logic for Gemini and Gemma models.
    """

    try:
        try:
            setattr(AGENT_QDRANT_TOOL, "_emit", emitter)
        except Exception:
            pass

        _ = QdrantIncidentDataTool(emitter=emitter)
    except Exception:
        pass

    def _emit(event: str, data: Any):
        try:
            emitter(event, data)
        except Exception:
            pass

    _emit("status", {"phase": "crew:start"})
    
    result = None
    last_exception = None

    # fallbacks
    fallbacks = []
    if model.startswith("gemini"):
        # 3 Gemini keys, then fallback to gemma3:4b
        fallbacks.append((model, True, True))
        fallbacks.append(("gemini-2.0-flash-lite-001", True, True))
        fallbacks.append(("gemini-2.0-flash", True, True))
        fallbacks.append(("gemma3:4b", False, False))
    elif model.startswith("gemma"):
        # gemma3:4b, then fallback to Gemini Key
        fallbacks.append((model, False, False))
        fallbacks.append(("gemma3:4b", False, False))
        fallbacks.append(("gemini-2.0-flash-lite-001", True, True))
    else:
        fallbacks.append((model, model.startswith("gemini"), model.startswith("gemini")))

    for model_name, is_gemini, use_api_key_cycle in fallbacks:
        try:
            print('='*20)
            print(f"Trying model: {model_name}")
            print('='*20)
            
            if is_gemini and use_api_key_cycle:
                os.environ["GEMINI_API_KEY"] = get_gemini_api_key()
            configure_agents_llm(model_name, temperature)
            support_crew = create_support_crew()
            def kickoff():
                return try_kickoff_with_callbacks(support_crew, inputs, _emit)
            result = await asyncio.to_thread(kickoff)
            if result:
                print('='*20)
                print(f"Successfully processed {model_name}")
                print('='*20)
                break
            
        except Exception as e:
            print('='*20)
            print(f"Error occurred while processing {model_name}: {e}")
            print('='*20)
            last_exception = e
            time.sleep(1)
            continue

    if result is None:
        raise last_exception

    if hasattr(result, 'content'):
        answer = result.content
    else:
        answer = str(result)

    lines = answer.splitlines(True)
    for line in lines:
        _emit("answer_stream", {"text": line})
        await asyncio.sleep(0.1)
    
    _emit("status", {"phase": "crew:end"})
    return answer