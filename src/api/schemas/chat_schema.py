from datetime import datetime
from pydantic import BaseModel

class PromptModel(BaseModel):
    message:str
    chat_id: str | None
    generate_title: bool = True
    provider_id: str | None = None
    model_id: str | None = None
    
class ChatRenameRequest(BaseModel):
    """Schema for renaming a chat."""
    title: str
    
class MessagePartialUpdate(BaseModel):
    """Schema for saving a partial bot response."""
    bot: str

class ChatListItem(BaseModel):
    """Schema for chat list items containing only id, title, and updated_at."""
    id: str
    title: str
    updated_at: datetime