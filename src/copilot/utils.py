"""
Utility functions for the copilot module.
"""
import re
from typing import Tuple

# Context-dependent keywords
CONTEXT_KEYWORDS = {
    "it", "that", "this", "these", "those", "them", "they",
    "above", "below", "previous", "earlier", "before", "mentioned",
    "continue", "more", "also", "additionally",
    "same", "similar", "such", "said",
}


def is_context_dependent_query(query: str) -> Tuple[bool, str]:
    """
    Check if a query appears to depend on conversation context.
    
    Args:
        query (str): The user query to analyze
        
    Returns:
        Tuple[bool, str]: (is_dependent, reason)
    """
    if not query:
        return False, ""
    
    query_lower = query.lower().strip()
    words = query_lower.split()
    # If query contains an explicit incident ID
    incident_id_pattern = r'\bINC-\d{4}-\d{2}-\d{2}-\d+\b'
    if re.search(incident_id_pattern, query, re.IGNORECASE):
        return False, ""
    
    # Very short queries are often context-dependent
    if len(words) <= 2:
        continuation_words = {"continue", "more", "elaborate", "explain", "why", "how"}
        if any(word in continuation_words for word in words):
            return True, f"Query appears to be a continuation: '{query}'"
    
    # Check for context keywords
    for keyword in CONTEXT_KEYWORDS:
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, query_lower):
            return True, f"Query contains context-dependent reference: '{keyword}'"
    
    # Check for vague imperatives
    imperative_pattern = r'^(generate|create|write|give|show|tell|explain)\s+(the|a|an)\s+\w+\s*$'
    if re.search(imperative_pattern, query_lower):
        return True, "Query has vague reference (e.g., 'generate the incident')"
    
    return False, ""


def should_ask_clarification(query: str, has_history: bool) -> Tuple[bool, str]:
    """
    Determine if the bot should ask for clarification before processing.
    
    Args:
        query (str): The user query
        has_history (bool): Whether there's conversation history
        
    Returns:
        Tuple[bool, str]: (should_ask, clarification_message)
    """
    is_dependent, reason = is_context_dependent_query(query)
    
    # If query is context-dependent but there's no history, ask for clarification
    if is_dependent and not has_history:
        clarification = (
            "Your query seems to reference something from a previous conversation. "
            "Could you please provide more context or rephrase your question to be more specific? "
            f"For example, instead of '{query}', you could specify what you're referring to."
        )
        return True, clarification
    
    return False, ""
