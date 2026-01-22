from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func, or_, delete
from fastapi import HTTPException
from ..db.models import AuthProvider, User, Role, UserRole
from ..auth.service import revoke_all_user_tokens
from typing import Optional, Tuple, List
import uuid
from datetime import datetime


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

    # Get paginated users with roles (both legacy and new multi-role)
    stmt = (
        select(User)
        .options(
            selectinload(User.role),  # Legacy single role
            selectinload(User.user_roles).selectinload(UserRole.role)  # New multi-role
        )
        .where(base_filter)
        .order_by(User.email.asc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    users = result.scalars().all()

    return users, total


async def get_user_roles(user_id: uuid.UUID, session: AsyncSession) -> List[Role]:
    """Get all roles assigned to a user."""
    stmt = (
        select(UserRole)
        .options(selectinload(UserRole.role))
        .where(UserRole.user_id == user_id)
    )
    result = await session.execute(stmt)
    user_roles = result.scalars().all()
    return [ur.role for ur in user_roles if ur.role]


async def assign_role_to_user(
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    assigned_by: Optional[uuid.UUID],
    session: AsyncSession
) -> bool:
    """Assign a role to a user. Returns True if newly assigned, False if already had role."""
    # Check if user exists
    user_stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    user_result = await session.execute(user_stmt)
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if role exists
    role_stmt = select(Role).where(Role.id == role_id)
    role_result = await session.execute(role_stmt)
    role = role_result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    # Check if already assigned
    existing_stmt = select(UserRole).where(
        UserRole.user_id == user_id,
        UserRole.role_id == role_id
    )
    existing_result = await session.execute(existing_stmt)
    if existing_result.scalar_one_or_none():
        return False  # Already assigned

    # Create new assignment
    user_role = UserRole(
        user_id=user_id,
        role_id=role_id,
        assigned_at=datetime.utcnow(),
        assigned_by=assigned_by
    )
    session.add(user_role)

    # Increment token version to invalidate existing tokens (permissions changed)
    user.token_version = int(user.token_version) + 1

    await session.commit()
    return True


async def remove_role_from_user(user_id: uuid.UUID, role_id: uuid.UUID, session: AsyncSession) -> bool:
    """Remove a role from a user. Returns True if removed, False if not found."""
    # Check if user exists
    user_stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    user_result = await session.execute(user_stmt)
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Remove the assignment
    delete_stmt = delete(UserRole).where(
        UserRole.user_id == user_id,
        UserRole.role_id == role_id
    )
    result = await session.execute(delete_stmt)

    if result.rowcount == 0:
        return False

    # Increment token version to invalidate existing tokens (permissions changed)
    user.token_version = int(user.token_version) + 1

    await session.commit()
    return True


async def set_user_roles(
    user_id: uuid.UUID,
    role_ids: List[uuid.UUID],
    assigned_by: Optional[uuid.UUID],
    session: AsyncSession
) -> List[Role]:
    """Replace all roles for a user with the provided list of roles."""
    # Check if user exists
    user_stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    user_result = await session.execute(user_stmt)
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify all roles exist
    if role_ids:
        roles_stmt = select(Role).where(Role.id.in_(role_ids))
        roles_result = await session.execute(roles_stmt)
        roles = roles_result.scalars().all()
        if len(roles) != len(role_ids):
            raise HTTPException(status_code=400, detail="One or more roles not found")
    else:
        roles = []

    # Remove all existing role assignments
    delete_stmt = delete(UserRole).where(UserRole.user_id == user_id)
    await session.execute(delete_stmt)

    # Add new role assignments
    for role_id in role_ids:
        user_role = UserRole(
            user_id=user_id,
            role_id=role_id,
            assigned_at=datetime.utcnow(),
            assigned_by=assigned_by
        )
        session.add(user_role)

    # Increment token version to invalidate existing tokens (permissions changed)
    user.token_version = int(user.token_version) + 1

    await session.commit()
    return roles

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
    from datetime import datetime

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Soft delete - set deleted_at instead of hard delete
    user.deleted_at = datetime.utcnow()
    user.is_active = False
    # Revoke all tokens
    user.token_version = int(user.token_version) + 1

    await session.commit()
    return True
