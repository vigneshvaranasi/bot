import os
from crewai import Agent, LLM

# Custom tools
from .tools.qdrant_tool import QdrantIncidentDataTool

# Check if Gemini embeddings should be used - default to true since we use Gemini
use_gemini_embeddings = os.getenv('USE_GEMINI_EMBEDDINGS', 'true').lower() == 'true'
qdrant_data_tool = QdrantIncidentDataTool(use_gemini=use_gemini_embeddings)

def create_llm_from_settings(model: str, temperature: float = 0.7):
    if model.startswith('gemma'):
        return LLM(
            model=f'ollama/{model}',
            base_url='http://202.53.81.125:11434',
            temperature=temperature
        )
    elif model.startswith('gemini'):
        return LLM(
            model=f'gemini/{model}',
            api_key=os.getenv("GEMINI_API_KEY"),
            temperature=temperature
        )
    else:
        # Default fallback
        return LLM(
            model='ollama/gemma3:4b',
            base_url='http://202.53.81.125:11434',
            temperature=temperature
        )

# default LLM
default_llm = create_llm_from_settings("gemma3:4b", 0.7)

# Manager Agent: SupportCoordinator
support_coordinator_agent = Agent(
    role='SupportCoordinator',
    goal="""
Determine routing strategy: assess if context is sufficient, detect user intent (information vs solution), and decide the minimal workflow path needed.
""",
    backstory="""
Backstory:
You are the workflow router for technical support. Your decisions determine which agents execute.
Role Description:
You decide which workflow path to take:
- context_only: Answer directly from provided context
- info_only: Route to researcher for information gathering
- solution_plan: Route to researcher + synthesizer for actionable solutions
Rules to Respond:
- Detect whether user wants information (what/why/history) or solutions (how to fix/resolve)
- Output simple JSON routing decision
""",
    verbose=True,
    allow_delegation=False,
    llm=default_llm
)

# Agent 1: Researcher Agent (HistoryResearcher)
researcher_agent = Agent(
    role='HistoryResearcher',
    goal="""
    Generate optimal search queries for incident databases and retrieve relevant historical incidents.
    """,
    backstory="""
        Backstory:
        You are an expert at searching incident databases. You understand that incidents are indexed by error codes, service names, and symptoms.
        Role Description:
        Create targeted search queries that match how incidents are actually stored and categorized. Return raw incident data without interpretation.
        Rules to Respond:
        - Focus on error codes, service names, and symptoms
        - Output only raw incident data, no interpretation
    """,
    verbose=True,
    allow_delegation=False,
    tools=[qdrant_data_tool],
    llm=default_llm
)

# Agent 2: Synthesizer Agent (SolutionSynthesizer)
synthesizer_agent = Agent(
    role='SolutionSynthesizer',
    goal="""
Transform research findings into structured, actionable resolution plans.
""",
    backstory="""
Backstory:
You create implementable action plans from incident research data.
Role Description:
Focus on immediate resolution steps, root cause mitigation, monitoring guidance, and escalation paths. Only activate when solution-oriented responses are needed.
Rules to Respond:
- Only output structured action plans when required
- Be concise and actionable
""",
    verbose=True,
    allow_delegation=False,
    llm=default_llm
)

# Agent 3: User Query Responder Agent (Responder)
user_query_responder_agent = Agent(
    role='Responder',
    goal="""
Deliver technical information and solutions directly without meta-commentary or self-references.
""",
    backstory="""
Backstory:
You are a technical expert who answers questions directly and professionally.
Role Description:
Start responses with the relevant technical information or steps. For solutions: Begin with concrete actions and steps. For information: Begin with technical details or explanations.
Rules to Respond:
- Never introduce yourself or explain your role
- Use clean Markdown formatting without triple backticks
""",
    verbose=True,
    allow_delegation=False,
    llm=default_llm
)

# Agent 5: JSON Summary Agent
json_summary_agent = Agent(
    role='Conversation Summarizer',
    goal="""
Generate a concise and token-efficient summary of a conversation thread.
""",
    backstory="""
Backstory:
You are an expert in summarizing conversation threads between users and chatbots.
Role Description:
Extract the key context and provide a concise summary that is optimized for token usage.
Rules to Respond:
- Focus on main user intent and key chatbot responses
""",
    verbose=True,
    allow_delegation=False,
    llm=default_llm
)

# Agent 6: Summary Title Agent
summary_title_agent = Agent(
    role='Summary Title Generator',
    goal="""
Create a concise and informative title for User Prompt.
""",
    backstory="""
Backstory:
You are a specialist in generating titles for User Prompts.
Role Description:
Create a title that captures the essence of the user prompt while being concise and informative.
Rules to Respond:
- Output only the title, nothing else
""",
    verbose=True,
    allow_delegation=False,
    llm=default_llm
)

def configure_agents_llm(model: str, temperature: float = 0.7):
    llm = create_llm_from_settings(model, temperature)
    support_coordinator_agent.llm = llm
    researcher_agent.llm = llm
    synthesizer_agent.llm = llm
    user_query_responder_agent.llm = llm
    json_summary_agent.llm = llm
    summary_title_agent.llm = llm