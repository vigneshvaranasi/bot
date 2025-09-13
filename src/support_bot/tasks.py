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
- MUST output valid JSON format: {{"route": "context_only|info_only|solution_plan", "detected_intent": "information|solution", "rationale": "brief explanation"}}
- If context contains sufficient information to answer {user_prompt}, choose "context_only"
- If user asks about past incidents, errors, or information, choose appropriate route
- If user asks for solutions, fixes, or how-to, choose "solution_plan"
- Rationale should be 1-2 sentences explaining the decision

Chain of Thought:
- Analyze if provided context can directly answer the user prompt
- Determine if user wants information (what/why/history) or solutions (how to fix/resolve)  
- Choose minimal workflow: context_only > info_only > solution_plan
- Always respond with valid JSON - no additional text or explanation
""",
    expected_output="""
Valid JSON only: {{"route": "context_only|info_only|solution_plan", "detected_intent": "information|solution", "rationale": "explanation"}}
""",
    agent=support_coordinator_agent,
)

# Task 1: Research - Generate search query and retrieve incidents
research_task = Task(
    description="""
Description:
Analyze the user prompt to understand what it's about and generate an appropriate search query for the incident database.

Chain of Thought:
- Check if route='context_only' from manager_plan_task, if so return "[]"
- Analyze {user_prompt} to understand what the user is talking about
- If {user_prompt} refers to {context}, include relevant context information
- Generate a focused search query based on the topic/issue the user is asking about
- Use Qdrant Incident Data Retriever tool exactly once with the generated search query
- Return the raw results from the tool

Rules to Output:
- If route='context_only': Return exactly "[]" (empty array string)
- Otherwise: Generate search query based on what {user_prompt} is discussing
- Create search terms that match the topic, issue type, or technical problem mentioned
- Use the tool only once with your generated search query
- Return raw incident data text from database search
""",
    expected_output="""
Raw incident data from database search as formatted text, or "[]" if no research needed
""",
    agent=researcher_agent,
    context=[manager_plan_task],
)

# Task 2: Synthesis - Create Solution Strategy

synthesis_task = Task(
    description="""
Description:
Transform research results into actionable resolution plans for technical issues.

Rules to Output:
- Check routing decision from manager_plan_task - if route='context_only', return ""
- If research results are "[]" or empty, return ""
- Only synthesize for solution-oriented queries (detected_intent='solution')
- Focus only on creating structured action plans from historical incident data
- Output structured sections: Immediate Steps, Root Cause Mitigation, Monitoring, Escalation Path
- Be concise and actionable - focus on implementable solutions only
- Return clean Markdown text structure, never JSON format

Chain of Thought:
- Extract routing decision and detected intent from manager_plan_task
- If route='context_only' OR research results are empty: return ""
- If detected_intent='information': return "" (info queries don't need action plans)
- If detected_intent='solution': analyze research data to identify:
  - Common patterns in similar incidents from the data
  - Successful mitigation strategies that worked in past incidents
  - Typical resolution steps with proven effectiveness
- Create structured action plan with:
  - Immediate Steps (urgent actions to take now)
  - Root Cause Mitigation (fix underlying issue based on historical patterns)
  - Monitoring (what metrics to watch based on past incidents)
  - Escalation Path (when and where to escalate if steps don't work)
- Extract actionable guidance specifically from the historical incident resolutions provided
""",
    expected_output="""
Structured action plan in clean Markdown format with sections for Immediate Steps, Root Cause Mitigation, Monitoring, and Escalation Path. Empty string if no synthesis needed.
""",
    agent=synthesizer_agent,
    context=[manager_plan_task, research_task],
)

# Task 3: User Response - Format based on routing and data

user_query_response_task = Task(
    description="""
Description:
Answer the user's query directly and professionally based on the routing decision and available data.

Rules to Output:
- Check the route from manager_plan_task output to determine response approach
- If route='context_only': Answer strictly from the provided {context} - use research or synthesis data if its required to clarify
- If route='info_only' or 'solution_plan': Use research data and synthesis (if available) to provide comprehensive response
- Never introduce yourself or explain your role - start directly with the answer
- Use clean Markdown formatting (h1, h2, h3, lists) without triple backticks
- Keep responses concise, direct, and professional
- Never reference the context source, research process, or your capabilities
- Return only clean Markdown text, never JSON format

Chain of Thought:
- Extract route decision from manager_plan_task context
- For 'context_only': Use only the original {context} provided with {user_prompt}
- For 'info_only': Combine research findings with informational explanation 
- For 'solution_plan': Use research findings + synthesis action plan for comprehensive solution
- Structure response based on user's detected intent:
  - Information queries: Technical explanation, causes, background
  - Solution queries: Immediate steps, mitigation, monitoring, escalation
- Ensure response directly addresses {user_prompt} without meta-commentary
""",
    expected_output="""
Clean Markdown response directly answering the user query, using appropriate data based on routing decision
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
