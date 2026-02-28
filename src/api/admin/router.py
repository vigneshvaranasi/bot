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
from ..services import permission_service
from ..services import audit_service
from ..schemas.permission_schemas import (
    UserDirectPermissionAssignment,
    UserDirectPermissionsUpdate,
    UserDirectPermissionResponse,
    UserDirectPermissionsResponse,
    UserDirectPermissionSetAssignment,
    UserDirectPermissionSetsUpdate,
    UserDirectPermissionSetResponse,
    UserDirectPermissionSetsResponse,
    UserEffectivePermissionsDetailedResponse,
    RbacAuditLogResponse,
    RbacAuditLogsResponse,
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
    current_user: dict = Depends(get_current_user),
    admin: dict = Depends(require_permission("user.edit"))
):
    """Remove a role from a user."""
    removed_by = uuid.UUID(current_user["user_id"]) if current_user else None
    removed = await remove_role_from_user(user_id, role_id, session, removed_by)
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


# ==================== Direct User Permission Endpoints ====================

@router.get("/users/{user_id}/permissions/direct", response_model=UserDirectPermissionsResponse)
async def get_user_direct_permissions(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_permission("user.view"))
):
    """Get all permissions directly assigned to a user (bypassing roles)."""
    direct_perms = await permission_service.get_user_direct_permissions(user_id, session)
    return UserDirectPermissionsResponse(
        user_id=user_id,
        direct_permissions=[
            UserDirectPermissionResponse(
                permission_id=up.permission_id,
                permission_code=up.permission.code,
                permission_name=up.permission.name,
                assigned_at=up.assigned_at,
                assigned_by=up.assigned_by
            )
            for up in direct_perms
        ]
    )


@router.put("/users/{user_id}/permissions/direct", response_model=UserDirectPermissionsResponse)
async def update_user_direct_permissions(
    user_id: uuid.UUID,
    data: UserDirectPermissionsUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
    admin: dict = Depends(require_permission("user.edit"))
):
    """Replace all direct permissions for a user."""
    assigned_by = uuid.UUID(current_user["user_id"]) if current_user else None
    await permission_service.set_user_direct_permissions(user_id, data.permission_ids, assigned_by, session)
    # Fetch updated list
    direct_perms = await permission_service.get_user_direct_permissions(user_id, session)
    return UserDirectPermissionsResponse(
        user_id=user_id,
        direct_permissions=[
            UserDirectPermissionResponse(
                permission_id=up.permission_id,
                permission_code=up.permission.code,
                permission_name=up.permission.name,
                assigned_at=up.assigned_at,
                assigned_by=up.assigned_by
            )
            for up in direct_perms
        ]
    )


@router.post("/users/{user_id}/permissions/direct")
async def add_user_direct_permission(
    user_id: uuid.UUID,
    data: UserDirectPermissionAssignment,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
    admin: dict = Depends(require_permission("user.edit"))
):
    """Assign a permission directly to a user."""
    assigned_by = uuid.UUID(current_user["user_id"]) if current_user else None
    await permission_service.assign_permission_to_user(user_id, data.permission_id, assigned_by, session)
    return {"status": "success", "message": "Permission assigned directly to user"}


@router.delete("/users/{user_id}/permissions/direct/{permission_id}")
async def remove_user_direct_permission(
    user_id: uuid.UUID,
    permission_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_permission("user.edit"))
):
    """Remove a direct permission from a user."""
    removed = await permission_service.remove_permission_from_user(user_id, permission_id, session)
    if not removed:
        raise HTTPException(status_code=404, detail="Permission not directly assigned to user")
    return {"status": "success", "message": "Direct permission removed"}


# ==================== Direct User Permission Set Endpoints ====================

@router.get("/users/{user_id}/permission-sets/direct", response_model=UserDirectPermissionSetsResponse)
async def get_user_direct_permission_sets(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_permission("user.view"))
):
    """Get all permission sets directly assigned to a user (bypassing roles)."""
    direct_sets = await permission_service.get_user_direct_permission_sets(user_id, session)
    return UserDirectPermissionSetsResponse(
        user_id=user_id,
        direct_permission_sets=[
            UserDirectPermissionSetResponse(
                permission_set_id=ups.permission_set_id,
                permission_set_code=ups.permission_set.code,
                permission_set_name=ups.permission_set.name,
                assigned_at=ups.assigned_at,
                assigned_by=ups.assigned_by
            )
            for ups in direct_sets
        ]
    )


