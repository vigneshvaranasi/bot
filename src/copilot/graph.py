"""LangGraph agent for the incident resolution copilot.

This module defines the agent graph that processes user queries,
searches the knowledge base, and generates responses.
"""

import hashlib
import json
import logging
from collections import OrderedDict
from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional, Sequence, Tuple, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langfuse import propagate_attributes
from langfuse.langchain import CallbackHandler
from psycopg import Connection

import src.copilot.config as config
# LLM factory imports are done lazily in create_llm_for_request and get_configured_llm
from src.copilot.tools import available_tools
from src.api.utils.tracing import get_langfuse_client
from src.api.services.golden_example_service import (
    search_golden_examples_sync,
    build_prompt_with_golden_examples,
)
import threading
import atexit

logger = logging.getLogger(__name__)


def _extract_text_content(content: Any) -> str:
    """Normalize LLM response content to a plain string.

    OpenAI/Gemini return content as str; Anthropic returns a list of
    content blocks.  Strips surrounding quotes that some models add.
    """
    if content is None:
        return ""
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
            elif hasattr(block, "text"):
                parts.append(getattr(block, "text", "") or "")
            else:
                parts.append(str(block) if block is not None else "")
        text = "".join(parts)
    else:
        text = str(content)
    # Strip whitespace, then surrounding quotes some models add
    text = text.strip().strip('"').strip("'").strip()
    return text

# Connection settings for PostgreSQL checkpointer
_connection_kwargs = {
    "prepare_threshold": 0,
    "autocommit": True,
}

def _get_model_with_tools(state: Optional[Dict[str, Any]] = None) -> BaseChatModel:
    """Get the configured LLM bound with tools.

    Args:
        state: Agent state containing llm_config for per-request LLM.

    Returns:
        LLM instance with tools bound.
    """
    llm = get_configured_llm(state)
    return llm.bind_tools(available_tools)


def create_langfuse_callback(
    langfuse_config: Optional[Dict[str, str]] = None,
    trace_context: Optional[Dict[str, str]] = None,
) -> CallbackHandler:
    """Create a Langfuse callback handler, optionally nesting under a trace.

    This handler should be created ONCE per request and passed via the graph's
    config (not per-node) so that the entire LangGraph execution tree appears
    as one unified trace in Langfuse.

    Args:
        langfuse_config: Dict with secret_key, public_key, host. If None, uses env vars.
        trace_context: Dict with trace_id and parent_span_id from the parent trace.
    """
    try:
        get_langfuse_client(langfuse_config)
    except Exception as e:
        logger.warning(f"Failed to initialize Langfuse client for callbacks: {e}")

    kwargs: Dict[str, Any] = {}
    if langfuse_config and langfuse_config.get("public_key"):
        kwargs["public_key"] = langfuse_config["public_key"]
    if trace_context:
        kwargs["trace_context"] = trace_context
    return CallbackHandler(**kwargs)


