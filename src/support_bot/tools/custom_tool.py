from crewai.tools import BaseTool
import json
import os
from typing import List, Dict, Any

# Tool for fetching customer support incident data
class CustomerSupportDataTool(BaseTool):
    name: str = "Customer Support Data Fetcher"
    description: str = (
        "Fetches past incident data from incidents.json file. "
        "Search for incidents by providing keywords like HTTP codes (499, 400, 429), "
        "issue types (latency, outage, carding), or any text that might appear in incidents. "
        "Returns detailed incident information including root cause and mitigation steps.")

    def _run(self, argument: str) -> str:
        print(f"--- Fetching incident data for query: {argument} ---")
        
        # Get the path to incidents.json relative to this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        incidents_path = os.path.join(current_dir, "..", "..", "..", "data", "incidents.json")
        
        try:
            # Load incidents data
            with open(incidents_path, 'r', encoding='utf-8') as file:
                incidents_data = json.load(file)
            
            # Search for matching incidents
            matching_incidents = self._search_incidents(incidents_data, argument)
            
            if not matching_incidents:
                return f"No incidents found matching query: '{argument}'"
            
            # Format the results
            result = f"Found {len(matching_incidents)} incident(s) matching '{argument}':\n\n"
            
            for i, incident in enumerate(matching_incidents, 1):
                result += f"=== INCIDENT {i} ===\n"
                result += f"ID: {incident['Incident ID']}\n"
                result += f"Main Issue: {incident['Main Issue']}\n"
                result += f"Details:\n{incident['text']}\n"
                result += "=" * 50 + "\n\n"
            
            return result
            
        except FileNotFoundError:
            return f"Error: incidents.json file not found at {incidents_path}"
        except json.JSONDecodeError:
            return "Error: Could not parse incidents.json file"
        except Exception as e:
            return f"Error fetching incident data: {str(e)}"
    
    def _search_incidents(self, incidents: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """Search incidents based on the query string"""
        query_lower = query.lower()
        matching_incidents = []
        
        for incident in incidents:
            # Search in all text fields
            search_text = f"{incident.get('Incident ID', '')} {incident.get('Main Issue', '')} {incident.get('text', '')}"
            search_text_lower = search_text.lower()
            
            # Check if query matches any part of the incident
            if query_lower in search_text_lower:
                matching_incidents.append(incident)
        
        return matching_incidents