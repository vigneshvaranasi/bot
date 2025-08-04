from crewai.tools import BaseTool
from typing import List, Dict, Any
import re

class IncidentAnalysisTool(BaseTool):
    name: str = "Incident Analysis Tool"
    description: str = (
        "Analyzes incident data to extract patterns, common root causes, "
        "and successful resolution strategies. Useful for identifying "
        "trends and building comprehensive solution strategies.")

    def _run(self, incident_data: str) -> str:
        """
        Analyze incident data to extract key insights
        """
        print(f"--- Analyzing incident data patterns ---")
        
        try:
            # Extract incident IDs
            incident_ids = re.findall(r'PAYU-INC-\d{4}-\d{2}-\d{2}-\d+', incident_data)
            
            # Extract HTTP codes
            http_codes = re.findall(r'HTTP (\d{3})', incident_data)
            
            # Extract root causes
            root_causes = re.findall(r'rootCause: ([^.]+\.)', incident_data)
            
            # Extract mitigation strategies
            mitigations = re.findall(r'mitigation: ([^.]+\.)', incident_data)
            
            # Extract timelines
            timelines = re.findall(r'timeline: ([^.]+\.)', incident_data)
            
            # Build analysis report
            analysis = f"""
INCIDENT PATTERN ANALYSIS
========================

INCIDENTS FOUND: {len(incident_ids)}
Incident IDs: {', '.join(incident_ids)}

HTTP ERROR CODES: {list(set(http_codes))}
Most common codes: {self._get_most_common(http_codes)}

ROOT CAUSE PATTERNS:
{self._format_list(root_causes)}

SUCCESSFUL MITIGATION STRATEGIES:
{self._format_list(mitigations)}

TYPICAL RESOLUTION TIMELINE PATTERNS:
{self._format_list(timelines[:3])}  # Show first 3 timelines

RECOMMENDATIONS BASED ON PATTERNS:
- Monitor for recurring HTTP {self._get_most_common(http_codes)[0] if http_codes else 'error'} patterns
- Implement proactive timeout monitoring
- Establish client communication protocols for configuration changes
- Create automated detection for similar incident patterns
"""
            
            return analysis
            
        except Exception as e:
            return f"Error analyzing incident data: {str(e)}"
    
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
