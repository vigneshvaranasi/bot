"""LangGraph agent for the incident resolution copilot.

This module defines the agent graph that processes user queries,
searches the knowledge base, and generates responses.
"""

import logging
from typing import Annotated, Any, Dict, Optional, Sequence, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langfuse import propagate_attributes
from langfuse.langchain import CallbackHandler
from psycopg import Connection

import src.copilot.config as config
# LLM factory imports are done lazily in set_llm_from_config and get_configured_llm
from src.copilot.tools import available_tools

logger = logging.getLogger(__name__)

# Connection settings for PostgreSQL checkpointer
_connection_kwargs = {
    "prepare_threshold": 0,
    "autocommit": True,
}

# Lazy-initialized Langfuse handler (avoid network connections at import time)
_langfuse_handler = None


def _get_model_with_tools() -> BaseChatModel:
    """Get the configured LLM bound with tools.

    Returns:
        LLM instance with tools bound.
    """
    llm = get_configured_llm()
    return llm.bind_tools(available_tools)


def _get_langfuse_handler() -> CallbackHandler:
    """Get or create the Langfuse callback handler with lazy initialization."""
    global _langfuse_handler
    if _langfuse_handler is None:
        _langfuse_handler = CallbackHandler()
    return _langfuse_handler


def _get_callbacks(state: dict) -> list:
    """Get callbacks based on state configuration.

    Args:
        state: Agent state containing langfuse_enabled flag

    Returns:
        List of callbacks to use for LLM invocations
    """
    # Default to False for privacy - tracking requires explicit opt-in
    if state.get("langfuse_enabled", False):
        return [_get_langfuse_handler()]
    return []


