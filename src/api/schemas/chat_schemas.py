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


class ChatPromptResponse(BaseModel):
    """Schema for the response containing chat prompt."""
    chatId: str
    chatTitle: str
    new_message: str

class ChatPromptRequest(BaseModel):
    """Schema for the request containing chat prompt."""
    chatId: str = None
    prompt: str
    
class ChatRenameRequest(BaseModel):
    """Schema for renaming a chat."""
    title: str