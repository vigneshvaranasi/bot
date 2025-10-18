from datetime import datetime
from fastapi import HTTPException
import json
from sqlalchemy import asc, func, select
from src.api.utils.auth import get_current_user
from src.copilot.graph import create_agent_graph
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from src.api.schemas.chat_schema import ChatListItem, ChatRenameRequest, PromptModel
from langchain_core.messages import AIMessage,AIMessageChunk
from src.api.db.models import Chat,Message
from src.api.db.session import get_session
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

# / -> Get All Chats of the User
@router.get("/")
async def get_user_chats(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
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
            ChatListItem(
                id=str(chat.id),
                title=chat.title,
                updated_at=chat.updated_at
            )
            for chat in chats_data
        ]
        
        return {
            "error":False,
            "chats": chat_items
        }

    except Exception as e:
        print(f"Error retrieving user chats: {e}")
        return {
            "error": True,
            "message": f"Could not retrieve chats: {e}",
        }

# Build graph
support_bot_graph = create_agent_graph()

async def get_or_create_chat(chat_id: str | None, user_id: str, session: AsyncSession) -> tuple[str, dict]:
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
            select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id, Chat.archived_at.is_(None))
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
async def prompt_stream(request: PromptModel, current_user: dict = Depends(get_current_user), session:AsyncSession = Depends(get_session)):
    """Post a new prompt and get response"""
    humanMessage = request.message
    chat_id = request.chat_id
    user_id = current_user["user_id"]
    new_chat = None
    try:
        actual_chat_id, thread_config = await get_or_create_chat(chat_id, user_id, session)
        inputs = {"messages": [("user", humanMessage)]}
        async def stream_generator():
            answer = ""
            memory_saved = False
            # Streaming mode
            for mode,chunk in support_bot_graph.stream(
                config=thread_config,
                input=inputs,
                stream_mode=["custom", "messages"]
            ):
                if(mode=="custom"):
                    status_payload ={
                        "message": chunk["status"]
                    }
                    yield f"event: status\ndata: {json.dumps(status_payload)}\n\n"
                    if( "Almost done, wrapping up the details" in chunk["status"] and not memory_saved ):
                        final_data = {
                            "answer": answer,
                            "chat_id": str(actual_chat_id)
                        }
                        yield f"event: complete\ndata: {json.dumps(final_data)}\n\n"
                        # Finalize and save message to DB
                        try:
                            message = Message(chat_id=actual_chat_id, human=humanMessage, bot=answer)
                            session.add(message)
                            memory_saved = True
                            await session.commit()
                        except Exception as e:
                            await session.rollback()
                            print(f"Error saving message to database: {e}")

                elif(mode == "messages"):
                    for message_chunk in chunk:
                        if isinstance(message_chunk, AIMessageChunk) and message_chunk.content:
                            answer += message_chunk.content
                            chunk_payload = {
                                "chunk": message_chunk.content
                            }
                            yield f"event: final_answer\ndata: {json.dumps(chunk_payload)}\n\n"

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

async def get_graph_response_non_stream(inputs, config, support_bot_graph=support_bot_graph):
    """Helper function to get non-streaming response from the support bot graph."""
    try:
        result = support_bot_graph.invoke(inputs, config=config)
        final_message = result["messages"][-1]
        
        if isinstance(final_message, AIMessage):
            answer = str(final_message.content)
        else:
            answer = str(final_message.content)
        return answer
    except Exception as e:
        print(f"Error in get_graph_response_non_stream: {e}")
        raise e

@router.post("/prompt")
async def prompt(request: PromptModel, current_user: dict = Depends(get_current_user), session:AsyncSession = Depends(get_session)):
    """Post a new prompt and get response"""
    humanMessage = request.message
    chat_id = request.chat_id
    user_id = current_user["user_id"]
    new_chat = None
    try:
        actual_chat_id, thread_config = await get_or_create_chat(chat_id, user_id, session)
        inputs = {"messages": [("user", humanMessage)]}
        answer = await get_graph_response_non_stream(inputs, thread_config, support_bot_graph) 
        message = Message(chat_id=actual_chat_id,human=humanMessage,bot=answer)
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
async def get_chat_with_messages(chat_id: str, session: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
    """Retrieve a chat and its messages by chat id, with messages sorted by creation time."""
    try:
        user_id = current_user["user_id"]
        # Get the chat
        result = await session.execute(
            select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id, Chat.archived_at == None)
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
async def rename_chat(chat_id: str, request: ChatRenameRequest, session: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
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
    return {"error":False, "detail": "Chat renamed successfully", "new_title": request.title}

# /archive/{chat_id} -> Archive a chat
@router.delete("/archive/{chat_id}")
async def archive_chat(chat_id: str, session: AsyncSession = Depends(get_session), current_user: dict = Depends(get_current_user)):
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
