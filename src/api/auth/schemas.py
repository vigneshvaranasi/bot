from pydantic import BaseModel, EmailStr
from typing import Optional, List
import uuid

class UserSignup(BaseModel):
    email: EmailStr
    password: str
    role_id: Optional[uuid.UUID] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class PasswordUpdate(BaseModel):
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: uuid.UUID
    email: Optional[str]
    role: str

class UserResponse(BaseModel):
    id: uuid.UUID
    email: Optional[str]
    is_active: bool
    role: str
    auth_identities: List[str]

    class Config:
        from_attributes = True
