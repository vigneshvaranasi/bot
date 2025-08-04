# Support Bot - Incident Analysis Workflow

## Overview

This CrewAI-powered support bot analyzes historical incident data to provide comprehensive incident analysis and resolution strategies. The system uses three specialized agents working in sequence to research, synthesize, and report on incident patterns and solutions.

## Architecture

### Three-Agent System

1. **Researcher Agent** - Retrieves historical incident data
2. **Synthesizer Agent** - Generates resolution steps based on patterns
3. **Expert Writer Agent** - Creates comprehensive analysis reports

### Tools

- **CustomerSupportDataTool**: Searches and retrieves incident data from `incidents.json`
- **IncidentAnalysisTool**: Analyzes patterns and extracts insights from incident data

## Workflow

```
Query Input → Researcher Agent → Synthesizer Agent → Expert Writer Agent → Final Report
```

### 1. Research Phase
- Searches historical incidents based on query
- Identifies similar past incidents
- Extracts relevant incident details and patterns

### 2. Synthesis Phase  
- Analyzes patterns from research data
- Generates actionable resolution steps
- Creates prevention strategies based on historical successes

### 3. Reporting Phase
- Compiles comprehensive incident analysis report
- Identifies nearest matching historical issue
- Provides root cause explanation
- Presents detailed solution strategy

## Usage

### Basic Usage

```python
from support_bot.crew import support_crew

# Define your query
inputs = {
    'data_query': 'HTTP 499 timeout errors'
}

# Run the analysis
result = support_crew.kickoff(inputs=inputs)
```

### Example Queries

The system can handle various types of queries:

- **HTTP Error Codes**: `"HTTP 499"`, `"HTTP 400"`, `"HTTP 429"`
- **Issue Types**: `"timeout"`, `"latency"`, `"rate limit"`
- **Specific Problems**: `"carding attack"`, `"database outage"`
- **General Terms**: `"performance"`, `"authentication"`

### Sample Output

The system generates a comprehensive report with:

```
## INCIDENT ANALYSIS REPORT

### 1. NEAREST MATCHING ISSUE
- Most similar historical incident
- Relevance and similarity analysis

### 2. ROOT CAUSE ANALYSIS  
- Technical explanation of the issue
- Contributing factors
- Environmental conditions

### 3. SOLUTION STRATEGY
- Immediate resolution steps
- Root cause mitigation
- Prevention strategies
- Monitoring recommendations

### 4. RECOMMENDATIONS
- Long-term improvements
- Process enhancements
- Monitoring upgrades
```

## Running the System

### Prerequisites

1. Set up your environment variables:
   ```bash
   export GEMINI_API_KEY="your_gemini_api_key"
   ```

2. Install dependencies:
   ```bash
   pip install crewai
   ```

### Execution

1. **Direct execution**:
   ```bash
   python src/support_bot/main.py
   ```

2. **Custom queries**:
   ```python
   from support_bot.main import run
   
   # Modify the inputs in main.py or call directly
   inputs = {'data_query': 'your query here'}
   result = support_crew.kickoff(inputs=inputs)
   ```

3. **Test scenarios**:
   ```bash
   python test_scenarios.py
   ```

## Data Source

The system reads from `data/incidents.json` which contains historical incident data with fields:
- Incident ID
- Main Issue  
- Full incident text with details like:
  - Executive summary
  - Impact analysis
  - Root cause
  - Mitigation steps
  - Timeline

## Customization

### Adding New Tools

Create new tools in `src/support_bot/tools/` and import them in the agents:

```python
from .tools.your_new_tool import YourNewTool

# Add to agent
agent = Agent(
    tools=[existing_tools, YourNewTool()],
    # ... other config
)
```

### Modifying Agent Behavior

Update agent prompts in `src/support_bot/agents.py`:

```python
agent = Agent(
    role='Your Custom Role',
    goal='Your specific goal',
    backstory='Your agent backstory',
    # ... other config
)
```

### Customizing Tasks

Modify task descriptions in `src/support_bot/tasks.py` to change agent behavior and output format.

## Files Structure

```
support_bot/
├── data/
│   └── incidents.json              # Historical incident data
├── src/support_bot/
│   ├── agents.py                   # Agent definitions
│   ├── crew.py                     # Crew configuration
│   ├── main.py                     # Main execution script
│   ├── tasks.py                    # Task definitions
│   └── tools/
│       ├── custom_tool.py          # Incident data retrieval tool
│       └── analysis_tool.py        # Pattern analysis tool
├── test_scenarios.py               # Test different query types
└── README.md                       # This file
```
