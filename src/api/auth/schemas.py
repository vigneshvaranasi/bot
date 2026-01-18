import re
import uuid
from typing import Optional, List

from pydantic import BaseModel, EmailStr, field_validator

from src.api.core.config import ENABLE_PASSWORD_VALIDATION


def validate_password_strength(password: str) -> str:
    """Validate password meets enterprise requirements.

    Requirements (when validation enabled):
    - Minimum 12 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    """
    if not ENABLE_PASSWORD_VALIDATION:
        return password

    errors = []
    if len(password) < 12:
        errors.append("at least 12 characters")
    if not re.search(r'[A-Z]', password):
        errors.append("one uppercase letter")
    if not re.search(r'[a-z]', password):
        errors.append("one lowercase letter")
    if not re.search(r'\d', password):
        errors.append("one digit")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append("one special character")

    if errors:
        raise ValueError(f"Password must contain: {', '.join(errors)}")
    return password


class UserSignup(BaseModel):
    email: EmailStr
    password: str
    role_id: Optional[uuid.UUID] = None

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class PasswordUpdate(BaseModel):
    password: str

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)


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
