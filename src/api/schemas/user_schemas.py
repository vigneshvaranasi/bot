from pydantic import BaseModel

class UserCreate(BaseModel):
    email: str
    password: str
    role_id: str

class UserResponse(BaseModel):
    id: str
    email: str
    role_id: str