from datetime import datetime
from fastapi import HTTPException
import json
import asyncio
from sqlalchemy import asc, func, select
from src.copilot.guardrails.prompt_guardrails import PromptGuardrail
from src.api.utils.auth import get_current_user
from scripts.cache import check_cache_for_query, store_chat_response
from src.copilot.graph import create_agent_graph
from src.copilot.utils import should_ask_clarification
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from src.api.schemas.chat_schema import ChatListItem, ChatRenameRequest, PromptModel
from langchain_core.messages import AIMessage, AIMessageChunk
from src.api.db.models import Chat, Message, Setting
from src.api.db.session import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from langfuse import get_client, propagate_attributes
from src.api.utils.tracing import conditional_observation
langfuse = get_client()


router = APIRouter()

# / -> Get All Chats of the User
@router.get("/")
async def get_user_chats(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get all chats for the authenticated user with only id, title, and created_at."""
    try:
        user_id = current_user["user_id"]
        result = await session.execute(
            select(Chat.id, Chat.title, Chat.updated_at)
            .where(Chat.user_id == user_id)
            .where(Chat.archived_at == None)
            .order_by(Chat.updated_at.desc())
        )
        chats_data = result.all()
        chat_items = [
            ChatListItem(id=str(chat.id), title=chat.title, updated_at=chat.updated_at)
            for chat in chats_data
        ]

        return {"error": False, "chats": chat_items}

    except Exception as e:
        print(f"Error retrieving user chats: {e}")
        return {
            "error": True,
            "message": f"Could not retrieve chats: {e}",
        }


# Build graph
support_bot_graph = create_agent_graph()


async def validate_prompt(prompt: str, session: AsyncSession):
    """Validate the prompt using the provided guardrail."""
    try:
        result = await session.execute(
            select(Setting).order_by(Setting.updated_at.desc())
        )
        settings = result.scalars().first()
        try:
            guard = PromptGuardrail(deny_words=settings.deny_words if settings else "")
            is_valid, reject_msg = guard.validate_or_reject(prompt=prompt)
            return is_valid, reject_msg, settings
        except Exception as e:
            raise ValueError(f"An error occurred while validating the prompt: {e}")
    except Exception as e:
        raise ValueError(f"An error occurred while accessing the Settings: {e}")


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
        thread_config = {"configurable": {"thread_id": str(chat_id)}}
        actual_chat_id = chat_id
    else:
        # create new chat
        try:
            new_chat = Chat(user_id=user_id, title="New Chat")
            session.add(new_chat)
            await session.commit()
            await session.refresh(new_chat)
            actual_chat_id = new_chat.id
            thread_config = {"configurable": {"thread_id": str(new_chat.id)}}
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
    humanMessage = request.message
    chat_id = request.chat_id
    user_id = current_user["user_id"]
    new_chat = None
    try:
        is_valid, reject_msg, settings = await validate_prompt(humanMessage, session)
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
            print(f"[CONVERSATION CHECK] Chat {actual_chat_id} has {message_count} messages")
        
        # Check if we should ask for clarification on context-dependent queries
        should_clarify, clarification_message = should_ask_clarification(humanMessage, has_conversation_history)
        if should_clarify:
            print(f"[CLARIFICATION NEEDED] Query requires clarification: '{humanMessage[:50]}...'")
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
        
        langfuse_enabled = settings.langfuse_enabled if settings else True
        inputs = {"messages": [("user", humanMessage)], "session_id": actual_chat_id,"user_id": str(user_id), "langfuse_enabled": langfuse_enabled }

        async def stream_generator():
            # Check cache first before processing with LangGraph
            # Only use cache for self-contained queries without conversation context
            print(f"[CACHE CHECK] Checking cache for query: '{humanMessage[:50]}...'")
            print(f"[CACHE CHECK] Has conversation history: {has_conversation_history}")
            cached_response = check_cache_for_query(humanMessage)
            
            if cached_response:
                print(f"[CACHE HIT] Found cached response, streaming from cache")
                # Stream cached response
                yield f"event: status\ndata: {json.dumps({'message': 'Found cached response, delivering instantly...'})}\n\n"
                
                # Generate title for new chat
                try:
                    result = await session.execute(
                        select(Chat).where(Chat.id == actual_chat_id, Chat.user_id == user_id)
                    )
                    chat_row = result.scalar_one_or_none()
                    if chat_row and (not chat_row.title or chat_row.title.strip() in ("", "New Chat")):
                        # Generate title from the user's query
                        from langchain_ollama import ChatOllama
                        from langchain_core.messages import SystemMessage
                        
                        llm = ChatOllama(
                            model="gpt-oss:20b",
                            base_url="http://ollama.trackcode.in",
                            temperature=0.1
                        )
                        
                        prompt = SystemMessage(
                            "Generate a concise, 2-4 word title for this query. "
                            "The title should clearly represent the main theme or subject. "
                            f"Query: {humanMessage}\n\n"
                            "Prioritize accuracy over excessive creativity; keep it clear and simple. "
                            "The output must be only the title, without any markdown code fences or other encapsulating text."
                        )
                        response = llm.invoke([prompt])
                        generated_title = response.content.strip()
                        if not generated_title:
                            generated_title = "Untitled Chat"
                        
                        chat_row.title = generated_title
                        await session.commit()
                        
                        # Send title event to frontend
                        yield f"event: title\ndata: {json.dumps({'title': generated_title})}\n\n"
                        print(f"[CACHE] Generated title: {generated_title}")
                except Exception as e:
                    await session.rollback()
                    print(f"Error generating title for cached response: {e}")
                
                # Save cached response to database (if new chat)
                try:
                    new_message = Message(
                        chat_id=actual_chat_id,
                        human=humanMessage,
                        bot=cached_response,
                    )
                    session.add(new_message)
                    await session.commit()
                    await session.refresh(new_message)
                except Exception as e:
                    await session.rollback()
                    print(f"Error saving cached response to database: {e}")
                
                # Stream the cached answer - send content chunks preserving markdown
                print(f"[CACHE STREAM] Streaming cached response with markdown formatting")
                
                # Split by characters to preserve newlines and markdown formatting
                chunk_size = 5  # Send 5 characters at a time for smooth streaming
                for i in range(0, len(cached_response), chunk_size):
                    chunk_text = cached_response[i:i + chunk_size]
                    chunk_payload = {"chunk": chunk_text}
                    yield f"event: final_answer\ndata: {json.dumps(chunk_payload)}\n\n"
                    await asyncio.sleep(0.01)  # Small delay for streaming effect
                
                # Send completion event with full answer
                final_data = {"answer": cached_response, "chat_id": str(actual_chat_id)}
                yield f"event: complete\ndata: {json.dumps(final_data)}\n\n"
                print(f"[CACHE STREAM] Stream completed successfully")
                return
            
            print(f"[CACHE MISS] No cached response found, processing with LangGraph")
            answer = ""
            memory_saved = False
            accumulate_answer = True
            generated_title = current_title

            workflow_observation = conditional_observation(
                enabled=langfuse_enabled,
                as_type="agent",
                name="copilot-chat",
                input=humanMessage,
                metadata={"type": "streaming", "chat_id": str(actual_chat_id)}
            )
            try:
                with workflow_observation as observation:
                    with propagate_attributes(
                        session_id=str(actual_chat_id),
                        user_id=str(user_id)
                    ):
                        # Streaming mode
                        for mode, chunk in support_bot_graph.stream(
                            config=thread_config, input=inputs, stream_mode=["custom", "messages"]
                        ):
                            if mode == "custom":
                                # Title event
                                if isinstance(chunk, dict) and "title" in chunk:
                                    generated_title = chunk["title"]
                                    yield f"event: title\ndata: {json.dumps({'title': generated_title})}\n\n"
                                    try:
                                        result = await session.execute(
                                            select(Chat).where(Chat.id == actual_chat_id, Chat.user_id == user_id)
                                        )
                                        chat_row = result.scalar_one_or_none()
                                        if chat_row and (not chat_row.title or chat_row.title.strip() in ("", "New Chat")):
                                            chat_row.title = generated_title
                                            await session.commit()
                                    except Exception as e:
                                        await session.rollback()
                                        print(f"Error saving generated title to database: {e}")

                                # Status event
                                if isinstance(chunk, dict) and "status" in chunk:
                                    status_payload = {"message": chunk["status"]}
                                    yield f"event: status\ndata: {json.dumps(status_payload)}\n\n"
                                    # Once title generation begins, stop accumulating answer chunks
                                    if "Generating title for the incident report" in chunk["status"]:
                                        accumulate_answer = False
                                    if (
                                        "Almost done, wrapping up the details" in chunk["status"]
                                        and not memory_saved
                                    ):
                                        final_data = {"answer": answer, "chat_id": str(actual_chat_id)}
                                        yield f"event: complete\ndata: {json.dumps(final_data)}\n\n"
                                        
                                        # Store response in cache for future use
                                        try:
                                            print(f"[CACHE STORE] Storing response in cache for query: '{humanMessage[:50]}...'")
                                            store_chat_response(humanMessage, answer)
                                            print(f"[CACHE STORE] Successfully cached response")
                                        except Exception as e:
                                            print(f"[CACHE ERROR] Error storing response in cache: {e}")
                                        
                                        # Finalize and save message to DB
                                        try:
                                            message = Message(
                                                chat_id=actual_chat_id, human=humanMessage, bot=answer
                                            )
                                            session.add(message)
                                            memory_saved = True
                                            await session.commit()
                                        except Exception as e:
                                            await session.rollback()
                                            print(f"Error saving message to database: {e}")

                            elif mode == "messages":
                                token_chunk, metadata = chunk
                                if (
                                    metadata.get('langgraph_node')!='qdrant_search'
                                    and isinstance(token_chunk, AIMessageChunk)
                                    and token_chunk.content
                                ):
                                    if accumulate_answer:
                                        answer += token_chunk.content
                                        chunk_payload = {"chunk": token_chunk.content}
                                        yield f"event: final_answer\ndata: {json.dumps(chunk_payload)}\n\n"
                        
                        observation.update(output=answer,name=generated_title)
            except Exception as e:
                print(f"Error during streaming response: {e}")
                raise e

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
            }
        )
    except Exception as e:
        await session.rollback()
        print(f"Error occurred while processing prompt: {e}")
        return {
            "success": False,
            "message": f"An error occurred while processing the prompt: {e}",
        }


async def get_graph_response_non_stream(
    inputs, config, support_bot_graph=support_bot_graph
):
    """Helper function to get non-streaming response from the support bot graph."""
    try:
        result = support_bot_graph.invoke(inputs, config=config)
        final_message = result["messages"][-1]

        if isinstance(final_message, AIMessage):
            answer = str(final_message.content)
        else:
            answer = str(final_message.content)
        title = result.get("title") if isinstance(result, dict) else None
        return answer, title
    except Exception as e:
        print(f"Error in get_graph_response_non_stream: {e}")
        raise e


@router.post("/prompt")
async def prompt(
    request: PromptModel,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Post a new prompt and get response"""
    humanMessage = request.message
    chat_id = request.chat_id
    user_id = current_user["user_id"]
    new_chat = None
    try:
        is_valid, reject_msg, settings = await validate_prompt(humanMessage, session)
        if not is_valid:
            return {
                "success": False,
                "message": reject_msg,
            }
        actual_chat_id, thread_config = await get_or_create_chat(
            chat_id, user_id, session
        )
        
        # Check cache first before processing with LangGraph
        print(f"[CACHE CHECK] Checking cache for query: '{humanMessage[:50]}...'")
        cached_response = check_cache_for_query(humanMessage)
        
        if cached_response:
            print(f"[CACHE HIT] Found cached response, returning from cache")
            # Save cached response to database
            try:
                new_message = Message(
                    chat_id=actual_chat_id,
                    human=humanMessage,
                    bot=cached_response,
                )
                session.add(new_message)
                await session.commit()
                await session.refresh(new_message)
            except Exception as e:
                await session.rollback()
                print(f"Error saving cached response to database: {e}")
            
            return {
                "success": True,
                "message": cached_response,
                "chat_id": str(actual_chat_id)
            }
        
        print(f"[CACHE MISS] No cached response found, processing with LangGraph")
        inputs = {"messages": [("user", humanMessage)]}
        answer, title = await get_graph_response_non_stream(
            inputs, thread_config, support_bot_graph
        )
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
                print(f"Error saving generated title (non-stream) to database: {e}")
        
        # Store response in cache for future use
        try:
            print(f"[CACHE STORE] Storing response in cache for query: '{humanMessage[:50]}...'")
            store_chat_response(humanMessage, answer)
            print(f"[CACHE STORE] Successfully cached response")
        except Exception as e:
            print(f"[CACHE ERROR] Error storing response in cache: {e}")
        
        message = Message(chat_id=actual_chat_id, human=humanMessage, bot=answer)
        session.add(message)
        await session.commit()
        return {"answer": answer, "chat_id": actual_chat_id}
    except Exception as e:
        await session.rollback()
        print(f"Error occurred while processing prompt: {e}")
        return {
            "success": False,
            "message": f"An error occurred while processing the prompt: {e}",
        }


# /messages/{chat_id} -> Get all messages in a chat
@router.get("/messages/{chat_id}")
async def get_chat_with_messages(
    chat_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Retrieve a chat and its messages by chat id, with messages sorted by creation time."""
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

        # Get messages for the chat, sorted by created_at ascending
        messages_result = await session.execute(
            select(Message)
            .where(Message.chat_id == chat_id)
            .order_by(asc(Message.created_at))
        )
        messages = messages_result.scalars().all()

        # Format messages for response
        messages_data = [
            {
                "id": str(msg.id),
                "chat_id": str(msg.chat_id),
                "human": msg.human,
                "bot": msg.bot,
                "created_at": msg.created_at.isoformat() if msg.created_at else None
            }
            for msg in messages
        ]

        return {
            "error": False,
            "id": str(chat.id),
            "user_id": str(chat.user_id),
            "title": chat.title,
            "updated_at": chat.updated_at.isoformat() if chat.updated_at else None,
            "messages": messages_data
        }
    except Exception as e:
        print(f"Error retrieving chat messages: {e}")
        return{
            "error": True,
            "message": f"Chat messages could not be retrieved: {e}",
        }


# /rename/{chat_id} -> Rename a chat
@router.put("/rename/{chat_id}")
async def rename_chat(
    chat_id: str,
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
    chat_id: str,
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
    except Exception as e:
        await session.rollback()
        return {
            "error": True,
            "message": f"An error occurred while archiving the chat: {e}",
        }
