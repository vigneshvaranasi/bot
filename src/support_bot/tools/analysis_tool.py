from crewai.tools import BaseTool
from typing import List, Dict, Any, Union
import re
import json
from pydantic import BaseModel, Field

class IncidentAnalysisTool(BaseTool):
    name: str = "Incident Analysis Tool"
    description: str = (
        "Analyzes incident data to extract patterns, common root causes, "
        "and successful resolution strategies. Useful for identifying "
        "trends and building comprehensive solution strategies.")
    
    class ArgsSchema(BaseModel):
        incident_data: Union[str, dict] = Field(
            ..., 
            description="The incident data to analyze. Can be a string or a dictionary containing incident information."
        )

    def __init__(self, emitter=None):
        super().__init__()
        self._emit = emitter
    
    def _normalize_input(self, incident_data: Union[str, dict]) -> str:
        """
        Normalize the input data to ensure we always work with strings
        """
        if isinstance(incident_data, str):
            return incident_data
        elif isinstance(incident_data, dict):
            if 'description' in incident_data:
                return str(incident_data['description'])
            # Try to convert the entire dict to a string if no description field
            return json.dumps(incident_data)
        # For any other type, convert to string
        return str(incident_data)

    def _run(self, incident_data: Union[str, dict]) -> str:
        """
        Analyze incident data to extract key insights
        """
        # Normalize input
        incident_data = self._normalize_input(incident_data)
        if self._emit:
            try:
                self._emit("tool:start", {
                    "tool": "analysis",
                    "label": "Analyzing incident data patterns and trends..."
                })
            except Exception:
                pass
        else:
            print(f"--- Analyzing incident data patterns ---")
        
        try:
            # Extract incident IDs
            incident_ids = re.findall(r'PAYU-INC-\d{4}-\d{2}-\d{2}-\d+', incident_data)
            
            # Extract root causes
            root_causes = re.findall(r'rootCause: ([^.]+\.)', incident_data)
            
            # Extract mitigation strategies
            mitigations = re.findall(r'mitigation: ([^.]+\.)', incident_data)
            
            # Extract timelines
            timelines = re.findall(r'timeline: ([^.]+\.)', incident_data)
            
            if self._emit:
                try:
                    self._emit("tool:results", {"tool": "analysis", "count": len(incident_ids)})
                except Exception:
                    pass
            
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
            
        except Exception as e:
            result = f"Error analyzing incident data: {str(e)}"
        finally:
            if self._emit:
                try:
                    pattern_count = len(root_causes) + len(mitigations) + len(timelines)
                    self._emit("tool:end", {
                        "tool": "analysis",
                        "count": len(incident_ids),
                        "label": f"Pattern analysis complete. Analyzed {len(incident_ids)} incident{'s' if len(incident_ids) != 1 else ''}."
                    })
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