class AgentState(TypedDict):
    """State schema for the agent graph."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    title: Optional[str]
    session_id: Optional[str]
    user_id: Optional[str]
    langfuse_enabled: Optional[bool]
    langfuse_config: Optional[Dict[str, str]]
    generate_title: Optional[bool]
    llm_config: Optional[Dict[str, Any]]
    guardrail_config: Optional[Dict[str, Any]]

_llm_cache: Dict[str, BaseChatModel] = {}
_llm_cache_lock = threading.Lock()
_LLM_CACHE_MAX_SIZE = 20


def create_llm_for_request(
    provider_type: Optional[str] = None,
    model_id: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    provider_config: Optional[Dict[str, Any]] = None,
    temperature: Optional[float] = None,
) -> BaseChatModel:
    """Create or retrieve a cached LLM instance for a request.

    Thread-safe. The cache key includes api_key to prevent cross-user
    contamination.

    Args:
        provider_type: Type of provider (anthropic, openai, google, custom).
        model_id: Model identifier.
        api_key: Decrypted API key.
        base_url: Provider base URL.
        provider_config: Additional provider config.
        temperature: LLM temperature setting.

    Returns:
        An LLM instance for this configuration.
    """
    config_tuple = (provider_type, model_id, api_key, base_url, temperature)
    config_hash = str(hash(config_tuple))

    with _llm_cache_lock:
        if config_hash in _llm_cache:
            return _llm_cache[config_hash]

    # Build outside the lock to avoid holding it during network calls
    if provider_type and model_id:
        from src.copilot.llm_factory import create_llm_from_provider
        llm = create_llm_from_provider(
            provider_type=provider_type,
            model_id=model_id,
            api_key=api_key,
            base_url=base_url,
            provider_config=provider_config or {},
            temperature=temperature or config.DEFAULT_LLM_TEMPERATURE,
        )
        logger.info(f"Created LLM: {provider_type}/{model_id}")
    else:
        from src.copilot.llm_factory import get_default_llm
        llm = get_default_llm(
            temperature=temperature or config.DEFAULT_LLM_TEMPERATURE
        )
        logger.info("Using default Ollama LLM")

    with _llm_cache_lock:
        if len(_llm_cache) >= _LLM_CACHE_MAX_SIZE:
            oldest_key = next(iter(_llm_cache))
            del _llm_cache[oldest_key]
        _llm_cache[config_hash] = llm

    return llm


def get_configured_llm(state: Optional[Dict[str, Any]] = None) -> BaseChatModel:
    """Get the LLM for the current request from state, or fall back to default.

    Args:
        state: Agent state containing llm_config dict.

    Returns:
        An LLM instance.
    """
    if state and state.get("llm_config"):
        cfg = state["llm_config"]
        return create_llm_for_request(
            provider_type=cfg.get("provider_type"),
            model_id=cfg.get("model_id"),
            api_key=cfg.get("api_key"),
            base_url=cfg.get("base_url"),
            provider_config=cfg.get("provider_config"),
            temperature=cfg.get("temperature"),
        )
    from src.copilot.llm_factory import get_default_llm
    return get_default_llm()


GUARDRAIL_REJECTION_MESSAGE = (
    "I cannot help with that, maybe I can help you with a query regarding incidents"
)

GUARDRAIL_SYSTEM_PROMPT = """You are a safety classifier. Your ONLY job \
is to check whether the user's latest message is asking about any of these \
deny topics — directly, or through aliases, synonyms, related entities, \
adjacent concepts, or indirect references.

Deny topics:
{deny_words}

You will be given a recent conversation (may be empty) and the latest user \
message. Resolve follow-up references ("that", "it", "more about this") \
using the conversation before deciding.

Respond with ONLY JSON (no markdown, no prose):
{{"allow": true|false, "reason": "<one short sentence>"}}

