from typing import Annotated, Sequence, TypedDict
from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from .tools import get_incident_report
from langchain.chat_models import init_chat_model

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection
from .config import DATABASE_URL

# DB Initializing
connection_kwargs = {
    "prepare_threshold": 0,
    "autocommit": True,
}


# Initialize the LLM and bind tools

# llm = ChatGoogleGenerativeAI(
#     model=config.LLM_MODEL_NAME,
#     temperature=0,
#     max_retries=2,
#     google_api_key=config.GEMINI_API_KEY,
# )

llm = init_chat_model(
    "google_genai:gemini-2.0-flash",
    temperature=0,
    max_retries=2,
)

# llm = ChatOllama(
#         model="gpt-oss:20b",
#         temperature=0,
#         base_url="http://ollama.trackcode.in",
#         max_retries=2
#     )
    
# Configure the tools the agent can use
allowed_tools = [get_incident_report]

model_with_tools = llm.bind_tools(allowed_tools)


# 1. Define the Agent's State
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]

# 2. Define the Agent's Nodes
def call_model(state: AgentState):
    """Node To Call the LLM."""
    print("---NODE: CALLING MODEL---")
    system_message = SystemMessage(
        "You are an incident resolution assistant. Your role is to help users by providing information only from the incident reports available in the knowledge base. "
        "use the get_incident_report tool to search for relevant information. "
        "If the incident transcripts do not contain the requested information, explicitly state that the information is not available in the knowledge base. "
        "Do not generate, assume, or provide information that is not present in the retrieved incident reports. "
        "Be concise and directly reference the incident data in your responses."
    )
    messages = [system_message] + list(state["messages"])
    response = model_with_tools.invoke(messages)
    return {"messages": [response]}

qdrant_tool_node = ToolNode([get_incident_report])

# 3. Define the Conditional Edge
def wants_qdrant_tool(state: AgentState):
    """
    Decide whether the model wants to call the Qdrant search tool or finish.
    """
    print("---CONDITIONAL EDGE: WANTS QDRANT TOOL?---")
    last_message = state["messages"][-1]
    if not getattr(last_message, "tool_calls", None):
        print("DECISION: End of process.")
        return "end"
    else:
        print("DECISION: Call Qdrant tool.")
        return "continue"

# 4. Assemble the Graph
def create_agent_graph():
    """Creates and Compiles Copilot Agent Graph."""
    conn = Connection.connect(DATABASE_URL, **connection_kwargs)
    checkpointer = PostgresSaver(conn)
    checkpointer.setup()
    
    workflow = StateGraph(AgentState)
    
    workflow.add_node("support_bot", call_model)
    workflow.add_node("qdrant_search", qdrant_tool_node)
    
    workflow.set_entry_point("support_bot")
    
    workflow.add_conditional_edges(
        "support_bot",
        wants_qdrant_tool,
        {"continue": "qdrant_search", "end": END},
    )
    
    workflow.add_edge("qdrant_search", "support_bot")
    
    # Use an in-memory checkpointer so state persists across turns (per process)
    # memory = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)

# app = create_agent_graph()

# png_data = app.get_graph().draw_mermaid_png()
# with open("agent_graph.png", "wb") as f:
#     f.write(png_data)