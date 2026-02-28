from datetime import datetime, timedelta, timezone
from typing import Optional
import threading
import uuid

import jwt
from jwt import InvalidTokenError

from src.api.core.config import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRY_DAYS

SECRET_KEY = JWT_SECRET_KEY
ALGORITHM = JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_DAYS = JWT_EXPIRY_DAYS

_consumed_state_jtis: dict[str, datetime] = {}
_consumed_jtis_lock = threading.Lock()

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
    """Create a signed OAuth state with a unique jti for replay protection."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode = {
        "jti": str(uuid.uuid4()),
        "sub": "oauth_state",
        "provider": provider,
        "purpose": purpose,
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }
    if user_id:
        to_encode["user_id"] = user_id
        
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_oauth_state(token: str) -> Optional[dict]:
    """Verify, decode, and consume an OAuth state token (single-use).

    Returns None if the token is invalid, expired, or already used.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": True})
        if payload.get("sub") != "oauth_state":
            return None
        jti = payload.get("jti")
        if not jti:
            return None

        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

        with _consumed_jtis_lock:
            now = datetime.now(timezone.utc)
            expired_keys = [k for k, v in _consumed_state_jtis.items() if v <= now]
            for k in expired_keys:
                del _consumed_state_jtis[k]

            if jti in _consumed_state_jtis:
                return None

            _consumed_state_jtis[jti] = exp

        return payload
    except InvalidTokenError:
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
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
