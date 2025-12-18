from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from ..core.jwt import decode_token
from ..db.session import get_session
from ..db.models import User, RevokedToken
import uuid

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session)
) -> dict:
    """Get current user from JWT token in Authorization header."""
    token = credentials.credentials
    payload = decode_token(token)
    
    user_id = payload.get("user_id")
    jti = payload.get("jti")
    token_version = payload.get("token_version")

    if not user_id:
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Check revocation (JTI)
    if jti:
        result = await session.execute(select(RevokedToken).where(RevokedToken.jti == jti))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token revoked",
            )

    # Check if user is active in DB
    result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive or deleted",
        )
    
    # Check token version (Global revocation)
    if token_version and str(token_version) != str(user.token_version):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalid (logged out or role changed)",
        )
    
    return payload

# Role checks are allowed ONLY for admin/internal routes.
def require_role(role_name: str):
    def dependency(user: dict = Depends(get_current_user)):
        role = user.get("role")
        if role != role_name:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing role: {role_name}",
            )
        return user
    return dependency
