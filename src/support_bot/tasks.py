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

# Task 0: Manager planning with context-first optimization and routing
manager_plan_task = Task(
    description=(
        """As SupportCoordinator, determine the minimal workflow to answer the user's prompt.

1) Context-first optimization: If the answer can be produced from {context} alone with high confidence, select route=context_only.
2) Intent analysis: Determine if the user asks for information-only (what/why/history) or a solution/action plan (how/steps/mitigation).
3) Routing:
   - context_only → Responder only
   - info_only → HistoryResearcher → Responder
   - solution_plan → HistoryResearcher → SolutionSynthesizer → Responder
4) Build search_query: If a specific incident id/code is present, craft a targeted query; else craft a broad nearest-neighbor query.

Produce a compact JSON plan with fields: route, search_query, rationale.
Input prompt: {user_prompt}
Context: {context}
"""
    ),
    expected_output=(
        """A compact JSON object: {\"route\": \"context_only|info_only|solution_plan\", \"search_query\": \"...\", \"rationale\": \"...\"}"""
    ),
    agent=support_coordinator_agent,
)

# Task 1: Research historical incidents per manager plan
research_task = Task(
    description=(
        """Follow the SupportCoordinator plan from the context. Steps:
1) Parse the plan JSON from SupportCoordinator output in your context to get: route and search_query.
2) If route=context_only → DO NOT use any tools. Output exactly: 'SKIP: context_only'.
3) Otherwise → use the Qdrant tool to run the search using the extracted search_query.
4) Return raw incident data (IDs, titles, summaries/details, scores if any) without interpretation.
"""
    ),
    expected_output=(
        """Raw incident hits including IDs, titles, summaries/details, and any scores available. Provide up to 5 results, or 'SKIP: context_only'."""
    ),
    agent=researcher_agent,
    context=[manager_plan_task],
)

# Task 2: Synthesize resolution steps (only when needed by route)
synthesis_task = Task(
    description=(
        """If route=solution_plan, transform the research raw results into an Action Plan:
- Immediate Resolution Steps (prioritized)
- Mitigation strategies linked to likely causes
- Monitoring and Validation guidance
- Escalation Path if initial steps fail
If route is not solution_plan, output 'SKIP: no_synthesis'.
"""
    ),
    expected_output=(
        """Action Plan with sections: Immediate Steps, Root Cause Mitigation, Monitoring and Validation, Escalation Path; or 'SKIP: no_synthesis'."""
    ),
    agent=synthesizer_agent,
    context=[manager_plan_task, research_task],
)

# Removed the monolithic report task; the Responder consumes research/synthesis directly.

# Task 3: User Query Response
user_query_response_task = Task(
    description=(
        """Produce the final answer for the user in Markdown.
Use this routing logic from SupportCoordinator plan:
- If route=context_only → answer using only {context}, do not perform research/synthesis.
- If route=info_only → use research results to answer information requests (root causes, nearest incidents), skip synthesis.
- If route=solution_plan → use research + action plan to answer with Solution Strategy and Monitoring and Validation.

Always consider the original prompt: {user_prompt} and the provided context: {context}.
Your response must be **clear, concise, and strictly formatted in Markdown**.
Do NOT wrap the entire response in any fenced code block (no ``` or ```markdown). Use headings and lists directly.

---

### INTENT DETECTION:

- **If the user asks for a solution** → Provide:
  - `Solution Strategy`
    - `Monitoring and Validation`

- **If the user asks for a cause or explanation** → Provide:
    - `Root Cause Analysis`

- **If the exact incident is found**:
  - Mention the matched incident title.
  - Return only the relevant section(s) based on user intent.

 - **If the exact incident is not found**:
  - Do not block the answer. Retrieve and summarize the 3-4 most recent, nearest incidents based on:
    - API name or error type (e.g., HTTP 499, timeout).
    - Client-side vs server-side nature.
    - Similar symptoms or misconfigurations.
    - For each incident (3-4), provide:
    - Title.
    - 1-2 sentence summary.
  - If a solution or cause is requested, adapt and provide that section from the closest match.

- **If the query is unrelated to incidents**:
  - Respond politely: "This system is designed only to handle incident-related queries."

---

### RESPONSE GUIDELINES:

- Use a **friendly and helpful tone**.
- Avoid mentioning the report or system behavior.
- Minimize technical jargon unless necessary.
- Format responses in **Markdown**:
        - Use bold headers, bullet points, and spacing for readability.
        - Never include triple backticks in the output.
"""
    ),
    expected_output=(
        """A markdown-formatted response that includes relevant sections based on the selected route and user intent; cites matched incident titles when appropriate; and if no exact match exists, lists 3-4 most recent nearest incidents (title + short summary) and adapts content as needed. Avoid triple backticks."""
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
        """
    ),
    expected_output=("""A concise and informative title for the user prompt."""),
    agent=summary_title_agent,
)
