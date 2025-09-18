from sqlalchemy import asc

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.api.schemas.chat_schemas import ChatPromptResponse, ChatPromptRequest
from src.api.db.database import get_session
from src.api.models import Chat, Message
from src.api.schemas import ChatCreate, ChatResponse, ChatListItem, ChatListResponse
from src.api.utils.auth import get_current_user
from src.support_bot.crew import support_crew, conversation_summary_crew,conversation_title_generation_crew
from src.support_bot.utils.formatting import sanitize_markdown_output
from src.support_bot.runner import run_support_with_emitter
from typing import List
import re
import asyncio
import json

from src.support_bot.prompt_guardrail import PromptGuardrail

router = APIRouter()


@router.post("/", response_model=ChatResponse)
async def create_chat(chat: ChatCreate, session: AsyncSession = Depends(get_session)):
    new_chat = Chat(user_id=chat.user_id, title=chat.title, summary=chat.summary)
    session.add(new_chat)
    await session.commit()
    await session.refresh(new_chat)
    return new_chat

@router.get("/", response_model=List[ChatResponse])
async def get_chats(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Chat))
    chats = result.scalars().all()
    return chats

@router.get("/my-chats", response_model=ChatListResponse)
async def get_user_chats(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get all chats for the authenticated user with only id, title, and created_at."""
    user_id = current_user["user_id"]
    
    result = await session.execute(
        select(Chat.id, Chat.title, Chat.created_at)
        .where(Chat.user_id == user_id)
        .order_by(Chat.created_at.desc())
    )
    
    chats_data = result.all()
    
    chat_items = [
        ChatListItem(
            id=str(chat.id),
            title=chat.title,
            created_at=chat.created_at
        )
        for chat in chats_data
    ]
    
    return ChatListResponse(chats=chat_items)

# new message
@router.post("/prompt")
async def get_chat_prompt(
    request: ChatPromptRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """
    Process a chat prompt and stream SSE status updates while working.
    Emits events: status (Thinking/Researching/Processing) and result (final payload).
    """
    user_id = current_user["user_id"]

    def sse(event: str, data: str) -> str:
        return f"event: {event}\ndata: {data}\n\n"
    
    async def is_client_connected() -> bool:
        """Check if the client is still connected"""
        try:
            # Check if the client connection is still active
            return not await http_request.is_disconnected()
        except Exception:
            return False
    
    isContextPresent = bool(request.chatId)
    guard = PromptGuardrail()
    is_valid, reject_msg = guard.validate_or_reject(prompt=request.prompt, isContext=isContextPresent)
    if not is_valid:
        # Stream an immediate SSE error so the client receives Reject Event
        async def immediate_reject_stream():
            try:
                yield sse("status", "Thinking")
                yield sse("error", reject_msg)
                yield sse("end", "bye")
            except Exception:
                return

        headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
        return StreamingResponse(immediate_reject_stream(), media_type="text/event-stream", headers=headers)

    async def kickoff_support_with_events(inputs: dict, emit):
        result = await run_support_with_emitter(inputs, emit)
        return sanitize_markdown_output(str(result))

    async def event_stream():
        try:
            yield sse("status", "Thinking")
            await asyncio.sleep(0)

            chat_id = request.chatId
            if chat_id is not None and isinstance(chat_id, str) and chat_id.strip() == "":
                chat_id = None

            if chat_id is None:
                yield sse("status", "Researching")
                inputs = {"user_prompt": request.prompt, "context": ""}

                async def emit(event: str, data):
                    try:
                        if not isinstance(data, str):
                            data_json = json.dumps(data)
                        else:
                            data_json = data
                        yield sse(event, data_json)
                    except Exception:
                        pass

                queue: asyncio.Queue = asyncio.Queue()

                def emitter(event: str, data):
                    try:
                        queue.put_nowait((event, data))
                    except Exception:
                        pass

                async def pump_events(task: asyncio.Task):
                    while True:
                        # Check if client is still connected
                        if not await is_client_connected():
                            task.cancel()
                            yield sse("error", "Request cancelled by client")
                            return
                        
                        if task.done() and queue.empty():
                            break
                        try:
                            event, data = await asyncio.wait_for(queue.get(), timeout=0.1)
                            if not isinstance(data, str):
                                data = json.dumps(data)
                            yield sse(event, data)
                        except asyncio.TimeoutError:
                            continue
                        except asyncio.CancelledError:
                            yield sse("error", "Request cancelled")
                            return

                crew_task = asyncio.create_task(kickoff_support_with_events(inputs, emitter))
                try:
                    async for chunk in pump_events(crew_task):
                        yield chunk
                    bot_response = await crew_task
                except asyncio.CancelledError:
                    yield sse("error", "Request cancelled by user")
                    return
                except Exception as e:
                    crew_task.cancel()
                    yield sse("error", f"Processing error: {str(e)}")
                    return

                yield sse("status", "Processing")
                title = await generate_title_from_prompt(request.prompt)
                summary = await generate_summary_from_content(request.prompt, bot_response)

                new_chat = Chat(user_id=user_id, title=title, summary=summary)
                session.add(new_chat)
                await session.commit()
                await session.refresh(new_chat)

                new_message = Message(
                    chat_id=new_chat.id,
                    user_query=request.prompt,
                    bot_solution=bot_response,
                )
                session.add(new_message)
                await session.commit()

                payload = {
                    "chatId": str(new_chat.id),
                    "chatTitle": title,
                    "new_message": bot_response,
                }
                yield sse("result", json.dumps(payload))

            else:
                result = await session.execute(
                    select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
                )
                existing_chat = result.scalar_one_or_none()

                if not existing_chat:
                    yield sse("error", "Chat not found")
                    return
                
                

                inputs = {
                    "user_prompt": request.prompt,
                    "context": existing_chat.summary or "",
                }

                queue: asyncio.Queue = asyncio.Queue()

                def emitter(event: str, data):
                    try:
                        queue.put_nowait((event, data))
                    except Exception:
                        pass

                async def pump_events(task: asyncio.Task):
                    while True:
                        # Check if client is still connected
                        if not await is_client_connected():
                            task.cancel()
                            yield sse("error", "Request cancelled by client")
                            return
                        
                        if task.done() and queue.empty():
                            break
                        try:
                            event, data = await asyncio.wait_for(queue.get(), timeout=0.1)
                            if not isinstance(data, str):
                                data = json.dumps(data)
                            yield sse(event, data)
                        except asyncio.TimeoutError:
                            continue
                        except asyncio.CancelledError:
                            yield sse("error", "Request cancelled")
                            return

                crew_task = asyncio.create_task(kickoff_support_with_events(inputs, emitter))
                try:
                    async for chunk in pump_events(crew_task):
                        yield chunk
                    bot_response = await crew_task
                except asyncio.CancelledError:
                    yield sse("error", "Request cancelled by user")
                    return
                except Exception as e:
                    crew_task.cancel()
                    yield sse("error", f"Processing error: {str(e)}")
                    return

                yield sse("status", "Processing")

                new_message = Message(
                    chat_id=existing_chat.id,
                    user_query=request.prompt,
                    bot_solution=bot_response,
                )
                session.add(new_message)

                updated_summary = await update_chat_summary(
                    existing_chat.summary or "", request.prompt, bot_response
                )
                existing_chat.summary = updated_summary

                await session.commit()

                payload = {
                    "chatId": str(existing_chat.id),
                    "chatTitle": existing_chat.title,
                    "new_message": bot_response,
                }
                yield sse("result", json.dumps(payload))

            yield sse("end", "bye")

        except Exception as e:
            await session.rollback()
            # to do: report to admin
            print(f"Prompt error: {str(e)}")
            user_message = "Sorry, the AI service is currently unavailable. Please try again later."
            yield sse("error", user_message)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)


async def generate_title_from_prompt(prompt: str) -> str:
    """Generate a concise title from the user's prompt using the conversation title generation crew."""
    try:
        inputs = {
            'user_prompt': prompt
        }
        
        result = conversation_title_generation_crew.kickoff(inputs=inputs)
        title = str(result).strip()
        
        if len(title) > 50:
            title = title[:47] + "..."
            
        return title or "New Chat"
        
    except Exception as e:
        # Fallback to simple title generation if crew fails
        title = prompt.strip()
        title = re.sub(r'[^\w\s-]', '', title)
        words = title.split()
        if len(words) > 6:
            title = ' '.join(words[:6]) + "..."
        return title or "New Chat"


async def generate_summary_from_content(prompt: str, response: str) -> str:
    """Generate a summary from prompt and response using the conversation summary crew."""
    try:
        conversation_json = {
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response}
            ]
        }
        
        inputs = {
            'conversation_json': str(conversation_json)
        }
        
        result = conversation_summary_crew.kickoff(inputs=inputs)
        return str(result)[:500]
        
    except Exception as e:
        return f"Discussion about: {prompt[:100]}..."


