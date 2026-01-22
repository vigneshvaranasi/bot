from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.session import get_session
from ..auth.dependencies import require_permission, get_current_user
from .service import (
    update_provider_config,
    update_user_status,
    get_paginated_users,
    delete_user,
    get_user_roles,
    assign_role_to_user,
    remove_role_from_user,
    set_user_roles,
)
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


class UserRolesUpdate(BaseModel):
    """Update user roles (replace all roles)."""
    role_ids: List[uuid.UUID]


class UserRoleAssign(BaseModel):
    """Assign a single role to a user."""
    role_id: uuid.UUID


class UserRoleResponse(BaseModel):
    role_id: uuid.UUID
    role_name: str
    assigned_at: Optional[str] = None


class AdminUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    is_active: bool
    role_id: Optional[uuid.UUID] = None  # Legacy field, may be None
    role_name: Optional[str] = None  # Legacy field
    roles: List[UserRoleResponse] = []  # New multi-role field


class PaginatedUsersResponse(BaseModel):
    users: List[AdminUserResponse]
    total: int
    limit: int
    offset: int
    has_more: bool

@router.get("/users", response_model=PaginatedUsersResponse)
async def list_users(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_permission("user.view"))
):
    """Get paginated list of users with optional search."""
    users, total = await get_paginated_users(session, limit, offset, search)
    user_list = []
    for user in users:
        # Build roles list from user_roles (new multi-role system)
        roles = []
        for ur in user.user_roles:
            if ur.role:
                roles.append(UserRoleResponse(
                    role_id=ur.role_id,
                    role_name=ur.role.name,
                    assigned_at=ur.assigned_at.isoformat() if ur.assigned_at else None
                ))

        # Legacy role info (for backward compatibility)
        legacy_role_id = user.role_id
        legacy_role_name = user.role.name if user.role else None

        # If no roles in new system but has legacy role, include it
        if not roles and legacy_role_id and user.role:
            roles.append(UserRoleResponse(
                role_id=legacy_role_id,
                role_name=user.role.name,
                assigned_at=None
            ))

        user_list.append(AdminUserResponse(
            id=user.id,
            email=user.email,
            is_active=user.is_active,
            role_id=legacy_role_id,
            role_name=legacy_role_name,
            roles=roles
        ))

    return PaginatedUsersResponse(
        users=user_list,
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(user_list) < total
    )

@router.put("/providers/{provider_name}")
async def update_provider(
    provider_name: str,
    data: ProviderUpdate,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_permission("auth.edit"))
):
    await update_provider_config(provider_name, data.enabled, data.config, session)
    return {"message": "Provider updated"}

@router.put("/users/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_permission("user.edit"))
):
    await update_user_status(user_id, data.is_active, data.role_id, session)
    return {"message": "User updated"}


@router.get("/users/{user_id}/roles")
async def get_user_roles_endpoint(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_permission("user.view"))
):
    """Get all roles assigned to a user."""
    roles = await get_user_roles(user_id, session)
    return {
        "status": "success",
        "user_id": str(user_id),
        "roles": [
            {"role_id": str(r.id), "role_name": r.name}
            for r in roles
        ]
    }


@router.put("/users/{user_id}/roles")
async def update_user_roles(
    user_id: uuid.UUID,
    data: UserRolesUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
    admin: dict = Depends(require_permission("user.edit"))
):
    """Replace all roles for a user."""
    assigned_by = uuid.UUID(current_user["user_id"]) if current_user else None
    roles = await set_user_roles(user_id, data.role_ids, assigned_by, session)
    return {
        "status": "success",
        "message": "User roles updated",
        "roles": [{"role_id": str(r.id), "role_name": r.name} for r in roles]
    }


@router.post("/users/{user_id}/roles")
async def add_user_role(
    user_id: uuid.UUID,
    data: UserRoleAssign,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
    admin: dict = Depends(require_permission("user.edit"))
):
    """Assign a role to a user."""
    assigned_by = uuid.UUID(current_user["user_id"]) if current_user else None
    is_new = await assign_role_to_user(user_id, data.role_id, assigned_by, session)
    return {
        "status": "success",
        "message": "Role assigned" if is_new else "Role already assigned"
    }


@router.delete("/users/{user_id}/roles/{role_id}")
async def remove_user_role(
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_permission("user.edit"))
):
    """Remove a role from a user."""
    removed = await remove_role_from_user(user_id, role_id, session)
    if not removed:
        raise HTTPException(status_code=404, detail="Role not assigned to user")
    return {"status": "success", "message": "Role removed"}


@router.delete("/users/{user_id}")
async def remove_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_permission("user.delete"))
):
    await delete_user(user_id, session)
    return {"message": "User deleted"}
