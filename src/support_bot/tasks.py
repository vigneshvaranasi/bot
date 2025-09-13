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
    description="""
Description:
Analyze the user query and context to determine the optimal workflow route.
Evaluate if context:{context} can answer prompt:{user_prompt} directly. Detect user intent: information-seeking vs solution-seeking. Choose route: context_only (sufficient context) | info_only (need research) | solution_plan (need research + action plan).
Rules to Output:
- Output JSON with: route, detected_intent, rationale.
Chain of Thought:
- Consider if the context is sufficient for a direct answer
- Detect if the user wants information or a solution
- Choose the minimal workflow path
""",
    expected_output="""
JSON: {"route": "context_only|info_only|solution_plan", "detected_intent": "information|solution", "rationale": "..."}
""",
    agent=support_coordinator_agent,
)

# Task 1: Research - Generate search query and retrieve incidents
research_task = Task(
    description="""
Description:
Generate an optimal search query for the incident database and retrieve relevant incidents.
Chain of Thought Description:
- If route=context_only, return an empty array [] to indicate no research needed
- Otherwise, analyze {user_prompt} to create a targeted search query focusing on error codes, service names, and symptoms.
- Use Qdrant tool to search and return raw incident data.
Rules to Output:
- Output up to 5 results or empty array [] if no research needed
Output: [ {id:..., title:..., details:..., score:...}, ... ] or []
""",
    expected_output="""
Raw incident data (IDs, titles, details, scores) up to 5 results, or empty array []
""",
    agent=researcher_agent,
    context=[manager_plan_task],
)

# Task 2: Synthesis - Create Solution Strategy

synthesis_task = Task(
    description="""
Description:
Transform research results into actionable resolution plans for issues.

Rules to Output:
- If the route is 'context_only', do not synthesize or search for new information—answer strictly from the provided context.
- Do not introduce yourself or mention your role.
- Start with the most relevant technical steps or explanations.
- Use clean Markdown formatting (h1, h2, h3, numbered/bullet lists), but do not use triple backticks.
- For solution queries, begin with concrete actions and steps (Immediate Steps, Root Cause Mitigation, Monitoring, Escalation Path).
- Keep responses concise, direct, and professional.
- Never reference the context, sources, or your own capabilities.
- If escalation is needed, clearly state the escalation path.
- If monitoring is requested, provide only the monitoring steps and tools.

Chain of Thought:
- If research results are empty ([]), do not perform synthesis and return an empty object {}
- If research results exist, analyze the data to identify:
  - Common patterns in incidents
  - Successful mitigation strategies
  - Typical resolution steps
- Break down solutions into:
  - Immediate Steps
  - Root Cause Mitigation
  - Monitoring
  - Escalation Path
- For monitoring, list only the relevant metrics, tools, and alerting strategies
- For information, explain the error, common causes, and debugging steps
""",
    expected_output="""
Structured Action Plan with clear sections, or empty object {}
""",
    agent=synthesizer_agent,
    context=[manager_plan_task, research_task],
)

# Task 3: User Response - Format based on routing and data

user_query_response_task = Task(
    description="""
Description:
Answer the user's query directly and professionally, focusing solely on the technical content for {user_prompt}.

Rules to Output:
- If the route is 'context_only', answer strictly from the provided context—do not search, synthesize, or add new information.
- Never introduce yourself or explain your role/capabilities. Jump straight into answering the question.
- For information queries: Directly explain the technical details, root causes, or incident information.
- For solution queries: Start with the concrete steps, actions, or guidance needed.
- Keep responses concise and professional. Use technical language appropriately.
- Format in clean Markdown, using h1, h2, h3, numbered lists, bullet list without triple backticks.
- Never reference the context, sources, or your own capabilities.

Chain of Thought:
- If route is 'context_only', use only the provided context for the answer.
- Use detected_intent to decide response structure.
- For solutions, break down into Immediate Steps, Root Cause Mitigation, Monitoring, and Escalation Path.
- For monitoring, list only the relevant metrics, tools, and alerting strategies.
- For information, explain the error, common causes, and debugging steps.
""",
    expected_output="""
Clean, conversational Markdown response matching detected intent, using available research/synthesis data appropriately and never referencing context or sources.
""",
    agent=user_query_responder_agent,
    context=[manager_plan_task, research_task, synthesis_task],
)

# Task 5: JSON Summary Generation
json_summary_task = Task(
    description="""
Description:
Process a JSON thread of conversations between a user and a chatbot. Extract the key context and generate a concise summary that is optimized for token usage.
Rules to Output:
- Capture the main intent of the user.
- Highlight key responses from the chatbot.
- Provide a clear and economical context for further processing.
Chain of Thought:
- Summarize only the most relevant information

JSON Thread: {conversation_json}
""",
    expected_output="""
A concise text summary of the conversation thread, capturing:
- User's main intent.
- Key chatbot responses.
- Overall context in an economical format.
""",
    agent=json_summary_agent,
)

# Task 6: Summary Title Generation
summary_title_generation_task = Task(
    description="""
Description:
Generate a concise and informative title for a user prompt.
Rules to Output:
- The title should capture the essence of the user prompt while being concise and informative.
- Output just the title, nothing else and unformatted.
Chain of Thought:
- Focus on the main subject of the prompt - {user_prompt}
""",
    expected_output="""
A concise and informative title for the user prompt.
""",
    agent=summary_title_agent,
)
