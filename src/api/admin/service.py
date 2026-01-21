from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func, or_
from fastapi import HTTPException
from ..db.models import AuthProvider, User, Role
from ..auth.service import revoke_all_user_tokens
from typing import Optional, Tuple, List
import uuid


async def get_paginated_users(
    session: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    search: Optional[str] = None
) -> Tuple[List[User], int]:
    """Get paginated users with optional search.

    Returns a tuple of (users, total_count).
    """
    # Base query with non-deleted users
    base_filter = User.deleted_at.is_(None)

    # Add search filter if provided
    if search:
        search_filter = or_(
            User.email.ilike(f"%{search}%"),
        )
        base_filter = base_filter & search_filter

    # Get total count
    count_stmt = select(func.count(User.id)).where(base_filter)
    count_result = await session.execute(count_stmt)
    total = count_result.scalar() or 0

    # Get paginated users
    stmt = (
        select(User)
        .options(selectinload(User.role))
        .where(base_filter)
        .order_by(User.email.asc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    users = result.scalars().all()

    return users, total

async def update_provider_config(provider_name: str, enabled: bool, config: dict, session: AsyncSession):
    result = await session.execute(select(AuthProvider).where(AuthProvider.provider_name == provider_name))
    provider = result.scalar_one_or_none()
    
    if not provider:
        # Create if not exists? Or raise error?
        # Usually providers are pre-seeded or created by admin.
        # Let's create if not exists.
        provider = AuthProvider(provider_name=provider_name)
        session.add(provider)
    
    provider.enabled = enabled
    provider.config = config
    await session.commit()
    return provider

async def update_user_status(user_id: uuid.UUID, is_active: bool, role_id: uuid.UUID, session: AsyncSession):
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.is_active = is_active
    user.role_id = role_id
    
    # Revoke all tokens on status/role change
    user.token_version = int(user.token_version) + 1
    
    await session.commit()
    return user

async def delete_user(user_id: uuid.UUID, session: AsyncSession):
    """Soft delete a user by setting deleted_at timestamp."""
    from datetime import datetime, timezone

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Soft delete - set deleted_at instead of hard delete
    user.deleted_at = datetime.now(timezone.utc)
    user.is_active = False
    # Revoke all tokens
    user.token_version = int(user.token_version) + 1

    await session.commit()
    return True
