from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.session import get_session
from ..auth.dependencies import require_role
from .service import update_provider_config, update_user_status, get_all_users, delete_user
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import uuid

router = APIRouter()

class ProviderUpdate(BaseModel):
    enabled: bool
    config: Dict[str, Any]

class UserUpdate(BaseModel):
    is_active: bool
    role_id: uuid.UUID

class AdminUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    is_active: bool
    role_id: uuid.UUID
    role_name: str

@router.get("/users", response_model=List[AdminUserResponse])
async def list_users(
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_role("admin"))
):
    users = await get_all_users(session)
    return [
        AdminUserResponse(
            id=user.id,
            email=user.email,
            is_active=user.is_active,
            role_id=user.role_id,
            role_name=user.role.name if user.role else "None"
        )
        for user in users
    ]

@router.put("/providers/{provider_name}")
async def update_provider(
    provider_name: str, 
    data: ProviderUpdate, 
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_role("admin"))
):
    await update_provider_config(provider_name, data.enabled, data.config, session)
    return {"message": "Provider updated"}

@router.put("/users/{user_id}")
async def update_user(
    user_id: uuid.UUID, 
    data: UserUpdate, 
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_role("admin"))
):
    await update_user_status(user_id, data.is_active, data.role_id, session)
    return {"message": "User updated"}

@router.delete("/users/{user_id}")
async def remove_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_role("admin"))
):
    await delete_user(user_id, session)
    return {"message": "User deleted"}
