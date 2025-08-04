import os
from crewai import Agent, LLM

# Import your custom tools
from .tools.custom_tool import CustomerSupportDataTool
from .tools.analysis_tool import IncidentAnalysisTool

# Use Gemini 2.0 Flash Lite
gemini_llm = LLM(
    model='gemini/gemini-2.0-flash-lite-001',
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.0
)

# Instantiate your custom tools
support_data_tool = CustomerSupportDataTool()
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
    tools=[support_data_tool],
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