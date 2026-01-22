"""Roles router - provides role management endpoints."""

from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.api.auth.dependencies import get_current_user, require_permission, require_any_permission
from src.api.db.models import Role, PermissionSet, RolePermissionSet
from src.api.db.session import get_session
from src.api.schemas.role_schemas import RoleResponse, RoleCreate, RoleUpdate, RoleDetailResponse

router = APIRouter()


@router.get("/", response_model=List[RoleResponse])
async def get_roles(
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user)
):
    """Get all roles."""
    result = await session.execute(select(Role).where(Role.deleted_at.is_(None)))
    roles = result.scalars().all()
    return [
        {
            "id": str(role.id),
            "name": role.name,
            "description": role.description,
        }
        for role in roles
    ]


@router.get("/{role_id}", response_model=RoleDetailResponse)
async def get_role(
    role_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_permission("role.view"))
):
    """Get a role with its permission sets."""
    result = await session.execute(
        select(Role)
        .options(selectinload(Role.role_permission_sets).selectinload(RolePermissionSet.permission_set))
        .where(Role.id == role_id, Role.deleted_at.is_(None))
    )
    role = result.scalar_one_or_none()

    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    permission_sets = []
    if hasattr(role, 'role_permission_sets'):
        for rps in role.role_permission_sets:
            if rps.permission_set:
                permission_sets.append({
                    "id": str(rps.permission_set.id),
                    "code": rps.permission_set.code,
                    "name": rps.permission_set.name,
                })

    return {
        "id": str(role.id),
        "name": role.name,
        "description": role.description,
        "permission_sets": permission_sets,
    }


@router.post("/", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_permission("role.create"))
):
    """Create a new role."""
    # Check if role name already exists
    result = await session.execute(
        select(Role).where(Role.name == role_data.name, Role.deleted_at.is_(None))
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Role with this name already exists")

    # Verify permission sets exist if provided
    if role_data.permission_set_ids:
        ps_result = await session.execute(
            select(PermissionSet).where(
                PermissionSet.id.in_(role_data.permission_set_ids),
                PermissionSet.deleted_at.is_(None)
            )
        )
        found_sets = ps_result.scalars().all()
        if len(found_sets) != len(role_data.permission_set_ids):
            raise HTTPException(status_code=400, detail="One or more permission sets not found")

    # Create the role
    new_role = Role(
        name=role_data.name,
        description=role_data.description,
    )
    session.add(new_role)
    await session.flush()

    # Add permission sets if provided
    for ps_id in role_data.permission_set_ids or []:
        rps = RolePermissionSet(role_id=new_role.id, permission_set_id=ps_id)
        session.add(rps)

    await session.commit()
    await session.refresh(new_role)

    return {
        "id": str(new_role.id),
        "name": new_role.name,
        "description": new_role.description,
    }


@router.put("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: UUID,
    role_data: RoleUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_permission("role.edit"))
):
    """Update an existing role."""
    result = await session.execute(
        select(Role).where(Role.id == role_id, Role.deleted_at.is_(None))
    )
    role = result.scalar_one_or_none()

    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    # Check if new name conflicts with existing role
    if role_data.name and role_data.name != role.name:
        name_check = await session.execute(
            select(Role).where(
                Role.name == role_data.name,
                Role.id != role_id,
                Role.deleted_at.is_(None)
            )
        )
        if name_check.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Role with this name already exists")
        role.name = role_data.name

    if role_data.description is not None:
        role.description = role_data.description

    # Update permission sets if provided
    if role_data.permission_set_ids is not None:
        # Verify permission sets exist
        if role_data.permission_set_ids:
            ps_result = await session.execute(
                select(PermissionSet).where(
                    PermissionSet.id.in_(role_data.permission_set_ids),
                    PermissionSet.deleted_at.is_(None)
                )
            )
            found_sets = ps_result.scalars().all()
            if len(found_sets) != len(role_data.permission_set_ids):
                raise HTTPException(status_code=400, detail="One or more permission sets not found")

        # Remove existing permission sets
        await session.execute(
            delete(RolePermissionSet).where(RolePermissionSet.role_id == role_id)
        )

        # Add new permission sets
        for ps_id in role_data.permission_set_ids:
            rps = RolePermissionSet(role_id=role_id, permission_set_id=ps_id)
            session.add(rps)

    role.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(role)

    return {
        "id": str(role.id),
        "name": role.name,
        "description": role.description,
    }


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_permission("role.delete"))
):
    """Soft delete a role."""
    result = await session.execute(
        select(Role).where(Role.id == role_id, Role.deleted_at.is_(None))
    )
    role = result.scalar_one_or_none()

    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    role.deleted_at = datetime.utcnow()
    await session.commit()
    return None