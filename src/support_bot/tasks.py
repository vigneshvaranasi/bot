from crewai import Task
from .agents import (
    support_coordinator_agent,
    researcher_agent,
    synthesizer_agent,
    user_query_responder_agent,
    json_summary_agent,
    summary_title_agent,
)

"""
Workflow contract
- Inputs: {user_prompt}, {context}
- Manager output (route_plan): JSON with keys: route in [context_only, info_only, solution_plan], search_query, rationale
- Research output: raw_results (top incidents, details)
- Synthesis output (optional): action_plan (steps, mitigations, monitoring)
- Responder output: final markdown answer as per formatting rules
"""

# Task 0: Manager planning
manager_plan_task = Task(
    description=(
        """Analyze the user query and context to determine the optimal workflow route.

Evaluate if context:{context} can answer prompt:{user_prompt} directly. Detect user intent: information-seeking vs solution-seeking.
Choose route: context_only (sufficient context) | info_only (need research) | solution_plan (need research + action plan).

Output JSON with: route, detected_intent, rationale.

User prompt: {user_prompt}
Context: {context}
"""
    ),
    expected_output=(
        """JSON: {\"route\": \"context_only|info_only|solution_plan\", \"detected_intent\": \"information|solution\", \"rationale\": \"...\"}"""
    ),
    agent=support_coordinator_agent,
)

# Task 1: Research - Generate search query and retrieve incidents
research_task = Task(
    description=(
        """Generate an optimal search query for the incident database and retrieve relevant incidents.

Based on coordinator's routing decision:
- If route=context_only → Output: 'SKIP_RESEARCH'
- Otherwise → Analyze {user_prompt} to create targeted search query focusing on:
  * Error codes (HTTP 499, 500, timeout, etc.)
  * Service names (PayU, specific APIs)
  * Symptoms (connection issues, slow response)
  
Then use Qdrant tool to search and return raw incident data.

User prompt: {user_prompt}
"""
    ),
    expected_output=(
        """Raw incident data (IDs, titles, details, scores) up to 5 results, or 'SKIP_RESEARCH'"""
    ),
    agent=researcher_agent,
    context=[manager_plan_task],
)

# Task 2: Synthesis - Create Solution Statergy
synthesis_task = Task(
    description=(
        """Transform research results into actionable resolution plans.

Check coordinator's route: if route != solution_plan → Output: 'SKIP_SYNTHESIS'
Otherwise, create structured action plan with: Immediate Steps, Root Cause Mitigation, Monitoring, Escalation Path.
"""
    ),
    expected_output=(
        """Structured Action Plan with clear sections, or 'SKIP_SYNTHESIS'"""
    ),
    agent=synthesizer_agent,
    context=[manager_plan_task, research_task],
)

# Task 3: User Response - Format based on routing and data
user_query_response_task = Task(
    description=(
        """Answer the user's query directly and professionally, focusing solely on the technical content.
        
    IMPORTANT: Never introduce yourself or explain your role/capabilities. Jump straight into answering the question.
    
    Based on coordinator's detected_intent, either:
    - For information queries: Directly explain the technical details, root causes, or incident information
    - For solution queries: Start with the concrete steps, actions, or guidance needed
    
    Keep responses concise and professional. Use technical language appropriately.
    Format in clean Markdown without triple backticks.
    
    User prompt: {user_prompt}
    """
    ),
    expected_output=(
        """Clean, conversational Markdown response matching detected intent, using available research/synthesis data appropriately and never referencing context or sources."""
    ),
    agent=user_query_responder_agent,
    context=[manager_plan_task, research_task, synthesis_task],
)

# Task 5: JSON Summary Generation
json_summary_task = Task(
    description=(
        """Process a JSON thread of conversations between a user and a chatbot. Extract the key context and generate a concise summary that is optimized for token usage.
        The summary should:
        - Capture the main intent of the user.
        - Highlight key responses from the chatbot.
        - Provide a clear and economical context for further processing.
        
        Input: {conversation_json}
        """
    ),
    expected_output=(
        """A concise text summary of the conversation thread, capturing:
        - User's main intent.
        - Key chatbot responses.
        - Overall context in an economical format."""
    ),
    agent=json_summary_agent,
)

# Task 6: Summary Title Generation
summary_title_generation_task = Task(
    description=(
        """Generate a concise and informative title for a user prompt.
        The title should capture the essence of the user prompt while being concise and informative.

        Input: {user_prompt}
        Output: Just Title, nothing else and unformatted.
        """
    ),
    expected_output=("""A concise and informative title for the user prompt."""),
    agent=summary_title_agent,
)
