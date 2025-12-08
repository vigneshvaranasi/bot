from typing import Annotated, Sequence, TypedDict,Optional
from langchain_core.messages import BaseMessage, SystemMessage,AIMessageChunk
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from src.copilot.tools.qdrantretriever import get_incident_report, available_tools
from langchain.chat_models import init_chat_model
import src.copilot.config as config
from langgraph.config import get_stream_writer
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection
import logging
from langfuse import propagate_attributes
from langfuse.langchain import CallbackHandler

langfuse_handler = CallbackHandler()

connection_kwargs = {
    "prepare_threshold": 0,
    "autocommit": True,
}

llm = ChatOllama(
        model="gpt-oss:20b",
        temperature=0.33,
        base_url="http://ollama.trackcode.in",
        max_retries=2
    )

model_with_tools = llm.bind_tools(available_tools)

stream_modes = ["custom","messages"]

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    title: Optional[str]
    session_id: Optional[str]
    user_id: Optional[str]
    langfuse_enabled: Optional[bool]


system_message_prompt = SystemMessage(
    """
    You are an expert incident resolution assistant, and you have a perfect memory of this conversation.

    Your primary goal is to answer the user's questions. Follow this logic:

    1.  **Check Memory First:** Carefully review the *entire* chat history (the 'messages'). If the user's latest question can be answered completely using information *already present* in the history (e.g., they are asking "what was that ID again?" about an incident you just discussed), then answer it directly from memory.

    2.  **Use Tool if Needed:** You MUST use the `get_incident_report` tool to search the knowledge base.

    3.  **Tool Usage Rules (When you use the tool):**
        * The tool will return one or more "Retrieved Context" blocks from past incidents.
        * You must base your answer *ONLY* on this "Retrieved Context".
        * You MUST cite the source by mentioning the "Source Incident ID" (e.g., "Based on incident INC-2025-08-24-001...") or "From Knowledge Base".
        * If the tool finds no relevant information, state that the information is not available in the knowledge base and suggest asking about the incidents that are nearer to user's message.

    4.  **Final Rule:** Do not make up information or answer questions outside of this scope. Be concise and factual and never use \n```\n to encapsulate your responses.
    """
)


def call_model(state: AgentState):
    """Node To Call the LLM."""
    print("---NODE: CALLING MODEL---")
    
    messages = [system_message_prompt] + list(state["messages"])
    
    with propagate_attributes(session_id=state.get("session_id"), user_id=state.get("user_id")):
        response = model_with_tools.invoke(
            messages,
            config={"callbacks": [langfuse_handler],"run_name": "Support Bot LLM"},
        )
    return {"messages": [response]}

qdrant_tool_node = ToolNode(available_tools)
def tool_wrapper(state: AgentState):
    with propagate_attributes(session_id=state.get("session_id"), user_id=state.get("user_id")):
        return qdrant_tool_node.invoke(
            state,
            config={"callbacks": [langfuse_handler],"run_name": "Incident Report Qdrant Tool"},
        )

def wants_qdrant_tool(state: AgentState):
    """
    Decide whether the model wants to call the Qdrant search tool or finish.
    """
    writer = get_stream_writer()
    print("---CONDITIONAL EDGE: WANTS QDRANT TOOL?---")
    last_message = state["messages"][-1]
    if not getattr(last_message, "tool_calls", None):
        if not state.get("title"):
            writer({
                "status": "Generating title for the incident report..."
            })
            print("DECISION: Call Title Generation Node.")
            return "title_generation"
        else:
            writer({
                "status": "Almost done, wrapping up the details"
            })
            print("DECISION: End of process.")
            return "end"
    else:
        writer({
            "status": "Analyzing your request... please hold on."
        })
        print("DECISION: Call Qdrant tool.")
        return "continue"


def title_generation_node(state: AgentState):
    """Node To Generate Title for the Incident Report."""
    writer = get_stream_writer()
    print("---NODE: GENERATING TITLE---")
    
    chat_text = "\n".join(
        f"{m.type.upper()}: {getattr(m, 'content', '')}"
        for m in state["messages"]
    )

    prompt = SystemMessage(
        "Generate a concise, 2-4 word title by using the chat history. "
        "The title should clearly represent the main theme or subject of the conversation. "
        "Here is a conversation transcript:\n"
        f"{chat_text}\n\n"
        "Prioritize accuracy over excessive creativity; keep it clear and simple. "
        "The output must be only the title, without any markdown code fences or other encapsulating text."
    )
    with propagate_attributes(session_id=state.get("session_id"), user_id=state.get("user_id")):
        response = llm.invoke(
        [prompt],
        config={"callbacks": [langfuse_handler], "run_name": "Title Generator LLM"},
    )
    title_text = response.content.strip()
    if not title_text:
        title_text = "Untitled Chat"
    print(f"Generated Title: {title_text}")
    writer({
        "title": title_text
    })
    writer({
        "status": "Almost done, wrapping up the details"
    })
    return {"title": title_text}

def create_agent_graph():
    """Creates and Compiles Copilot Agent Graph."""
    
    conn = Connection.connect(config.VECTOR_DATABASE_URL, **connection_kwargs)
    checkpointer = PostgresSaver(conn)
    checkpointer.setup()
    workflow = StateGraph(AgentState)
    
    workflow.add_node("support_bot", call_model)
    workflow.add_node("qdrant_search", tool_wrapper)
    workflow.add_node("title_generation", title_generation_node)
    
    workflow.set_entry_point("support_bot")
    
    workflow.add_conditional_edges(
        "support_bot",
        wants_qdrant_tool,
        {"continue": "qdrant_search", "title_generation": "title_generation", "end": END},
    )
    
    workflow.add_edge("qdrant_search", "support_bot")
    workflow.add_edge("title_generation", END)
    
    return workflow.compile(checkpointer=checkpointer)

# app = create_agent_graph()
# for mode, chunk in app.stream(
#     config={"configurable": {"thread_id": "hfsshffffbhjabshjdbd5454dssdvvbfgsdgg"}},
#     input={"messages": [("user", "What was the action taken?")]},
#     stream_mode=stream_modes
# ):
#     if(mode=="custom"):
#         print("-"*20)
#         print("Update:",chunk)
#         print("+"*20)
#     elif(mode == "messages"):
#         token_chunk, metadata = chunk
#         if metadata.get('langgraph_node')!='qdrant_search' and isinstance(token_chunk, AIMessageChunk) and token_chunk.content:
#             print(token_chunk.content, end="", flush=True)