@router.put("/users/{user_id}/permission-sets/direct", response_model=UserDirectPermissionSetsResponse)
async def update_user_direct_permission_sets(
    user_id: uuid.UUID,
    data: UserDirectPermissionSetsUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
    admin: dict = Depends(require_permission("user.edit"))
):
    """Replace all direct permission sets for a user."""
    assigned_by = uuid.UUID(current_user["user_id"]) if current_user else None
    await permission_service.set_user_direct_permission_sets(user_id, data.permission_set_ids, assigned_by, session)
    # Fetch updated list
    direct_sets = await permission_service.get_user_direct_permission_sets(user_id, session)
    return UserDirectPermissionSetsResponse(
        user_id=user_id,
        direct_permission_sets=[
            UserDirectPermissionSetResponse(
                permission_set_id=ups.permission_set_id,
                permission_set_code=ups.permission_set.code,
                permission_set_name=ups.permission_set.name,
                assigned_at=ups.assigned_at,
                assigned_by=ups.assigned_by
            )
            for ups in direct_sets
        ]
    )


@router.post("/users/{user_id}/permission-sets/direct")
async def add_user_direct_permission_set(
    user_id: uuid.UUID,
    data: UserDirectPermissionSetAssignment,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
    admin: dict = Depends(require_permission("user.edit"))
):
    """Assign a permission set directly to a user."""
    assigned_by = uuid.UUID(current_user["user_id"]) if current_user else None
    await permission_service.assign_permission_set_to_user(user_id, data.permission_set_id, assigned_by, session)
    return {"status": "success", "message": "Permission set assigned directly to user"}


@router.delete("/users/{user_id}/permission-sets/direct/{permission_set_id}")
async def remove_user_direct_permission_set(
    user_id: uuid.UUID,
    permission_set_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_permission("user.edit"))
):
    """Remove a direct permission set from a user."""
    removed = await permission_service.remove_permission_set_from_user(user_id, permission_set_id, session)
    if not removed:
        raise HTTPException(status_code=404, detail="Permission set not directly assigned to user")
    return {"status": "success", "message": "Direct permission set removed"}


# ==================== Effective Permissions Endpoint ====================

@router.get("/users/{user_id}/permissions/effective", response_model=UserEffectivePermissionsDetailedResponse)
async def get_user_effective_permissions_detailed(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_permission("user.view"))
):
    """Get user's effective permissions with breakdown by source."""
    detailed = await permission_service.get_user_permissions_detailed(user_id, session)
    return UserEffectivePermissionsDetailedResponse(
        user_id=user_id,
        from_roles=detailed["from_roles"],
        from_direct_sets=detailed["from_direct_sets"],
        from_direct_permissions=detailed["from_direct_permissions"],
        effective=detailed["effective"]
    )


# ==================== RBAC Audit Log Endpoints ====================

@router.get("/rbac/audit-logs", response_model=RbacAuditLogsResponse)
async def list_rbac_audit_logs(
    entity_type: Optional[str] = Query(default=None, description="Filter by entity type"),
    entity_id: Optional[uuid.UUID] = Query(default=None, description="Filter by entity ID"),
    action: Optional[str] = Query(default=None, description="Filter by action"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_permission("history.view"))
):
    """List RBAC audit logs with optional filters."""
    logs, total = await audit_service.get_audit_logs(
        session=session,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        limit=limit,
        offset=offset
    )
    return RbacAuditLogsResponse(
        audit_logs=[
            RbacAuditLogResponse(
                id=log.id,
                entity_type=log.entity_type,
                entity_id=log.entity_id,
                secondary_entity_id=log.secondary_entity_id,
                action=log.action,
                old_value=log.old_value,
                new_value=log.new_value,
                changed_by=log.changed_by,
                changed_at=log.changed_at,
                ip_address=log.ip_address
            )
            for log in logs
        ],
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/rbac/audit-logs/{entity_type}/{entity_id}")
async def get_rbac_entity_history(
    entity_type: str,
    entity_id: uuid.UUID,
    secondary_entity_id: Optional[uuid.UUID] = Query(default=None),
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_permission("history.view"))
):
    """Get complete audit history for a specific RBAC entity."""
    logs = await audit_service.get_entity_history(
        session=session,
        entity_type=entity_type,
        entity_id=entity_id,
        secondary_entity_id=secondary_entity_id
    )
    return {
        "status": "success",
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "history": [
            {
                "id": str(log.id),
                "action": log.action,
                "old_value": log.old_value,
                "new_value": log.new_value,
                "changed_by": str(log.changed_by) if log.changed_by else None,
                "changed_at": log.changed_at.isoformat()
            }
            for log in logs
        ]
    }


@router.get("/users/{user_id}/rbac-history")
async def get_user_rbac_history(
    user_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    admin: dict = Depends(require_permission("history.view"))
):
    """Get all RBAC changes related to a specific user."""
    logs = await audit_service.get_user_rbac_history(
        session=session,
        user_id=user_id,
        limit=limit,
        offset=offset
    )
    return {
        "status": "success",
        "user_id": str(user_id),
        "history": [
            {
                "id": str(log.id),
                "entity_type": log.entity_type,
                "action": log.action,
                "old_value": log.old_value,
                "new_value": log.new_value,
                "changed_by": str(log.changed_by) if log.changed_by else None,
                "changed_at": log.changed_at.isoformat()
            }
            for log in logs
        ]
    }
