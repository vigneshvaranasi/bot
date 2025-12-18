from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
from ..db.models import AuthProvider, User, Role
from ..auth.service import revoke_all_user_tokens
import uuid

async def get_all_users(session: AsyncSession):
    stmt = select(User).options(
        selectinload(User.role)
    )
    result = await session.execute(stmt)
    users = result.scalars().all()
    return users

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
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    await session.delete(user)
    await session.commit()
    return True
