from crewai import Task
from .agents import researcher_agent, synthesizer_agent, expert_writer_agent

# Task 1: Research historical incidents
research_task = Task(
    description=(
        """Use the Customer Support Data Fetcher tool to retrieve historical incident data based on the provided data_query.
        Search for incidents that are similar or related to the query terms. Analyze the retrieved incidents to identify:
        - The most relevant/similar historical incident(s)
        - Common patterns and root causes
        - Previous resolution approaches that were successful
        - Any recurring themes or issues
        
        Query to search: {data_query}"""
    ),
    expected_output=(
        """A detailed analysis report containing:
        - List of relevant historical incidents found
        - Summary of the most similar incident(s) to the current query
        - Key patterns identified across similar incidents
        - Root causes and contributing factors from past incidents
        - Previous successful resolution methods"""
    ),
    agent=researcher_agent
)

# Task 2: Synthesize resolution steps
synthesis_task = Task(
    description=(
        """Based on the historical incident analysis provided by the Researcher Agent, generate comprehensive 
        resolution steps for addressing similar issues. Focus on:
        - Immediate action items based on past successful resolutions
        - Preventive measures to avoid recurrence
        - Best practices derived from historical data
        - Step-by-step troubleshooting approach
        - Escalation procedures if initial steps fail
        
        Consider the root causes and successful mitigation strategies from the historical data."""
    ),
    expected_output=(
        """A structured resolution strategy containing:
        - Immediate Resolution Steps (prioritized action items)
        - Root Cause Mitigation (steps to address underlying causes)
        - Prevention Strategy (measures to prevent recurrence)
        - Monitoring and Validation (how to confirm resolution)
        - Escalation Path (next steps if resolution fails)"""
    ),
    agent=synthesizer_agent,
    context=[research_task]
)

# Task 3: Generate comprehensive report
report_task = Task(
    description=(
        """Compile a comprehensive incident analysis report using the research findings and resolution steps.
        The report should be detailed and professional, containing:
        
        1. **Nearest Matching Issue**: Identify and describe the most similar historical incident
        2. **Root Cause Explanation**: Provide detailed explanation of why this type of issue occurs
        3. **Solution Strategy**: Present the resolution steps recommended by the Synthesizer Agent
        
        Make the report clear, actionable, and suitable for both technical teams and management."""
    ),
    expected_output=(
        """A comprehensive incident analysis report with the following sections:
        
        ## INCIDENT ANALYSIS REPORT
        
        ### 1. NEAREST MATCHING ISSUE
        - Incident ID and description of the most similar historical case
        - Similarity analysis and relevance score
        
        ### 2. ROOT CAUSE ANALYSIS
        - Detailed explanation of why this issue typically occurs
        - Contributing factors and environmental conditions
        - Technical and operational root causes
        
        ### 3. SOLUTION STRATEGY
        - Complete resolution steps from the Synthesizer Agent
        - Implementation timeline and resource requirements
        - Success metrics and validation criteria
        
        ### 4. RECOMMENDATIONS
        - Long-term prevention strategies
        - Process improvements
        - Monitoring enhancements"""
    ),
    agent=expert_writer_agent,
    context=[research_task, synthesis_task]
)