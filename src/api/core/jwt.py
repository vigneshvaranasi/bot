from datetime import datetime, timedelta, timezone
import os
from typing import Optional, List
from jose import JWTError, jwt
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_EXPIRY", "7"))

import uuid

def create_access_token(
    user_id: str,
    role: str,
    auth_provider: str,
    token_version: int,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)

    to_encode = {
        "jti": str(uuid.uuid4()),
        "user_id": user_id,
        "role": role,
        "auth_provider": auth_provider,
        "token_version": str(token_version),
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_oauth_state(provider: str, user_id: Optional[str] = None, purpose: str = "login") -> str:
    """Create a signed OAuth state."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode = {
        "sub": "oauth_state",
        "provider": provider,
        "purpose": purpose,
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }
    if user_id:
        to_encode["user_id"] = user_id
        
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_oauth_state(token: str) -> dict:
    """Verify and decode OAuth state."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": True})
        if payload.get("sub") != "oauth_state":
            return None
        return payload
    except JWTError:
        return None

from fastapi import HTTPException, status

def decode_token(token: str) -> dict:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": True})
        if "exp" not in payload or "iat" not in payload:
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing expiration or issued at time",
            )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
