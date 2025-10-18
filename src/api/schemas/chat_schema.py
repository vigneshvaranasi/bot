from datetime import datetime
from pydantic import BaseModel

class PromptModel(BaseModel):
    message:str
    chat_id: str | None
    is_stream: bool = False
    
class ChatRenameRequest(BaseModel):
    """Schema for renaming a chat."""
    title: str
    
class ChatListItem(BaseModel):
    """Schema for chat list items containing only id, title, and updated_at."""
    id: str
    title: str
    updated_at: datetime