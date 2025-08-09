from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.api.db.database import get_session
from src.api.models import Chat
from src.api.schemas import ChatCreate, ChatResponse, ChatListItem, ChatListResponse
from src.api.utils.auth import get_current_user
from typing import List

router = APIRouter()

@router.post("/chats", response_model=ChatResponse)
async def create_chat(chat: ChatCreate, session: AsyncSession = Depends(get_session)):
    new_chat = Chat(user_id=chat.user_id, title=chat.title, summary=chat.summary)
    session.add(new_chat)
    await session.commit()
    await session.refresh(new_chat)
    return new_chat

@router.get("/chats", response_model=List[ChatResponse])
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
