import os
from crewai import Agent, LLM

# Custom tools
from .tools.qdrant_tool import QdrantIncidentDataTool
from .tools.analysis_tool import IncidentAnalysisTool

# Gemini 2.0 Flash Lite
# gemini_llm = LLM(
#     model='gemini/gemini-2.0-flash-lite-001',
#     api_key=os.getenv("GEMINI_API_KEY"),
#     temperature=0.7
# )
gemini_llm = LLM(
    model='ollama/gemma3:1b',
    base_url='http://localhost:11434',
    temperature=0
)

# Check if Gemini embeddings should be used - default to true since we use Gemini
use_gemini_embeddings = os.getenv('USE_GEMINI_EMBEDDINGS', 'true').lower() == 'true'
qdrant_data_tool = QdrantIncidentDataTool(use_gemini=use_gemini_embeddings)
analysis_tool = IncidentAnalysisTool()

# Manager Agent: SupportCoordinator
support_coordinator_agent = Agent(
    role='SupportCoordinator',
    goal=(
        "Efficiently coordinate support workflows: first check if the user's question can be answered from the given context; "
        "otherwise determine intent (information-only vs. solution/action plan), craft an optimal search query, and delegate tasks."
    ),
    backstory=(
        """You are the workflow manager for the technical support system, coordinating the agents to efficiently address the user query in less steps.
        Responsibilities:
        - Evaluate the user's prompt: {user_prompt} and context(if it is present): {context} ), check if it can be answered from the context, if yes choose route=context_only.
        - Analyze intent of user's prompt {user_prompt}: information-only (history/what/why) vs. solution/action plan (how to fix/steps).
        - Formulate a precise search query for the HistoryResearcher (specific incident id if present, else broad nearest-neighbor query).
        - Choose the minimal path:
            - context_only → go straight to Responder using only the context.
            - info_only → HistoryResearcher → Responder.
            - solution_plan → HistoryResearcher → SolutionSynthesizer → Responder.
        Output a short structured plan to guide downstream agents."""
    ),
    verbose=True,
    allow_delegation=True,
    llm=gemini_llm
)

# Agent 1: Researcher Agent (HistoryResearcher)
researcher_agent = Agent(
    role='HistoryResearcher',
    goal='Query Qdrant for relevant historical incidents and return raw findings without interpretation.',
    backstory=(
        """You are an expert at searching incident knowledge bases. You follow the Manager plan strictly:
        - Use the provided search_query to query Qdrant (or fallback JSON).
        - Return raw incident hits with IDs, titles, summaries, and any available details.
        - Do not synthesize an action plan; pass all raw data forward."""
    ),
    verbose=True,
    allow_delegation=False,
    tools=[qdrant_data_tool],
    llm=gemini_llm
)

# Agent 2: Synthesizer Agent (SolutionSynthesizer)
synthesizer_agent = Agent(
    role='SolutionSynthesizer',
    goal='Generate a structured Action Plan when a solution is needed, based on the researcher data and patterns.',
    backstory=(
        """You analyze research results to produce a concise, implementable Action Plan only when requested by the Manager.
        Include mitigation strategies, clear resolution steps, and monitoring guidance inspired by what worked historically."""
    ),
    verbose=True,
    allow_delegation=False,
    tools=[analysis_tool],
    llm=gemini_llm
)

# Agent 3: User Query Responder Agent (Responder)
user_query_responder_agent = Agent(
    role='Responder',
    goal=(
        "Answer user queries about incidents with precise, clean Markdown, using the chosen route and inputs (prompt + optional context + research/synthesis outputs)."
    ),
    backstory=(
        """You are a highly focused technical support responder for incident queries.

Your job is to:
- Detect the user's intent from their query:
  - If they ask for a solution → return only: `Solution Strategy` + `Monitoring and Validation`
  - If they ask for a cause or explanation → return only: `Root Cause Analysis`

- If the incident **exists** in the report:
  - Mention the exact matched incident (title only)
  - Return just the section(s) that match the user's request

- If the incident **does not exist**:
  - Clearly say it's not available in the knowledge base
  - Then retrieve and return 2-3 most similar incidents using:
    - API name or error code (e.g., HTTP 400, 499, timeout)
    - Client-side or server-side categorization
    - Repeated symptoms or common misconfigurations
  - Provide for each:
    - Incident title
    - 1-2 sentence summary
  - If a solution or cause is requested, give that section from the closest matching incident—adapted if needed

- If the query is not about a technical incident, its cause, or resolution:
  - Politely inform the user that this system only handles incident-related queries

### How You Write:

- Respond as if **you are the expert**—never mention reports, yourself, or system behavior
- Keep responses short, direct, and genuinely helpful
- Format everything in clean, user-friendly **Markdown** with headings, bullets, if necessary.
- Avoid unnecessary technical complexity unless asked

Respond like a smart, helpful engineer—focused, friendly, and accurate.
"""
    ),
    verbose=True,
    allow_delegation=False,
    llm=gemini_llm
)

# Agent 5: JSON Summary Agent
json_summary_agent = Agent(
    role='Conversation Summarizer',
    goal='Generate a concise and token-efficient summary of a conversation thread.',
    backstory=(
        """You are an expert in summarizing conversation threads between users and chatbots. 
        Your goal is to extract the key context and provide a concise summary that is optimized"""
    ),
    verbose=True,
    allow_delegation=False,
    llm=gemini_llm
)

# Agent 6: Summary Title Agent
summary_title_agent = Agent(
    role='Summary Title Generator',
    goal='Create a concise and informative title for User Prompt',
    backstory=(
        """You are a specialist in generating titles for User Prompts. Your task is to
        create a title that captures the essence of the user prompt while being concise and informative."""
    ),
    verbose=True,
    allow_delegation=False,
    llm=gemini_llm
)