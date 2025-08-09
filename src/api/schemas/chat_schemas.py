from pydantic import BaseModel
from datetime import datetime
from typing import List

class ChatCreate(BaseModel):
    user_id: str
    title: str
    summary: str = None

class ChatResponse(BaseModel):
    id: str
    user_id: str
    title: str
    summary: str

class ChatListItem(BaseModel):
    """Schema for chat list items containing only id, title, and created_at."""
    id: str
    title: str
    created_at: datetime

class ChatListResponse(BaseModel):
    """Schema for the response containing list of user's chats."""
    chats: List[ChatListItem]