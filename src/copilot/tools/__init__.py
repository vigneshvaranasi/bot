"""Incident knowledge base tools for the copilot agent.

This module exports specialized tools for different types of incident queries.
"""

from src.copilot.tools.incident_tools import (
    get_incidents_by_application,
    get_recent_incidents,
    get_incident_statistics,
    get_recurring_incidents,
    lookup_incident_by_id,
    search_similar_incidents,
)

# List of all available tools for the agent
available_tools = [
    lookup_incident_by_id,
    search_similar_incidents,
    get_incidents_by_application,
    get_recent_incidents,
    get_incident_statistics,
    get_recurring_incidents,
]

__all__ = [
    "lookup_incident_by_id",
    "search_similar_incidents",
    "get_incidents_by_application",
    "get_recent_incidents",
    "get_incident_statistics",
    "get_recurring_incidents",
    "available_tools",
]