async def update_chat_summary(current_summary: str, new_prompt: str, new_response: str) -> str:
    """Update the chat summary with new conversation content."""
    try:
        conversation_json = {
            "previous_context": current_summary,
            "new_messages": [
                {"role": "user", "content": new_prompt},
                {"role": "assistant", "content": new_response}
            ]
        }
        
        inputs = {
            'conversation_json': str(conversation_json)
        }
        
        result = conversation_summary_crew.kickoff(inputs=inputs)
        return str(result)[:500]
        
    except Exception as e:
        return f"{current_summary}\n\nLatest: {new_prompt[:50]}..."
    


@router.get("/messages/{chat_id}")
async def get_chat_with_messages(chat_id: str, session: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
    """Retrieve a chat and its messages by chat id, with messages sorted by creation time."""
    user_id = current_user["user_id"]
    # Get the chat
    result = await session.execute(
        select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
    )
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Get messages for the chat, sorted by created_at ascending
    messages_result = await session.execute(
        select(Message).where(Message.chat_id == chat_id).order_by(asc(Message.created_at))
    )
    messages = messages_result.scalars().all()

    # Format messages for response
    messages_data = [
        {
            "id": str(msg.id),
            "chat_id": str(msg.chat_id),
            "user_query": msg.user_query,
            "bot_solution": msg.bot_solution,
            "created_at": msg.created_at.isoformat() if msg.created_at else None
        }
        for msg in messages
    ]

    return {
        "id": str(chat.id),
        "user_id": str(chat.user_id),
        "title": chat.title,
        "summary": chat.summary,
        "created_at": chat.created_at.isoformat() if chat.created_at else None,
        "updated_at": chat.updated_at.isoformat() if chat.updated_at else None,
        "messages": messages_data
    }