from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from src.api.db.database import get_session
from src.api.db_models import Role
from src.api.schemas.role_schemas import RoleCreate, RoleResponse, RoleUpdate
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

@router.post("/", response_model=RoleResponse)
async def create_role(role: RoleCreate, session: AsyncSession = Depends(get_session)):
    """
    Create a new role.
    """
    new_role = Role(name=role.name)
    session.add(new_role)
    
    try:
        await session.commit()
        await session.refresh(new_role)
        return {"id": str(new_role.id), "name": new_role.name}
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role with this name already exists"
        )

@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(role_id: str, session: AsyncSession = Depends(get_session)):
    """
    Get a specific role by ID.
    """
    result = await session.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    return {"id": str(role.id), "name": role.name}

@router.put("/{role_id}", response_model=RoleResponse)
async def update_role(role_id: str, role_update: RoleUpdate, session: AsyncSession = Depends(get_session)):
    """
    Update a role.
    """
    result = await session.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    if role_update.name is not None:
        role.name = role_update.name
    
    try:
        await session.commit()
        await session.refresh(role)
        return {"id": str(role.id), "name": role.name}
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role with this name already exists"
        )

@router.delete("/{role_id}")
async def delete_role(role_id: str, session: AsyncSession = Depends(get_session)):
    """
    Delete a role.
    """
    result = await session.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    await session.delete(role)
    await session.commit()
    
    return {"message": "Role deleted successfully"}
