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

# Local Model
# gemini_llm = LLM(
#     model='ollama/gemma3:1b',
#     base_url='http://localhost:11434',
#     temperature=0
# )

# Check if Gemini embeddings should be used - default to true since we use Gemini
use_gemini_embeddings = os.getenv('USE_GEMINI_EMBEDDINGS', 'true').lower() == 'true'
qdrant_data_tool = QdrantIncidentDataTool(use_gemini=use_gemini_embeddings)
analysis_tool = IncidentAnalysisTool()

# Manager Agent: SupportCoordinator
support_coordinator_agent = Agent(
    role='SupportCoordinator',
    goal=(
        "Determine routing strategy: assess if context is sufficient, detect user intent (information vs solution), "
        "and decide the minimal workflow path needed."
    ),
    backstory=(
        """You are the workflow router for technical support. Your decisions determine which agents execute:
        
        - **context_only**: Answer directly from provided context
        - **info_only**: Route to researcher for information gathering  
        - **solution_plan**: Route to researcher + synthesizer for actionable solutions
        
        Detect whether user wants information (what/why/history) or solutions (how to fix/resolve).
        Output simple JSON routing decision."""
    ),
    verbose=True,
    allow_delegation=False,
    llm=gemini_llm
)

# Agent 1: Researcher Agent (HistoryResearcher)
researcher_agent = Agent(
    role='HistoryResearcher',
    goal='Generate optimal search queries for incident databases and retrieve relevant historical incidents.',
    backstory=(
        """You are an expert at searching incident databases. You understand that incidents are indexed by:
        - Error codes (HTTP 499, 500, timeout, etc.)
        - Service names (PayU, API endpoints)
        - Symptoms (connection issues, slow response, etc.)
        
        Create targeted search queries that match how incidents are actually stored and categorized.
        Return raw incident data without interpretation."""
    ),
    verbose=True,
    allow_delegation=False,
    tools=[qdrant_data_tool],
    llm=gemini_llm
)

# Agent 2: Synthesizer Agent (SolutionSynthesizer)
synthesizer_agent = Agent(
    role='SolutionSynthesizer',
    goal='Transform research findings into structured, actionable resolution plans.',
    backstory=(
        """You create implementable action plans from incident research data.
        Focus on immediate resolution steps, root cause mitigation, monitoring guidance, and escalation paths.
        Only activate when solution-oriented responses are needed."""
    ),
    verbose=True,
    allow_delegation=False,
    tools=[analysis_tool],
    llm=gemini_llm
)

# Agent 3: User Query Responder Agent (Responder)
user_query_responder_agent = Agent(
    role='Responder',
    goal='Provide direct, conversational answers to user queries, using coordinator routing decisions and available research/synthesis data. Avoid referencing context or sources; respond as an expert advisor.',
    backstory=(
        """You respond directly to user queries in a conversational and expert manner, using coordinator's detected intent and available data.
        
        - For solution intent: Offer actionable guidance, solution strategies, and monitoring advice as if speaking to the user.
        - For information intent: Explain root causes or incident details clearly and helpfully.
        
        Do not mention or reference 'context' or sources. Always answer as if you are the expert providing direct support. Use clean Markdown formatting without triple backticks."""
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