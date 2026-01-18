"""Roles router - provides role management endpoints."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.api.auth.dependencies import get_current_user
from src.api.db.models import Role
from src.api.db.session import get_session
from src.api.schemas.role_schemas import RoleResponse

router = APIRouter()


@router.get("/", response_model=List[RoleResponse])
async def get_roles(
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """Get all roles."""
    result = await session.execute(select(Role))
    roles = result.scalars().all()
    return [{"id": str(role.id), "name": role.name} for role in roles]