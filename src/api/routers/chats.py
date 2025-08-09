from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.api.db.database import get_session
from src.api.models import Chat
from src.api.schemas import ChatCreate, ChatResponse
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
