from crewai import Crew, Process
from .tasks import research_task, synthesis_task, report_task, user_query_response_task, json_summary_task
from .agents import researcher_agent, synthesizer_agent, expert_writer_agent, user_query_responder_agent, json_summary_agent

support_crew = Crew(
    agents=[researcher_agent, synthesizer_agent, expert_writer_agent, user_query_responder_agent],
    tasks=[research_task, synthesis_task, report_task, user_query_response_task],
    process=Process.sequential,
    verbose=True
)

conversation_summary_crew = Crew(
    agents=[json_summary_agent],
    tasks=[json_summary_task],
    process=Process.sequential,
    verbose=True
)