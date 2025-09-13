from crewai import Crew, Process
from .tasks import manager_plan_task, research_task, synthesis_task, user_query_response_task, json_summary_task, summary_title_generation_task
from .agents import support_coordinator_agent, researcher_agent, synthesizer_agent, user_query_responder_agent, json_summary_agent, summary_title_agent

support_crew = Crew(
    agents=[support_coordinator_agent, researcher_agent, synthesizer_agent, user_query_responder_agent],
    tasks=[manager_plan_task, research_task, synthesis_task, user_query_response_task],
    process=Process.sequential,
    verbose=True,
    # Memory
    memory=False,
    # Cache
    # cache=True
)

conversation_summary_crew = Crew(
    agents=[json_summary_agent],
    tasks=[json_summary_task],
    process=Process.sequential,
    verbose=True
)

conversation_title_generation_crew = Crew(
    agents=[summary_title_agent],
    tasks=[summary_title_generation_task],
    process=Process.sequential,
    verbose=True
)