class AgentState(TypedDict):
    """State schema for the agent graph."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    title: Optional[str]
    session_id: Optional[str]
    user_id: Optional[str]
    langfuse_enabled: Optional[bool]
    generate_title: Optional[bool]


# Global LLM instance cache (refreshed when provider config changes)
_cached_llm: Optional[BaseChatModel] = None
_cached_llm_config_hash: Optional[str] = None


def set_llm_from_config(
    provider_type: Optional[str] = None,
    model_id: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    provider_config: Optional[Dict[str, Any]] = None,
    temperature: Optional[float] = None,
) -> None:
    """Set the LLM instance from provider configuration.

    This function should be called before invoking the graph to configure
    which LLM provider to use. The LLM is cached and reused until the
    configuration changes.

    Args:
        provider_type: Type of provider (anthropic, openai, google, custom).
        model_id: Model identifier.
        api_key: Decrypted API key.
        base_url: Provider base URL.
        provider_config: Additional provider config.
        temperature: LLM temperature setting.
    """
    global _cached_llm, _cached_llm_config_hash

    # Create a hash of the config to detect changes
    config_tuple = (provider_type, model_id, base_url, temperature)
    config_hash = str(hash(config_tuple))

    # Only recreate if config changed
    if _cached_llm_config_hash == config_hash and _cached_llm is not None:
        return

    # Create new LLM from config
    if provider_type and model_id:
        from src.copilot.llm_factory import create_llm_from_provider
        _cached_llm = create_llm_from_provider(
            provider_type=provider_type,
            model_id=model_id,
            api_key=api_key,
            base_url=base_url,
            provider_config=provider_config or {},
            temperature=temperature or config.DEFAULT_LLM_TEMPERATURE,
        )
        logger.info(f"Configured LLM: {provider_type}/{model_id}")
    else:
        from src.copilot.llm_factory import get_default_llm
        _cached_llm = get_default_llm(
            temperature=temperature or config.DEFAULT_LLM_TEMPERATURE
        )
        logger.info("Using default Ollama LLM")

    _cached_llm_config_hash = config_hash


def get_configured_llm() -> BaseChatModel:
    """Get the currently configured LLM instance.

    Returns:
        The cached LLM instance, or creates a default one if not configured.
    """
    global _cached_llm
    if _cached_llm is None:
        from src.copilot.llm_factory import get_default_llm
        _cached_llm = get_default_llm()
    return _cached_llm


SYSTEM_MESSAGE_PROMPT = SystemMessage(
    """
    You are an expert incident resolution assistant with perfect memory of this conversation.

    Your primary goal is to answer user questions about incidents. Follow this logic:

    1. **When to Use Memory vs Tools:**
       - Use memory ONLY for follow-up questions about incidents where a tool has ALREADY
         returned data in a previous turn
       - ALWAYS use a tool when encountering a NEW incident ID or new search topic
       - If unsure whether you have the data, USE THE TOOL

    2. **Select the Right Tool:**
       - `lookup_incident_by_id`: When user mentions a specific ID (e.g., INC-2025-08-24-001)
       - `search_similar_incidents`: When user describes a problem/error without an ID
       - `get_incidents_by_application`: When asking about a specific app/system
       - `get_recent_incidents`: When asking about recent incidents or timeframes

    3. **Query Rewriting for Tools:**
       Before calling any tool, you MUST rewrite the user's conversational query into a
       search-optimized format. Extract the core search intent and remove conversational fluff.

       Examples:
       - "hey how to solve the issue with loan emi?" → query: "Loan EMI issue"
       - "can you tell me about payment gateway errors?" → query: "payment gateway errors"
       - "what happened with the Swift transfer delays last week?" → query: "Swift transfer delays"
       - "I need help with HTTP 403 forbidden errors in PayU" → query: "HTTP 403 forbidden PayU"
       - "tell me about this issue INC-2025-08-24-001" → incident_id: "INC-2025-08-24-001"

       Always pass CLEAN, CONCISE search terms to tools - never raw conversational text.

    4. **Tool Usage Rules:**
       * Base answers ONLY on retrieved context from tools
       * ALWAYS cite the source incident ID (e.g., "Based on incident INC-2025-08-24-001...")
       * If no relevant info found, state this clearly
       * You may call multiple tools if needed

    5. Do not make up information. Be concise and factual. Never use code fences to encapsulate responses.
    """
)


def call_model(state: AgentState) -> dict:
    """Node to call the LLM with the current state.

    Args:
        state: Current agent state with messages

    Returns:
        Dictionary with new messages to add to state
    """
    logger.debug("NODE: CALLING MODEL")

    # Get the configured LLM with tools
    model_with_tools = _get_model_with_tools()

    messages = [SYSTEM_MESSAGE_PROMPT] + list(state["messages"])
    callbacks = _get_callbacks(state)

    with propagate_attributes(
        session_id=state.get("session_id"),
        user_id=state.get("user_id")
    ):
        response = model_with_tools.invoke(
            messages,
            config={"callbacks": callbacks, "run_name": "Support Bot LLM"},
        )
    return {"messages": [response]}


_qdrant_tool_node = ToolNode(available_tools)


def tool_wrapper(state: AgentState) -> dict:
    """Wrapper node for tool execution with proper callbacks.

    Args:
        state: Current agent state

    Returns:
        Tool execution results
    """
    callbacks = _get_callbacks(state)
    with propagate_attributes(
        session_id=state.get("session_id"),
        user_id=state.get("user_id")
    ):
        return _qdrant_tool_node.invoke(
            state,
            config={"callbacks": callbacks, "run_name": "Incident Report Qdrant Tool"},
        )


def wants_qdrant_tool(state: AgentState) -> str:
    """Conditional edge: decide whether to call tool, generate title, or end.

    Args:
        state: Current agent state

    Returns:
        Next node name: "continue", "title_generation", or "end"
    """
    writer = get_stream_writer()
    logger.debug("CONDITIONAL EDGE: WANTS QDRANT TOOL?")

    last_message = state["messages"][-1]
    if not getattr(last_message, "tool_calls", None):
        should_generate_in_graph = state.get("generate_title", True)

        if not state.get("title") and should_generate_in_graph:
            writer({"status": "Generating title for the incident report..."})
            logger.debug("DECISION: Call Title Generation Node.")
            return "title_generation"
        else:
            writer({"status": "Almost done, wrapping up the details"})
            logger.debug("DECISION: End of process.")
            return "end"
    else:
        writer({"status": "Analyzing your request... please hold on."})
        logger.debug("DECISION: Call Qdrant tool.")
        return "continue"


def title_generation_node(state: AgentState) -> dict:
    """Node to generate a title for the conversation.

    Args:
        state: Current agent state with messages

    Returns:
        Dictionary with generated title
    """
    writer = get_stream_writer()
    logger.debug("NODE: GENERATING TITLE")

    # Get the configured LLM
    llm = get_configured_llm()

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

    callbacks = _get_callbacks(state)
    with propagate_attributes(
        session_id=state.get("session_id"),
        user_id=state.get("user_id")
    ):
        response = llm.invoke(
            [prompt],
            config={"callbacks": callbacks, "run_name": "Title Generator LLM"},
        )

    title_text = response.content.strip()
    if not title_text:
        title_text = "Untitled Chat"

    logger.debug(f"Generated Title: {title_text}")
    writer({"title": title_text})
    writer({"status": "Almost done, wrapping up the details"})

    return {"title": title_text}


def generate_title_from_query(
    query: str,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    langfuse_enabled: bool = False,
) -> str:
    """Generate a title from user query (standalone, for parallel execution).

    This function is designed to be called in parallel with the main response
    generation. It uses only the user query to generate a title, allowing
    title generation to start immediately without waiting for the response.

    Args:
        query: The user's query/message
        session_id: Optional session ID for tracing
        user_id: Optional user ID for tracing
        langfuse_enabled: Whether Langfuse tracing is enabled

    Returns:
        Generated title string
    """
    logger.debug("PARALLEL TITLE GENERATION: Starting")

    llm = get_configured_llm()

    prompt = SystemMessage(
        "Generate a concise, 2-4 word title for this query. "
        "The title should clearly represent the main theme or subject. "
        f"Query: {query}\n\n"
        "Prioritize accuracy over excessive creativity; keep it clear and simple. "
        "The output must be only the title, without any markdown code fences or other encapsulating text."
    )

    callbacks = []
    if langfuse_enabled:
        callbacks = [_get_langfuse_handler()]

    with propagate_attributes(session_id=session_id, user_id=user_id):
        response = llm.invoke(
            [prompt],
            config={"callbacks": callbacks, "run_name": "Parallel Title Generator"},
        )

    title_text = response.content.strip()
    if not title_text:
        title_text = "Untitled Chat"

    logger.debug(f"PARALLEL TITLE GENERATION: Generated '{title_text}'")
    return title_text


def create_agent_graph():
    """Create and compile the agent graph with PostgreSQL checkpointing.

    Returns:
        Compiled LangGraph workflow ready for invocation

    Note:
        The connection to PostgreSQL is managed internally. For production,
        consider using a connection pool for better resource management.
    """
    conn = Connection.connect(config.VECTOR_DATABASE_URL, **_connection_kwargs)
    checkpointer = PostgresSaver(conn)
    checkpointer.setup()

    workflow = StateGraph(AgentState)

    workflow.add_node("support_bot", call_model)
    workflow.add_node("incident_tools", tool_wrapper)
    workflow.add_node("title_generation", title_generation_node)

    workflow.set_entry_point("support_bot")

    workflow.add_conditional_edges(
        "support_bot",
        wants_qdrant_tool,
        {
            "continue": "incident_tools",
            "title_generation": "title_generation",
            "end": END,
        },
    )

    workflow.add_edge("incident_tools", "support_bot")
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
