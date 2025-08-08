import os
from crewai import Agent, LLM

# Custom tools
from .tools.qdrant_tool import QdrantIncidentDataTool
from .tools.analysis_tool import IncidentAnalysisTool

# Gemini 2.0 Flash Lite
gemini_llm = LLM(
    model='gemini/gemini-2.0-flash-lite-001',
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.7
)

# Check if Gemini embeddings should be used - default to true since we use Gemini
use_gemini_embeddings = os.getenv('USE_GEMINI_EMBEDDINGS', 'true').lower() == 'true'
qdrant_data_tool = QdrantIncidentDataTool(use_gemini=use_gemini_embeddings)
analysis_tool = IncidentAnalysisTool()

# Agent 1: Researcher Agent
researcher_agent = Agent(
    role='Incident Research Specialist',
    goal='Retrieve and analyze historical incident data to find similar issues and patterns.',
    backstory=(
        """You are an expert incident researcher with deep knowledge of past support issues.
        Your strength lies in quickly finding relevant historical incidents that match current problems
        and extracting key information from incident reports."""
    ),
    verbose=True,
    allow_delegation=False,
    tools=[qdrant_data_tool],
    llm=gemini_llm
)

# Agent 2: Synthesizer Agent
synthesizer_agent = Agent(
    role='Solution Synthesis Specialist',
    goal='Generate practical resolution steps based on historical incident data and patterns.',
    backstory=(
        """You are a seasoned technical problem solver who excels at synthesizing information
        from past incidents to create actionable resolution steps. You understand root causes
        and can translate historical solutions into current actionable recommendations."""
    ),
    verbose=True,
    allow_delegation=False,
    tools=[analysis_tool],
    llm=gemini_llm
)

# Agent 3: Expert Writer Agent
expert_writer_agent = Agent(
    role='Technical Report Writer',
    goal='Create comprehensive incident analysis reports with clear explanations and solution strategies.',
    backstory=(
        """You are an expert technical writer specializing in incident analysis and resolution documentation.
        You excel at explaining complex technical issues in clear terms, identifying root causes,
        and presenting comprehensive solution strategies based on historical precedents."""
    ),
    verbose=True,
    allow_delegation=False,
    llm=gemini_llm
)

# Agent 4: User Query Responder Agent
user_query_responder_agent = Agent(
    role='Incident Query Responder',
    goal=(
        "Answer user queries about technical incidents with **precise, markdown-formatted summaries** "
        "based strictly on the provided analysis report. but donot mention the report or system behavior, it should conversative"
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