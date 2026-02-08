from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
import uuid
import logging

from ..core.jwt import decode_token
from ..db.session import get_session
from ..db.models import User, RevokedToken
from ..services.permission_service import get_user_permissions

security = HTTPBearer()
logger = logging.getLogger(__name__)


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
# DEPRECATED: Use require_permission() instead for new code.
def require_role(role_name: str):
    """Deprecated: Use require_permission() for permission-based authorization."""
    logger.warning(f"require_role('{role_name}') is deprecated. Use require_permission() instead.")

    def dependency(user: dict = Depends(get_current_user)):
        role = user.get("role")
        if role != role_name:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing role: {role_name}",
            )
        return user
    return dependency


def require_permission(permission_code: str):
    """Dependency factory for permission-based authorization.

    Usage:
        @router.get("/settings", dependencies=[Depends(require_permission("aiml.view"))])
        async def get_settings():
            ...

    Args:
        permission_code: The permission code required (e.g., 'aiml.view')

    Returns:
        FastAPI dependency function
    """
    async def dependency(
        user: dict = Depends(get_current_user),
        session: AsyncSession = Depends(get_session)
    ):
        user_id = uuid.UUID(user["user_id"])
        permissions = await get_user_permissions(user_id, session)

        if permission_code not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {permission_code}",
            )
        return user
    return dependency


def require_any_permission(*permission_codes: str):
    """Require at least one of the specified permissions.

    Usage:
        @router.get("/data", dependencies=[Depends(require_any_permission("data.view", "data.edit"))])
        async def get_data():
            ...

    Args:
        *permission_codes: Permission codes, at least one must be present

    Returns:
        FastAPI dependency function
    """
    async def dependency(
        user: dict = Depends(get_current_user),
        session: AsyncSession = Depends(get_session)
    ):
        user_id = uuid.UUID(user["user_id"])
        permissions = await get_user_permissions(user_id, session)

        if not permissions.intersection(set(permission_codes)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing one of permissions: {', '.join(permission_codes)}",
            )
        return user
    return dependency


def require_all_permissions(*permission_codes: str):
    """Require all of the specified permissions.

    Usage:
        @router.delete("/critical", dependencies=[Depends(require_all_permissions("admin.delete", "audit.log"))])
        async def delete_critical():
            ...

    Args:
        *permission_codes: Permission codes, all must be present

    Returns:
        FastAPI dependency function
    """
    async def dependency(
        user: dict = Depends(get_current_user),
        session: AsyncSession = Depends(get_session)
    ):
        user_id = uuid.UUID(user["user_id"])
        permissions = await get_user_permissions(user_id, session)

        missing = set(permission_codes) - permissions
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permissions: {', '.join(missing)}",
            )
        return user
    return dependency


async def get_current_user_permissions(
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> set:
    """Get current user's permission codes as a set.

    Useful when you need to check permissions within a route handler.

    Usage:
        @router.get("/data")
        async def get_data(permissions: set = Depends(get_current_user_permissions)):
            if "data.edit" in permissions:
                # Show edit button
            ...
    """
    user_id = uuid.UUID(user["user_id"])
    return await get_user_permissions(user_id, session)
