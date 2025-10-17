# / -> Get All Role names + ids

# /health -> Health Check

# /create -> Create new Role
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from src.api.db.session import get_session
from src.api.db.models import Role
from src.api.schemas.role_schemas import RoleResponse
from typing import List

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/", response_model=List[RoleResponse])
async def get_roles(session: AsyncSession = Depends(get_session)):
    """
    Get all roles.
    """
    result = await session.execute(select(Role))
    roles = result.scalars().all()
    return [{"id": str(role.id), "name": role.name} for role in roles]