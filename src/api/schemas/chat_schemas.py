from pydantic import BaseModel

class ChatCreate(BaseModel):
    user_id: str
    title: str
    summary: str = None

class ChatResponse(BaseModel):
    id: str
    user_id: str
    title: str
    summary: str