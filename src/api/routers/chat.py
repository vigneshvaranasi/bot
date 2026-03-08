import asyncio
import json
import logging
import time
from datetime import datetime, timezone

def _utcnow_naive() -> datetime:
    """Return current UTC time as a timezone-naive datetime (for TIMESTAMP WITHOUT TIME ZONE columns)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessageChunk
from langfuse import propagate_attributes
from sqlalchemy import asc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.cache import check_cache_for_query, store_chat_response
from src.api.auth.dependencies import get_current_user
from src.api.db.models import Chat, Message, Setting
from src.api.db.session import get_session
from src.api.schemas.chat_schema import (
    ChatListItem,
    ChatRenameRequest,
    MessagePartialUpdate,
    PromptModel,
)
from src.api.utils.llm_provider_helper import (
    get_provider_config_for_chat,
    get_provider_config_for_model,
)
from src.api.utils.tracing import conditional_observation, resolve_langfuse_config
from src.copilot.graph import create_agent_graph, generate_title_from_query
from src.copilot.guardrails.prompt_guardrails import PromptGuardrail
from src.copilot.utils import should_ask_clarification

logger = logging.getLogger(__name__)


def _message_content_to_str(content: Any) -> str:
    """Normalize AIMessageChunk content to string for streaming.

    OpenAI/Gemini return content as str; Anthropic returns a list of content blocks.
    Only user-visible 'text' is included; 'thinking' (internal reasoning) is excluded.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
            elif hasattr(block, "text"):
                parts.append(getattr(block, "text", "") or "")
            else:
                parts.append(str(block) if block is not None else "")
        return "".join(parts)
    return str(content)


router = APIRouter()

