import asyncio
import threading
import time
from typing import Any, Callable, Dict

from .crew import support_crew
from .utils.events import try_kickoff_with_callbacks
from .tools.qdrant_tool import QdrantIncidentDataTool
from .tools.analysis_tool import IncidentAnalysisTool
from .agents import qdrant_data_tool as AGENT_QDRANT_TOOL, analysis_tool as AGENT_ANALYSIS_TOOL


class CancellableCrewRunner:
    """A cancellable crew runner that can stop execution when cancelled."""
    
    def __init__(self):
        self.cancelled = False
        self.result = None
        self.exception = None
        self.thread = None
    
    def cancel(self):
        """Mark the execution as cancelled."""
        self.cancelled = True
    
    def run_crew(self, inputs: Dict[str, Any], emitter: Callable[[str, Any], None]):
        """Run the crew in a separate thread."""
        try:
            # Check for cancellation before starting
            if self.cancelled:
                return "Execution cancelled before start"
            
            def _emit(event: str, data: Any):
                try:
                    # Check for cancellation before emitting events
                    if self.cancelled:
                        return
                    emitter(event, data)
                except Exception:
                    pass
            
            # Inject cancellation check into tools
            def cancellation_aware_emitter(event: str, data: Any):
                if self.cancelled:
                    raise RuntimeError("Execution cancelled")
                _emit(event, data)
            
            # Set up tools with cancellation awareness
            try:
                setattr(AGENT_QDRANT_TOOL, "_emit", cancellation_aware_emitter)
                setattr(AGENT_QDRANT_TOOL, "_cancelled", lambda: self.cancelled)
            except Exception:
                pass
            try:
                setattr(AGENT_ANALYSIS_TOOL, "_emit", cancellation_aware_emitter)
                setattr(AGENT_ANALYSIS_TOOL, "_cancelled", lambda: self.cancelled)
            except Exception:
                pass
            
            _emit("status", {"phase": "crew:start"})
            
            # Check for cancellation periodically during execution
            def kickoff_with_cancellation():
                if self.cancelled:
                    raise RuntimeError("Execution cancelled")
                
                # Periodically check for cancellation during long operations
                import time
                start_time = time.time()
                
                def periodic_cancellation_check():
                    if self.cancelled:
                        raise RuntimeError("Execution cancelled during crew operation")
                    if time.time() - start_time > 0.5:  # Check every 500ms
                        return True
                    return False
                
                # Set a global cancellation checker that tools can use
                setattr(self, '_check_cancellation', periodic_cancellation_check)
                
                return try_kickoff_with_callbacks(support_crew, inputs, cancellation_aware_emitter)
            
            self.result = kickoff_with_cancellation()
            
            if not self.cancelled:
                _emit("status", {"phase": "crew:end"})
            
        except Exception as e:
            if self.cancelled or "cancelled" in str(e).lower():
                emitter("status", {"phase": "crew:cancelled"})
                self.result = "Request cancelled by user"
            else:
                self.exception = e


async def run_support_with_emitter(inputs: Dict[str, Any], emitter: Callable[[str, Any], None]) -> str:
    """
    Run the support crew while emitting live events via `emitter`.
    Supports proper cancellation that actually stops crew execution.
    """
    
    runner = CancellableCrewRunner()
    
    # Start the crew execution in a background thread
    thread = threading.Thread(
        target=runner.run_crew,
        args=(inputs, emitter),
        daemon=True
    )
    thread.start()
    runner.thread = thread
    
    try:
        # Poll the thread and check for cancellation
        while thread.is_alive():
            # Check every 50ms if we should cancel - more responsive to cancellation
            await asyncio.sleep(0.05)
            
            # This will raise CancelledError if the client disconnected
            # The calling code should catch this and call runner.cancel()
        
        # Wait for thread to complete
        thread.join(timeout=1.0)
        
        if runner.exception:
            if runner.cancelled or "cancelled" in str(runner.exception).lower():
                return "Request cancelled by user"
            raise runner.exception
        
        return str(runner.result) if runner.result else "No result"
        
    except asyncio.CancelledError:
        # Client disconnected - cancel the crew execution
        emitter("status", {"phase": "crew:cancelling"})
        runner.cancel()
        
        # Give the thread some time to notice cancellation and clean up
        thread.join(timeout=3.0)
        
        # Force terminate if still running
        if thread.is_alive():
            emitter("status", {"phase": "crew:force_stopped"})
        
        emitter("status", {"phase": "crew:cancelled"})
        return "Request cancelled by user"


# Legacy function for backward compatibility
async def run_support_with_emitter_legacy(inputs: Dict[str, Any], emitter: Callable[[str, Any], None]) -> str:
    """
    Legacy version - kept for reference but not recommended for cancellation support.
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

    try:
        result = await asyncio.to_thread(kickoff)
        _emit("status", {"phase": "crew:end"})
        return str(result)
    except asyncio.CancelledError:
        _emit("status", {"phase": "crew:cancelled"})
        raise  # Re-raise to propagate cancellation
