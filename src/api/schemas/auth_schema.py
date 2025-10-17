from pydantic import BaseModel, EmailStr
from typing import Optional

class UserSignup(BaseModel):
    email: EmailStr
    password: str
    role_id: str
    
class UserSignupResponse(BaseModel):
    success: bool
    message: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    jwt: Optional[str] = None
    email: Optional[str] = None
    role_id: Optional[str] = None