Rules:
- If the latest message is asking about a deny topic in any form, \
return allow: false.
- Otherwise, return allow: true.
- When in doubt whether a message relates to a deny topic, return allow: true. \
Only block when the connection to a deny topic is clear.
"""

_guardrail_cache: "OrderedDict[str, bool]" = OrderedDict()
_guardrail_cache_lock = threading.Lock()
_GUARDRAIL_CACHE_MAX = 200

def _guardrail_cache_key(settings_id: str, prior_last_human: str, query: str) -> str:
    """Build a cache key that is history-aware but dedupes identical repeats.

    Keyed on `(settings_id, last prior human message, normalized current query)`
    so any settings change (deny list / use-case edit) naturally invalidates
    cached verdicts.
    """
    normalized = (query or "").strip().lower()[:500]
    prior_hash = hashlib.sha256((prior_last_human or "").encode()).hexdigest()[:16]
    raw = f"{settings_id}|{prior_hash}|{normalized}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _guardrail_cache_get(key: str) -> Optional[bool]:
    with _guardrail_cache_lock:
        if key in _guardrail_cache:
            _guardrail_cache.move_to_end(key)
            return _guardrail_cache[key]
    return None


def _guardrail_cache_set(key: str, allow: bool) -> None:
    with _guardrail_cache_lock:
        _guardrail_cache[key] = allow
        _guardrail_cache.move_to_end(key)
        while len(_guardrail_cache) > _GUARDRAIL_CACHE_MAX:
            _guardrail_cache.popitem(last=False)


def _build_guardrail_history(
    messages: Sequence[BaseMessage],
    history_turns: int,
) -> Tuple[str, str, str]:
    """Split the message list into (history_block, current_query, last_prior_human).

    - `history_block`: formatted transcript of the last N prior turns (role: text).
    - `current_query`: the latest human message that triggered this graph run.
    - `last_prior_human`: the most recent human message before the current one
      (used in the cache key for history-sensitive dedup).
    """
    if not messages:
        return "(no prior conversation)", "", ""

    current_query = _extract_text_content(getattr(messages[-1], "content", ""))

    max_prior = max(0, int(history_turns)) * 2
    prior = list(messages[:-1])[-max_prior:] if max_prior else []

    lines: List[str] = []
    last_prior_human = ""
    for m in prior:
        role = getattr(m, "type", "") or ""
        text = _extract_text_content(getattr(m, "content", ""))
        if not text:
            continue
        if role == "human":
            lines.append(f"user: {text[:500]}")
            last_prior_human = text
        elif role == "ai":
            lines.append(f"assistant: {text[:500]}")
        else:
            continue

    history_block = "\n".join(lines) if lines else "(no prior conversation)"
    return history_block, current_query, last_prior_human


def _parse_guardrail_decision(raw: str) -> Optional[bool]:
    """Parse the classifier's JSON response into an allow/deny bool.

    Returns None if the response cannot be parsed, so the caller can fail open.
    """
    if not raw:
        return None
    content = raw.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        content = content.rsplit("```", 1)[0]
    content = content.strip()
    try:
        decision = json.loads(content)
    except json.JSONDecodeError:
        logger.warning(f"Guardrail: could not parse JSON from classifier response: {raw!r}")
        return None
    allow = decision.get("allow")
    if isinstance(allow, bool):
        return allow
    return None


def guardrail_check(state: AgentState) -> dict:
    """Pluggable LLM guardrail gate at the entry of the graph.

    Reads `state['guardrail_config']`. When disabled or misconfigured, passes
    through transparently. When the classifier denies the query, appends an
    AIMessage with the refusal text — the conditional edge then routes to END.

    Fails OPEN on classifier errors (L1 regex already ran upstream).
    """
    writer = get_stream_writer()
    logger.debug("NODE: GUARDRAIL")

    gconfig = (state or {}).get("guardrail_config") or {}
    if not gconfig.get("enabled") or not gconfig.get("provider_type") or not gconfig.get("model_id"):
        return {}

    messages = state.get("messages") or []
    if not messages:
        return {}

    history_turns = gconfig.get("history_turns", 3)
    history_block, current_query, last_prior_human = _build_guardrail_history(messages, history_turns)

    if not current_query:
        return {}

    settings_id = str(gconfig.get("settings_id", ""))
    guardrail_model_id = gconfig.get("model_id")
    guardrail_provider_type = gconfig.get("provider_type")

    def _blocked_response() -> dict:
        writer({"status": "Request blocked by guardrail"})
        writer({
            "guardrail_refusal": GUARDRAIL_REJECTION_MESSAGE,
            "model_id": guardrail_model_id,
            "provider_type": guardrail_provider_type,
        })
        writer({"status": "Almost done, wrapping up the details"})
        return {
            "messages": [AIMessage(
                content=GUARDRAIL_REJECTION_MESSAGE,
                additional_kwargs={
                    "blocked_by_guardrail": True,
                    "guardrail_model_id": guardrail_model_id,
                    "guardrail_provider_type": guardrail_provider_type,
                },
            )]
        }

    cache_key = _guardrail_cache_key(settings_id, last_prior_human, current_query)
    cached = _guardrail_cache_get(cache_key)
    if cached is True:
        logger.info("Guardrail cache hit: allow")
        return {}
    if cached is False:
        logger.info("Guardrail cache hit: deny")
        return _blocked_response()

    try:
        writer({"status": "Understanding your question..."})
        from src.copilot.llm_factory import create_llm_from_provider

        classifier = create_llm_from_provider(
            provider_type=gconfig["provider_type"],
            model_id=gconfig["model_id"],
            api_key=gconfig.get("api_key"),
            base_url=gconfig.get("base_url"),
            provider_config=gconfig.get("provider_config") or {},
            temperature=0.0,
        )

        system_prompt = GUARDRAIL_SYSTEM_PROMPT.format(
            deny_words=gconfig.get("deny_words") or "(none configured)",
        )
        user_payload = (
            f"Recent conversation:\n{history_block}\n\n"
            f"Latest user message: {current_query}\n\n"
            "Classify and respond with JSON only."
        )

        response = classifier.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_payload),
            ],
            config={"run_name": "Guardrail Classifier"},
        )
        raw = _extract_text_content(getattr(response, "content", ""))
        decision = _parse_guardrail_decision(raw)
    except Exception as e:
        logger.error(f"Guardrail LLM call failed, failing open: {e}")
        return {}

    if decision is None:
        logger.warning("Guardrail returned unparseable decision, failing open")
        return {}

    _guardrail_cache_set(cache_key, decision)

    if decision is False:
        logger.info(f"Guardrail: DENIED query '{current_query[:80]}'")
        return _blocked_response()

    logger.debug("Guardrail: allowed")
    return {}


def _guardrail_decision(state: AgentState) -> str:
    """Conditional edge out of guardrail_check.

    If the latest message is an AI refusal (added by guardrail_check), route to END.
    Otherwise, continue to the main support bot node.
    """
    messages = state.get("messages") or []
    if not messages:
        return "allow"
    last = messages[-1]
    if isinstance(last, AIMessage) and _extract_text_content(getattr(last, "content", "")) == GUARDRAIL_REJECTION_MESSAGE:
        return "reject"
    return "allow"


SYSTEM_MESSAGE_PROMPT_TEMPLATE = """
    You are an expert incident resolution assistant with perfect memory of this conversation.
    Today's date is {current_date}. The user's local timezone is {local_timezone}. Use this to calculate date ranges for user queries.
    When displaying dates/times to the user, convert from UTC to {local_timezone} unless the user asks for UTC.

    Your primary goal is to answer user questions about incidents. Follow this logic:

    1. **Verified Knowledge (Highest Priority):**
       - If a "Verified Knowledge" section is provided below with a "Direct Answer Available",
         you MAY use that verified response directly WITHOUT calling tools
       - This applies ONLY when the user's question is asking for the SAME information
       - Just respond naturally - do NOT add any special prefix
       - If the question differs or needs additional details, use tools as normal

    2. **When to Use Memory vs Tools:**
       - Use memory ONLY for follow-up questions about incidents where a tool has ALREADY
         returned data in a previous turn
       - ALWAYS use a tool when encountering a NEW incident ID or new search topic
       - If unsure whether you have the data, USE THE TOOL

    3. **Select the Right Tool:**
       - `lookup_incident_by_id`: When user mentions a specific ID (e.g., INC-2025-08-24-001)
       - `search_similar_incidents`: When user describes a problem/error without an ID
       - `get_incidents_by_application`: When asking about a specific app/system
       - `get_recent_incidents`: When asking about recent incidents or timeframes (last N days)
       - `get_incident_statistics`: When user asks for counts, reports, trends, or grouped data
         Examples: "monthly report", "how many incidents today", "incidents grouped by month",
         "incidents by application this year"
       - `get_recurring_incidents`: When user asks about repeated/recurring/frequent incidents
         Examples: "most common incidents", "what keeps happening", "top recurring issues"

    **Date Handling for tools:**
       - "today" → start_date = {current_date}, end_date = day after {current_date}
       - "yesterday" → calculate the previous day from {current_date}
       - "last 6 months" → start_date = 6 months before {current_date}
       - "last 2 years" → start_date = 2 years before {current_date}
       - Always pass dates as YYYY-MM-DD to tools

    4. **Query Rewriting for Tools:**
       Before calling any tool, you MUST rewrite the user's conversational query into a
       search-optimized format. Extract the core search intent and remove conversational fluff.

       Examples:
       - "hey how to solve the issue with loan emi?" → query: "Loan EMI issue"
       - "can you tell me about payment gateway errors?" → query: "payment gateway errors"
       - "what happened with the Swift transfer delays last week?" → query: "Swift transfer delays"
       - "I need help with HTTP 403 forbidden errors in PayU" → query: "HTTP 403 forbidden PayU"
       - "tell me about this issue INC-2025-08-24-001" → incident_id: "INC-2025-08-24-001"

       Always pass CLEAN, CONCISE search terms to tools - never raw conversational text.

    5. **Tool Usage Rules:**
       * Base answers on retrieved context from tools OR verified knowledge
       * When using tool data, ALWAYS cite the source incident ID (e.g., "Based on incident INC-2025-08-24-001...")
       * If no relevant info found, state this clearly
       * You may call multiple tools if needed

    6. Do not make up information. Be concise and factual. Never use code fences to encapsulate responses.

    7. **(Only follow when you need to generate a table based on tool data to answer the user's question)Table Formatting Rules:**
        * NEVER generate tables with more than 4 columns
        * If data requires more columns, split into multiple smaller tables
        * Prioritize the most important columns (ID, Title, Status, Action)
    """


def call_model(state: AgentState) -> dict:
    """Node to call the LLM with the current state.

    This function:
    1. Searches for similar golden examples based on the user's query
    2. Enhances the system prompt with relevant examples
    3. Invokes the LLM with the enhanced prompt

    Args:
        state: Current agent state with messages

    Returns:
        Dictionary with new messages to add to state
    """
    logger.debug("NODE: CALLING MODEL")

    # Get the per-request LLM with tools
    model_with_tools = _get_model_with_tools(state)

    user_messages = [m for m in state["messages"] if hasattr(m, 'type') and m.type == 'human']
    latest_query = _extract_text_content(user_messages[-1].content) if user_messages else ""

    # Inject current date and timezone into system prompt
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    utc_offset_seconds = now.astimezone().utcoffset().total_seconds()
    utc_offset_hours = int(utc_offset_seconds // 3600)
    utc_offset_minutes = int((utc_offset_seconds % 3600) // 60)
    local_timezone = now.astimezone().tzname() or f"UTC{utc_offset_hours:+d}:{utc_offset_minutes:02d}"
    base_prompt_content = SYSTEM_MESSAGE_PROMPT_TEMPLATE.format(
        current_date=current_date,
        local_timezone=local_timezone,
    )
    enhanced_system_prompt = SystemMessage(base_prompt_content)

    if latest_query:
        try:
            golden_examples = search_golden_examples_sync(
                query=latest_query,
                top_k=2,
                score_threshold=0.6,
            )
            if golden_examples:
                logger.debug(f"Found {len(golden_examples)} golden examples for query")
                enhanced_content = build_prompt_with_golden_examples(
                    base_prompt=base_prompt_content,
                    golden_examples=golden_examples,
                )
                enhanced_system_prompt = SystemMessage(enhanced_content)
        except Exception as e:
            logger.warning(f"Error searching golden examples: {e}")
    messages = [enhanced_system_prompt] + list(state["messages"])

    response = model_with_tools.invoke(
        messages,
        config={"run_name": "Support Bot LLM"},
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
    return _qdrant_tool_node.invoke(
        state,
        config={"run_name": "Incident Report Qdrant Tool"},
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

    # Get per-request LLM from state
    llm = get_configured_llm(state)

    chat_text = "\n".join(
        f"{m.type.upper()}: {_extract_text_content(getattr(m, 'content', ''))[:500]}"
        for m in state["messages"]
        if getattr(m, 'type', '') in ('human', 'ai')
    )

    system = SystemMessage(
        "Generate a concise, 2-4 word title for the conversation. "
        "Prioritize accuracy over excessive creativity; keep it clear and simple. "
        "The output must be only the title, without any quotes, markdown code fences or other encapsulating text."
    )
    human = HumanMessage(
        f"Here is the conversation transcript:\n{chat_text}\n\n"
        "Generate a short title."
    )

    response = llm.invoke(
        [system, human],
        config={"run_name": "Title Generator LLM"},
    )

    title_text = _extract_text_content(response.content)
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
    llm_config: Optional[Dict[str, Any]] = None,
    langfuse_config: Optional[Dict[str, str]] = None,
    langfuse_trace_context: Optional[Dict[str, str]] = None,
    callbacks: Optional[list] = None,
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
        llm_config: Optional LLM config for per-request model selection
        langfuse_config: Optional Langfuse credentials dict
        langfuse_trace_context: Optional trace context to nest under the parent trace
        callbacks: Optional list of pre-created callback handlers to reuse

    Returns:
        Generated title string
    """
    logger.debug("PARALLEL TITLE GENERATION: Starting")

    llm = get_configured_llm({"llm_config": llm_config} if llm_config else None)

    system = SystemMessage(
        "Generate a concise, 2-4 word title for the user's query. "
        "Prioritize accuracy over excessive creativity; keep it clear and simple. "
        "The output must be only the title, without any quotes, markdown code fences or other encapsulating text."
    )
    human = HumanMessage(f"{query}")

    if callbacks is None:
        callbacks = []
        if langfuse_enabled:
            callbacks = [create_langfuse_callback(langfuse_config, trace_context=langfuse_trace_context)]
    title_chain = RunnableLambda(lambda _: llm.invoke([system, human])).with_config(
        {"run_name": "Parallel Title Generator"}
    )

    with propagate_attributes(session_id=session_id, user_id=user_id):
        response = title_chain.invoke(
            None,
            config={"callbacks": callbacks},
        )

    title_text = _extract_text_content(response.content)
    if not title_text:
        title_text = "Untitled Chat"

    logger.debug(f"PARALLEL TITLE GENERATION: Generated '{title_text}'")
    return title_text

_checkpointer_conn: Optional[Connection] = None


def _cleanup_checkpointer_conn():
    """Close the checkpointer connection on process exit."""
    global _checkpointer_conn
    if _checkpointer_conn is not None:
        try:
            _checkpointer_conn.close()
            logger.info("Checkpointer PostgreSQL connection closed.")
        except Exception:
            pass
        _checkpointer_conn = None


atexit.register(_cleanup_checkpointer_conn)


def create_agent_graph():
    """Create and compile the agent graph with PostgreSQL checkpointing.

    Returns:
        Compiled LangGraph workflow ready for invocation

    Note:
        The connection is stored at module level and cleaned up via atexit.
    """
    global _checkpointer_conn
    if _checkpointer_conn is not None:
        try:
            _checkpointer_conn.close()
        except Exception:
            pass

    _checkpointer_conn = Connection.connect(config.VECTOR_DATABASE_URL, **_connection_kwargs)
    checkpointer = PostgresSaver(_checkpointer_conn)
    checkpointer.setup()

    workflow = StateGraph(AgentState)

    workflow.add_node("guardrail_check", guardrail_check)
    workflow.add_node("support_bot", call_model)
    workflow.add_node("incident_tools", tool_wrapper)
    workflow.add_node("title_generation", title_generation_node)

    workflow.set_entry_point("guardrail_check")

    workflow.add_conditional_edges(
        "guardrail_check",
        _guardrail_decision,
        {"allow": "support_bot", "reject": END},
    )

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
