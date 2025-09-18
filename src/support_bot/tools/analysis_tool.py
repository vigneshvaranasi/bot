from crewai.tools import BaseTool
from typing import List, Dict, Any
import re

class IncidentAnalysisTool(BaseTool):
    name: str = "Incident Analysis Tool"
    description: str = (
        "Analyzes incident data to extract patterns, common root causes, "
        "and successful resolution strategies. Useful for identifying "
        "trends and building comprehensive solution strategies.")

    def __init__(self, emitter=None):
        super().__init__()
        self._emit = emitter

    def _run(self, incident_data: str) -> str:
        """
        Analyze incident data to extract key insights.
        Supports cancellation via _cancelled attribute.
        """
        # Check for cancellation before starting
        if hasattr(self, '_cancelled') and callable(self._cancelled) and self._cancelled():
            return "Analysis cancelled by user"
        
        if self._emit:
            try:
                # Check for cancellation before emitting
                if hasattr(self, '_cancelled') and callable(self._cancelled) and self._cancelled():
                    return "Analysis cancelled by user"
                self._emit("tool:start", {"tool": "analysis"})
            except Exception:
                pass
        else:
            print(f"--- Analyzing incident data patterns ---")
        
        # Check for cancellation before analysis
        if hasattr(self, '_cancelled') and callable(self._cancelled) and self._cancelled():
            return "Analysis cancelled by user"
        
        try:
            # Extract incident IDs
            incident_ids = re.findall(r'PAYU-INC-\d{4}-\d{2}-\d{2}-\d+', incident_data)
            
            # Extract root causes
            root_causes = re.findall(r'rootCause: ([^.]+\.)', incident_data)
            
            # Extract mitigation strategies
            mitigations = re.findall(r'mitigation: ([^.]+\.)', incident_data)
            
            # Extract timelines
            timelines = re.findall(r'timeline: ([^.]+\.)', incident_data)
            
            # Check for cancellation before building report
            if hasattr(self, '_cancelled') and callable(self._cancelled) and self._cancelled():
                return "Analysis cancelled by user"
            
            # Build analysis report
            analysis = f"""
INCIDENT PATTERN ANALYSIS
========================

INCIDENTS FOUND: {len(incident_ids)}

ROOT CAUSE PATTERNS:
{self._format_list(root_causes)}

SUCCESSFUL MITIGATION STRATEGIES:
{self._format_list(mitigations)}

TYPICAL RESOLUTION TIMELINE PATTERNS:
{self._format_list(timelines[:3])}  # Show first 3 timelines
"""
            
            result = analysis
            
            # Final cancellation check
            if hasattr(self, '_cancelled') and callable(self._cancelled) and self._cancelled():
                return "Analysis cancelled by user"
            
        except Exception as e:
            result = f"Error analyzing incident data: {str(e)}"
        finally:
            if self._emit:
                try:
                    self._emit("tool:end", {"tool": "analysis"})
                except Exception:
                    pass

        return result
    
    def _get_most_common(self, items: List[str]) -> List[str]:
        """Get most common items from a list"""
        if not items:
            return []
        from collections import Counter
        return [item for item, count in Counter(items).most_common(3)]
    
    def _format_list(self, items: List[str]) -> str:
        """Format list items for display"""
        if not items:
            return "- No patterns identified"
        
        formatted_items = []
        for i, item in enumerate(items[:5], 1):  # Show max 5 items
            formatted_items.append(f"- {item.strip()}")
        
        return '\n'.join(formatted_items)
