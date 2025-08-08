from crewai import Crew, Process
from .tasks import research_task, synthesis_task, report_task, user_query_response_task
from .agents import researcher_agent, synthesizer_agent, expert_writer_agent, user_query_responder_agent

support_crew = Crew(
    agents=[researcher_agent, synthesizer_agent, expert_writer_agent, user_query_responder_agent],
    tasks=[research_task, synthesis_task, report_task, user_query_response_task],
    process=Process.sequential,
    verbose=True
)