# / -> Get All Chats of the User (paginated)
@router.get("/")
@router.get("")
async def get_user_chats(
    limit: int = 20,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get paginated chats for the authenticated user with only id, title, and updated_at."""
    try:
        user_id = current_user["user_id"]

        # Get total count
        count_result = await session.execute(
            select(func.count(Chat.id))
            .where(Chat.user_id == user_id)
            .where(Chat.archived_at == None)
        )
        total = count_result.scalar() or 0

        # Get paginated chats
        result = await session.execute(
            select(Chat.id, Chat.title, Chat.updated_at)
            .where(Chat.user_id == user_id)
            .where(Chat.archived_at == None)
            .order_by(Chat.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        chats_data = result.all()
        chat_items = [
            ChatListItem(id=str(chat.id), title=chat.title, updated_at=chat.updated_at)
            for chat in chats_data
        ]

        return {
            "error": False,
            "chats": chat_items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(chat_items) < total,
        }

    except Exception as e:
        logger.debug(f"Error retrieving user chats: {e}")
        return {
            "error": True,
            "message": f"Could not retrieve chats: {e}",
        }


# Lazy-initialized graph (avoids database connection at import time)
_support_bot_graph = None


def get_support_bot_graph():
    """Get or create the support bot graph with lazy initialization."""
    global _support_bot_graph
    if _support_bot_graph is None:
        _support_bot_graph = create_agent_graph()
    return _support_bot_graph


async def async_stream_wrapper(sync_iterator):
    """Convert a sync iterator to an async iterator by running in thread pool.

    This prevents blocking the event loop when iterating over sync generators.
    """
    import queue
    import threading

    q = queue.Queue()
    sentinel = object()

    def producer():
        try:
            for item in sync_iterator:
                q.put(item)
        except Exception as e:
            q.put(e)
        finally:
            q.put(sentinel)

    thread = threading.Thread(target=producer, daemon=True)
    thread.start()

    while True:
        item = await asyncio.to_thread(q.get)
        if item is sentinel:
            break
        if isinstance(item, Exception):
            raise item
        yield item


async def validate_prompt(prompt: str, session: AsyncSession):
    """Validate the prompt using the provided guardrail."""
    try:
        result = await session.execute(
            select(Setting).order_by(Setting.updated_at.desc())
        )
        settings = result.scalars().first()
        guard = PromptGuardrail(deny_words=settings.deny_words if settings else "")
        is_valid, reject_msg = guard.validate_or_reject(prompt=prompt)
        return is_valid, reject_msg, settings
    except Exception as e:
        raise ValueError(f"An error occurred while validating the prompt: {e}")


async def get_or_create_chat(
    chat_id: str | None, user_id: str, session: AsyncSession
) -> tuple[str, dict]:
    """
    Get existing chat or create new chat for the user.

    Returns:
        tuple: (actual_chat_id, thread_config)

    Raises:
        ValueError: If chat is not found or cannot be created
    """
    if chat_id is not None and str(chat_id).strip():
        # Verify if Chat exists and user has access
        result = await session.execute(
            select(Chat).where(
                Chat.id == chat_id, Chat.user_id == user_id, Chat.archived_at.is_(None)
            )
        )
        existing_chat = result.scalar_one_or_none()
        if not existing_chat:
            raise ValueError("Chat not found.")
        thread_config = {"configurable": {"thread_id": str(chat_id)}, "recursion_limit": 10}
        actual_chat_id = chat_id
    else:
        # create new chat
        try:
            new_chat = Chat(user_id=user_id, title="New Chat")
            session.add(new_chat)
            await session.commit()
            await session.refresh(new_chat)
            actual_chat_id = new_chat.id
            thread_config = {"configurable": {"thread_id": str(new_chat.id)}, "recursion_limit": 10}
        except Exception as e:
            await session.rollback()
            raise ValueError(f"An error occurred while creating a new chat: {e}")

    return str(actual_chat_id), thread_config


@router.post("/prompt/stream")
async def prompt_stream(
    request: PromptModel,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Post a new prompt and get response"""
    human_message = request.message
    chat_id = request.chat_id
    user_id = current_user["user_id"]
    if not human_message or not human_message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    try:
        is_valid, reject_msg, settings = await validate_prompt(human_message, session)
        if not is_valid:
            return {
                "success": False,
                "message": reject_msg,
            }
        actual_chat_id, thread_config = await get_or_create_chat(
            chat_id, user_id, session
        )
        
        # Check if there's conversation history in this chat
        has_conversation_history = False
        if chat_id is not None and str(chat_id).strip():
            # Check if there are existing messages in this chat
            message_count_result = await session.execute(
                select(func.count(Message.id)).where(Message.chat_id == actual_chat_id)
            )
            message_count = message_count_result.scalar()
            has_conversation_history = message_count > 0
            logger.debug(f"[CONVERSATION CHECK] Chat {actual_chat_id} has {message_count} messages")
        
        # Check if we should ask for clarification on context-dependent queries
        should_clarify, clarification_message = should_ask_clarification(human_message, has_conversation_history)
        if should_clarify:
            logger.debug(f"[CLARIFICATION NEEDED] Query requires clarification: '{human_message[:50]}...'")
            return {
                "success": False,
                "message": clarification_message,
                "needs_clarification": True
            }

        # Fetch current title for the chat
        result = await session.execute(
            select(Chat.title).where(Chat.id == actual_chat_id)
        )
        current_title = result.scalar_one_or_none()
        
        langfuse_enabled = settings.langfuse_enabled if settings else False
        langfuse_config = resolve_langfuse_config(settings)

        # Fetch and configure LLM provider (per-prompt override or default)
        if request.provider_id and request.model_id:
            provider_config = await get_provider_config_for_model(
                session, request.provider_id, request.model_id
            )
        else:
            provider_config = await get_provider_config_for_chat(session, str(user_id))
        llm_config = {
            "provider_type": provider_config.get("provider_type"),
            "model_id": provider_config.get("model_id"),
            "api_key": provider_config.get("api_key"),
            "base_url": provider_config.get("base_url"),
            "provider_config": provider_config.get("provider_config", {}),
            "temperature": provider_config.get("temperature"),
        }

        needs_title = (
            request.generate_title
            and (not current_title or current_title.strip() in ("", "New Chat"))
        )

        inputs = {
            "messages": [("user", human_message)],
            "session_id": actual_chat_id,
            "user_id": str(user_id),
            "langfuse_enabled": langfuse_enabled,
            "langfuse_config": langfuse_config,
            "generate_title": not needs_title,
            "llm_config": llm_config,
        }

        pre_saved_message = Message(
            chat_id=actual_chat_id, human=human_message, bot=""
        )
        session.add(pre_saved_message)
        await session.commit()
        await session.refresh(pre_saved_message)
        cached_response = check_cache_for_query(human_message)

        async def stream_generator():
            title_queue = asyncio.Queue()
            title_task = None
            title_sent = False

            async def parallel_title_generator():
                """Generate title in parallel with main response."""
                try:
                    logger.debug("[PARALLEL TITLE] Starting parallel title generation")
                    title = await asyncio.to_thread(
                        generate_title_from_query,
                        human_message,
                        str(actual_chat_id),
                        str(user_id),
                        langfuse_enabled,
                        llm_config,
                        langfuse_config,
                    )
                    await title_queue.put({"title": title})
                    logger.debug(f"[PARALLEL TITLE] Generated: {title}")
                except Exception as e:
                    logger.debug(f"[PARALLEL TITLE] Error: {e}")
                    await title_queue.put({"error": str(e)})

            async def check_and_emit_title():
                """Check if title is ready and emit event (non-blocking)."""
                nonlocal title_sent
                if title_sent:
                    return None
                try:
                    result = title_queue.get_nowait()
                    if "title" in result:
                        title_sent = True
                        return result["title"]
                except asyncio.QueueEmpty:
                    pass
                return None

            async def save_title_to_db(title_text):
                """Save generated title to database."""
                try:
                    result = await session.execute(
                        select(Chat).where(Chat.id == actual_chat_id, Chat.user_id == user_id)
                    )
                    chat_row = result.scalar_one_or_none()
                    if chat_row and (not chat_row.title or chat_row.title.strip() in ("", "New Chat")):
                        chat_row.title = title_text
                        await session.commit()
                        logger.debug(f"[TITLE DB] Saved title: {title_text}")
                except Exception as e:
                    await session.rollback()
                    logger.debug(f"[TITLE DB] Error saving title: {e}")

            yield f"event: chat_init\ndata: {json.dumps({'chat_id': str(actual_chat_id), 'message_id': str(pre_saved_message.id)})}\n\n"

            if cached_response:
                logger.debug(f"[CACHE HIT] Found cached response, streaming from cache")

                if needs_title:
                    title_task = asyncio.create_task(parallel_title_generator())

                # Update pre-saved message with cached response
                try:
                    # Re-fetch the message to ensure we have a fresh object attached to the session
                    msg_result = await session.execute(
                        select(Message).where(Message.id == pre_saved_message.id)
                    )
                    msg_to_update = msg_result.scalar_one_or_none()
                    if msg_to_update:
                        msg_to_update.bot = cached_response
                        msg_to_update.responded_at = _utcnow_naive()
                        msg_to_update.model_id = llm_config.get("model_id") or "default"
                        msg_to_update.provider_type = llm_config.get("provider_type") or "ollama"
                        await session.commit()
                except Exception as e:
                    await session.rollback()
                    logger.debug(f"Error updating message with cached response: {e}")

                yield f"event: status\ndata: {json.dumps({'message': 'Found cached response, delivering instantly...'})}\n\n"

                # Stream the cached answer - send content chunks preserving markdown
                logger.debug(f"[CACHE STREAM] Streaming cached response with markdown formatting")
                # Split by characters to preserve newlines and markdown formatting
                chunk_size = 5  # Send 5 characters at a time for smooth streaming
                for i in range(0, len(cached_response), chunk_size):
                    chunk_text = cached_response[i:i + chunk_size]
                    chunk_payload = {"chunk": chunk_text}
                    yield f"event: final_answer\ndata: {json.dumps(chunk_payload)}\n\n"

                    # Check for title ready (non-blocking) during streaming
                    title_result = await check_and_emit_title()
                    if title_result:
                        yield f"event: title\ndata: {json.dumps({'title': title_result})}\n\n"
                        await save_title_to_db(title_result)

                    await asyncio.sleep(0.01)

                if needs_title and not title_sent and title_task:
                    try:
                        result = await asyncio.wait_for(title_queue.get(), timeout=10.0)
                        if "title" in result:
                            yield f"event: title\ndata: {json.dumps({'title': result['title']})}\n\n"
                            await save_title_to_db(result["title"])
                    except asyncio.TimeoutError:
                        logger.debug("[PARALLEL TITLE] Timeout waiting for title")

                # Send completion event with full answer
                final_data = {
                    "answer": cached_response,
                    "chat_id": str(actual_chat_id),
                    "message_id": str(pre_saved_message.id),
                    "time_to_first_token_ms": None,
                    "total_response_time_ms": None,
                    "model_id": llm_config.get("model_id") or "default",
                    "provider_type": llm_config.get("provider_type") or "ollama",
                }
                yield f"event: complete\ndata: {json.dumps(final_data)}\n\n"
                logger.debug(f"[CACHE STREAM] Stream completed successfully")
                return

            logger.debug(f"[CACHE MISS] No cached response found, processing with LangGraph")

            if needs_title:
                title_task = asyncio.create_task(parallel_title_generator())
                logger.debug("[PARALLEL TITLE] Task started")

            answer = ""
            memory_saved = False
            generated_title = current_title
            t_start: float | None = None
            t_first: float | None = None

            workflow_observation = conditional_observation(
                enabled=langfuse_enabled,
                langfuse_config=langfuse_config,
                as_type="agent",
                name="copilot-chat",
                input=human_message,
                metadata={"type": "streaming", "chat_id": str(actual_chat_id)}
            )
            try:
                with workflow_observation as observation:
                    with propagate_attributes(
                        session_id=str(actual_chat_id),
                        user_id=str(user_id)
                    ):
                        # Streaming mode - wrap sync iterator to avoid blocking event loop
                        sync_stream = get_support_bot_graph().stream(
                            config=thread_config, input=inputs, stream_mode=["custom", "messages"]
                        )
                        t_start = time.perf_counter()
                        async for mode, chunk in async_stream_wrapper(sync_stream):
                            
                            title_result = await check_and_emit_title()
                            if title_result:
                                generated_title = title_result
                                yield f"event: title\ndata: {json.dumps({'title': title_result})}\n\n"
                                await save_title_to_db(title_result)

                            if mode == "custom":
                                if isinstance(chunk, dict) and "title" in chunk and not title_sent:
                                    generated_title = chunk["title"]
                                    title_sent = True
                                    yield f"event: title\ndata: {json.dumps({'title': generated_title})}\n\n"
                                    await save_title_to_db(generated_title)

                                # Status event
                                if isinstance(chunk, dict) and "status" in chunk:
                                    status_payload = {"message": chunk["status"]}
                                    yield f"event: status\ndata: {json.dumps(status_payload)}\n\n"

                                    if (
                                        "Almost done, wrapping up the details" in chunk["status"]
                                        and not memory_saved
                                    ):
                                        # Wait for title if not yet received (with timeout)
                                        if needs_title and not title_sent and title_task:
                                            try:
                                                result = await asyncio.wait_for(title_queue.get(), timeout=5.0)
                                                if "title" in result:
                                                    generated_title = result["title"]
                                                    title_sent = True
                                                    yield f"event: title\ndata: {json.dumps({'title': generated_title})}\n\n"
                                                    await save_title_to_db(generated_title)
                                            except asyncio.TimeoutError:
                                                logger.debug("[PARALLEL TITLE] Timeout at completion")

                                        # Store response in cache for future use
                                        try:
                                            logger.debug(f"[CACHE STORE] Storing response in cache for query: '{human_message[:50]}...'")
                                            store_chat_response(human_message, answer)
                                            logger.debug(f"[CACHE STORE] Successfully cached response")
                                        except Exception as e:
                                            logger.debug(f"[CACHE ERROR] Error storing response in cache: {e}")

                                        # Update the pre-saved message with the full answer and metrics
                                        t_end = time.perf_counter()
                                        time_to_first_token_ms = (
                                            round((t_first - t_start) * 1000) if t_start is not None and t_first is not None else None
                                        )
                                        total_response_time_ms = (
                                            round((t_end - t_start) * 1000) if t_start is not None else None
                                        )
                                        try:
                                            msg_result = await session.execute(
                                                select(Message).where(Message.id == pre_saved_message.id)
                                            )
                                            msg_to_update = msg_result.scalar_one_or_none()
                                            if msg_to_update:
                                                msg_to_update.bot = answer
                                                msg_to_update.responded_at = _utcnow_naive()
                                                msg_to_update.time_to_first_token_ms = time_to_first_token_ms
                                                msg_to_update.total_response_time_ms = total_response_time_ms
                                                msg_to_update.model_id = llm_config.get("model_id") or "default"
                                                msg_to_update.provider_type = llm_config.get("provider_type") or "ollama"
                                                await session.commit()
                                                memory_saved = True
                                        except Exception as e:
                                            logger.error(f"[METRICS SAVE] Failed to save message metrics: {e}", exc_info=True)
                                            await session.rollback()

                                        final_data = {
                                            "answer": answer,
                                            "chat_id": str(actual_chat_id),
                                            "message_id": str(pre_saved_message.id),
                                            "time_to_first_token_ms": time_to_first_token_ms,
                                            "total_response_time_ms": total_response_time_ms,
                                            "model_id": llm_config.get("model_id") or "default",
                                            "provider_type": llm_config.get("provider_type") or "ollama",
                                        }
                                        yield f"event: complete\ndata: {json.dumps(final_data)}\n\n"

                            elif mode == "messages":
                                token_chunk, metadata = chunk
                                if (
                                    metadata.get('langgraph_node') != 'incident_tools'
                                    and isinstance(token_chunk, AIMessageChunk)
                                    and token_chunk.content
                                ):
                                    if t_first is None:
                                        t_first = time.perf_counter()
                                    chunk_text = _message_content_to_str(token_chunk.content)
                                    answer += chunk_text
                                    chunk_payload = {"chunk": chunk_text}
                                    yield f"event: final_answer\ndata: {json.dumps(chunk_payload)}\n\n"

                        observation.update(output=answer, name=generated_title)
            except Exception as e:
                logger.error(f"Error during streaming response: {e}", exc_info=True)
                # Cancel title task if still running
                if title_task and not title_task.done():
                    title_task.cancel()
                # Send error event so the frontend stops the loading state
                error_payload = {"message": "An error occurred while generating the response. Please try again."}
                yield f"event: error\ndata: {json.dumps(error_payload)}\n\n"
                # Also send a complete event so frontend can finalize
                t_end_err = time.perf_counter() if t_start is not None else None
                time_to_first_token_ms_err = (
                    round((t_first - t_start) * 1000) if t_start is not None and t_first is not None else None
                )
                total_response_time_ms_err = (
                    round((t_end_err - t_start) * 1000) if t_start is not None and t_end_err is not None else None
                )
                final_data = {
                    "answer": answer or "",
                    "chat_id": str(actual_chat_id),
                    "message_id": str(pre_saved_message.id),
                    "time_to_first_token_ms": time_to_first_token_ms_err,
                    "total_response_time_ms": total_response_time_ms_err,
                    "model_id": llm_config.get("model_id") or "default",
                    "provider_type": llm_config.get("provider_type") or "ollama",
                }
                yield f"event: complete\ndata: {json.dumps(final_data)}\n\n"
            finally:
                # Ensure title task is cleaned up
                if title_task and not title_task.done():
                    title_task.cancel()
                # Update pre-saved message with partial answer on disconnect
                logger.debug(f"[STREAM FINALLY] memory_saved={memory_saved}, answer_len={len(answer) if answer else 0}")
                if not memory_saved and answer:
                    try:
                        t_end_finally = time.perf_counter()
                        msg_result = await session.execute(
                            select(Message).where(Message.id == pre_saved_message.id)
                        )
                        msg_to_update = msg_result.scalar_one_or_none()
                        if msg_to_update:
                            msg_to_update.bot = answer
                            msg_to_update.responded_at = _utcnow_naive()
                            msg_to_update.time_to_first_token_ms = (
                                round((t_first - t_start) * 1000) if t_start is not None and t_first is not None else None
                            )
                            msg_to_update.total_response_time_ms = (
                                round((t_end_finally - t_start) * 1000) if t_start is not None else None
                            )
                            msg_to_update.model_id = llm_config.get("model_id") or "default"
                            msg_to_update.provider_type = llm_config.get("provider_type") or "ollama"
                            await session.commit()
                    except Exception as save_err:
                        logger.error(f"[STREAM FINALLY] Failed to save message in finally: {save_err}", exc_info=True)
                        await session.rollback()

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    except Exception as e:
        await session.rollback()
        logger.exception("Error occurred while processing prompt")
        return {
            "success": False,
            "message": "An error occurred while processing the prompt",
        }


async def get_graph_response_non_stream(inputs, config, graph=None):
    """Helper function to get non-streaming response from the support bot graph."""
    try:
        if graph is None:
            graph = get_support_bot_graph()
        # Run blocking graph invoke in thread pool to avoid blocking event loop
        result = await asyncio.to_thread(graph.invoke, inputs, config=config)
        final_message = result["messages"][-1]
        answer = str(final_message.content)
        title = result.get("title") if isinstance(result, dict) else None
        return answer, title
    except Exception as e:
        logger.exception("Error in get_graph_response_non_stream")
        raise


@router.post("/prompt")
async def prompt(
    request: PromptModel,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Post a new prompt and get response"""
    human_message = request.message
    chat_id = request.chat_id
    user_id = current_user["user_id"]
    if not human_message or not human_message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    try:
        is_valid, reject_msg, settings = await validate_prompt(human_message, session)
        if not is_valid:
            return {
                "success": False,
                "message": reject_msg,
            }
        actual_chat_id, thread_config = await get_or_create_chat(
            chat_id, user_id, session
        )
        
        # Check cache first before processing with LangGraph
        logger.debug(f"[CACHE CHECK] Checking cache for query: '{human_message[:50]}...'")
        cached_response = check_cache_for_query(human_message)
        
        if cached_response:
            logger.debug(f"[CACHE HIT] Found cached response, returning from cache")
            provider_config = await get_provider_config_for_model(
                session, request.provider_id, request.model_id
            ) if (request.provider_id and request.model_id) else await get_provider_config_for_chat(
                session, str(user_id)
            )
            try:
                new_message = Message(
                    chat_id=actual_chat_id,
                    human=human_message,
                    bot=cached_response,
                    responded_at=_utcnow_naive(),
                    model_id=provider_config.get("model_id") or "default",
                    provider_type=provider_config.get("provider_type") or "ollama",
                )
                session.add(new_message)
                await session.commit()
                await session.refresh(new_message)
            except Exception as e:
                await session.rollback()
                logger.debug(f"Error saving cached response to database: {e}")
            
            return {
                "success": True,
                "message": cached_response,
                "chat_id": str(actual_chat_id)
            }
        
        logger.debug(f"[CACHE MISS] No cached response found, processing with LangGraph")

        # Fetch and configure LLM provider (per-prompt override or default)
        if request.provider_id and request.model_id:
            provider_config = await get_provider_config_for_model(
                session, request.provider_id, request.model_id
            )
        else:
            provider_config = await get_provider_config_for_chat(session, str(user_id))
        llm_config = {
            "provider_type": provider_config.get("provider_type"),
            "model_id": provider_config.get("model_id"),
            "api_key": provider_config.get("api_key"),
            "base_url": provider_config.get("base_url"),
            "provider_config": provider_config.get("provider_config", {}),
            "temperature": provider_config.get("temperature"),
        }

        # Check if we need to generate a title
        result = await session.execute(
            select(Chat.title).where(Chat.id == actual_chat_id)
        )
        current_title = result.scalar_one_or_none()
        needs_title = (
            request.generate_title
            and (not current_title or current_title.strip() in ("", "New Chat"))
        )
        langfuse_enabled = settings.langfuse_enabled if settings else False
        langfuse_config = resolve_langfuse_config(settings)

        inputs = {
            "messages": [("user", human_message)],
            "session_id": str(actual_chat_id),
            "user_id": str(user_id),
            "langfuse_enabled": langfuse_enabled,
            "langfuse_config": langfuse_config,
            "generate_title": not needs_title,  # False = API handles title in parallel
            "llm_config": llm_config,
        }

        # Run main response and title generation in parallel
        title_task = None
        if needs_title:
            title_task = asyncio.create_task(
                asyncio.to_thread(
                    generate_title_from_query,
                    human_message,
                    str(actual_chat_id),
                    str(user_id),
                    langfuse_enabled,
                    llm_config,
                    langfuse_config,
                )
            )
            logger.debug("[PARALLEL TITLE] Non-stream: Task started")

        answer, graph_title = await get_graph_response_non_stream(
            inputs, thread_config
        )

        # Get title from parallel task or graph
        title = None
        if title_task:
            try:
                title = await asyncio.wait_for(title_task, timeout=10.0)
                logger.debug(f"[PARALLEL TITLE] Non-stream: Got title '{title}'")
            except asyncio.TimeoutError:
                logger.debug("[PARALLEL TITLE] Non-stream: Timeout")
            except Exception as e:
                logger.debug(f"[PARALLEL TITLE] Non-stream: Error {e}")
        elif graph_title:
            title = graph_title

        if title:
            try:
                result = await session.execute(
                    select(Chat).where(Chat.id == actual_chat_id, Chat.user_id == user_id)
                )
                chat_row = result.scalar_one_or_none()
                if chat_row and (not chat_row.title or chat_row.title.strip() in ("", "New Chat")):
                    chat_row.title = title
                    await session.commit()
            except Exception as e:
                await session.rollback()
                logger.debug(f"Error saving generated title (non-stream) to database: {e}")
        
        # Store response in cache for future use
        try:
            logger.debug(f"[CACHE STORE] Storing response in cache for query: '{human_message[:50]}...'")
            store_chat_response(human_message, answer)
            logger.debug(f"[CACHE STORE] Successfully cached response")
        except Exception as e:
            logger.debug(f"[CACHE ERROR] Error storing response in cache: {e}")
        
        message = Message(
            chat_id=actual_chat_id,
            human=human_message,
            bot=answer,
            responded_at=_utcnow_naive(),
            model_id=llm_config.get("model_id") or "default",
            provider_type=llm_config.get("provider_type") or "ollama",
        )
        session.add(message)
        await session.commit()
        return {"answer": answer, "chat_id": actual_chat_id}
    except Exception as e:
        await session.rollback()
        logger.debug(f"Error occurred while processing prompt: {e}")
        return {
            "success": False,
            "message": f"An error occurred while processing the prompt: {e}",
        }


# /messages/{chat_id} -> Get paginated messages in a chat
@router.get("/messages/{chat_id}")
async def get_chat_with_messages(
    chat_id: UUID,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Retrieve a chat and its paginated messages by chat id, with messages sorted by creation time."""
    try:
        user_id = current_user["user_id"]
        # Get the chat
        result = await session.execute(
            select(Chat).where(
                Chat.id == chat_id, Chat.user_id == user_id, Chat.archived_at == None
            )
        )
        chat = result.scalar_one_or_none()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        # Get total message count
        count_result = await session.execute(
            select(func.count(Message.id)).where(Message.chat_id == chat_id)
        )
        total = count_result.scalar() or 0

        # Get paginated messages for the chat, sorted by created_at ascending
        messages_result = await session.execute(
            select(Message)
            .where(Message.chat_id == chat_id)
            .order_by(asc(Message.created_at))
            .limit(limit)
            .offset(offset)
        )
        messages = messages_result.scalars().all()

        # Format messages for response
        messages_data = [
            {
                "id": str(msg.id),
                "chat_id": str(msg.chat_id),
                "human": msg.human,
                "bot": msg.bot,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
                "responded_at": msg.responded_at.isoformat() if msg.responded_at else None,
                "time_to_first_token_ms": msg.time_to_first_token_ms,
                "total_response_time_ms": msg.total_response_time_ms,
                "model_id": msg.model_id,
                "provider_type": msg.provider_type,
            }
            for msg in messages
        ]

        return {
            "error": False,
            "id": str(chat.id),
            "user_id": str(chat.user_id),
            "title": chat.title,
            "updated_at": chat.updated_at.isoformat() if chat.updated_at else None,
            "messages": messages_data,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(messages_data) < total,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.debug(f"Error retrieving chat messages: {e}")
        return{
            "error": True,
            "message": f"Chat messages could not be retrieved: {e}",
        }


# /rename/{chat_id} -> Rename a chat
@router.put("/rename/{chat_id}")
async def rename_chat(
    chat_id: UUID,
    request: ChatRenameRequest,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Rename a chat by chat id."""
    user_id = current_user["user_id"]
    result = await session.execute(
        select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
    )
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    chat.title = request.title
    await session.commit()
    return {
        "error": False,
        "detail": "Chat renamed successfully",
        "new_title": request.title,
    }


# /archive/{chat_id} -> Archive a chat
@router.delete("/archive/{chat_id}")
async def archive_chat(
    chat_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Archive a chat and its messages by chat id."""
    try:
        user_id = current_user["user_id"]
        # Verify the chat exists and belongs to the user
        result = await session.execute(
            select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
        )
        chat = result.scalar_one_or_none()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        chat.archived_at = func.now()
        await session.commit()
        return {
            "error": False,
            "message": "Chat archived successfully",
        }
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        return {
            "error": True,
            "message": f"An error occurred while archiving the chat: {e}",
        }


@router.patch("/messages/{message_id}/partial")
async def save_partial_message(
    message_id: UUID,
    data: MessagePartialUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Save a partial bot response (e.g. when user stops streaming)."""
    user_id = current_user["user_id"]
    result = await session.execute(
        select(Message).join(Chat, Message.chat_id == Chat.id).where(
            Message.id == message_id,
            Chat.user_id == user_id,
        )
    )
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    message.bot = data.bot
    await session.commit()
    return {"success": True}
