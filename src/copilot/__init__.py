"""Copilot AI Agent module for incident resolution.

This module provides an AI-powered incident resolution assistant that
searches a knowledge base of past incidents and provides relevant
information to help resolve current issues.

Main components:
- graph: LangGraph-based agent workflow
- tools: Vector search tools for knowledge base access
- guardrails: Prompt validation and security filtering
- config: Configuration and environment variable management

Usage:
    from src.copilot.graph import create_agent_graph

    app = create_agent_graph()
    result = app.invoke({"messages": [("user", "How do I fix error X?")]})
"""

from src.copilot.graph import create_agent_graph
from src.copilot.guardrails.prompt_guardrails import PromptGuardrail

__all__ = ["create_agent_graph", "PromptGuardrail"]
