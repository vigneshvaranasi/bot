"""Permissions router for RBAC management.

This router provides endpoints for managing:
- Permissions (read-only, system-defined)
- Permission Sets (CRUD for custom sets)
- Roles (CRUD for custom roles)
- User role assignments
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import logging

from ..db.session import get_session
from ..auth.dependencies import (
    get_current_user,
    require_permission,
)
from ..services import permission_service
from ..schemas.permission_schemas import (
    PermissionResponse,
    PermissionListResponse,
    PermissionCategoryResponse,
    PermissionSetCreate,
    PermissionSetUpdate,
    PermissionSetResponse,
    PermissionSetListResponse,
    PermissionSetBriefResponse,
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    RoleListResponse,
    RoleEffectivePermissionsResponse,
    UserEffectivePermissionsResponse,
)

router = APIRouter(prefix="/permissions", tags=["permissions"])
logger = logging.getLogger(__name__)


# ==================== Permission Endpoints ====================

@router.get("", response_model=PermissionListResponse)
async def list_permissions(
    user: dict = Depends(require_permission("permission_set.view")),
    session: AsyncSession = Depends(get_session),
):
    """List all permissions (system-defined)."""
    permissions = await permission_service.get_all_permissions(session)
    return PermissionListResponse(
        permissions=[
            PermissionResponse(
                id=p.id,
                code=p.code,
                name=p.name,
                description=p.description,
                category=p.category,
                is_system=p.is_system,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in permissions
        ]
    )


@router.get("/categories", response_model=PermissionCategoryResponse)
async def list_permission_categories(
    user: dict = Depends(require_permission("permission_set.view")),
    session: AsyncSession = Depends(get_session),
):
    """List all permission categories."""
    categories = await permission_service.get_permission_categories(session)
    return PermissionCategoryResponse(categories=categories)


@router.get("/me", response_model=UserEffectivePermissionsResponse)
async def get_my_permissions(
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get current user's effective permissions."""
    user_id = UUID(user["user_id"])
    permissions = await permission_service.get_user_permissions(user_id, session)
    return UserEffectivePermissionsResponse(
        user_id=user_id,
        permissions=list(permissions),
    )


# ==================== Permission Set Endpoints ====================

@router.get("/sets", response_model=PermissionSetListResponse)
async def list_permission_sets(
    user: dict = Depends(require_permission("permission_set.view")),
    session: AsyncSession = Depends(get_session),
):
    """List all permission sets."""
    permission_sets = await permission_service.get_all_permission_sets(session)
    return PermissionSetListResponse(
        permission_sets=[
            PermissionSetResponse(
                id=ps.id,
                code=ps.code,
                name=ps.name,
                description=ps.description,
                                created_at=ps.created_at,
                updated_at=ps.updated_at,
                permissions=[
                    PermissionResponse(
                        id=psp.permission.id,
                        code=psp.permission.code,
                        name=psp.permission.name,
                        description=psp.permission.description,
                        category=psp.permission.category,
                        is_system=psp.permission.is_system,
                        created_at=psp.permission.created_at,
                        updated_at=psp.permission.updated_at,
                    )
                    for psp in ps.permission_set_permissions
                    if psp.permission.deleted_at is None
                ],
            )
            for ps in permission_sets
        ]
    )


@router.post("/sets", response_model=PermissionSetResponse, status_code=status.HTTP_201_CREATED)
async def create_permission_set(
    data: PermissionSetCreate,
    user: dict = Depends(require_permission("permission_set.create")),
    session: AsyncSession = Depends(get_session),
):
    """Create a new permission set."""
    # Check if code already exists
    existing = await permission_service.get_permission_set_by_code(data.code, session)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Permission set with code '{data.code}' already exists",
        )

    try:
        ps = await permission_service.create_permission_set(
            code=data.code,
            name=data.name,
            permission_codes=data.permission_codes,
            description=data.description,
            session=session,
        )
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Permission set with code '{data.code}' already exists",
        )

    # Reload with permissions
    ps = await permission_service.get_permission_set_by_id(ps.id, session)
    return PermissionSetResponse(
        id=ps.id,
        code=ps.code,
        name=ps.name,
        description=ps.description,
                created_at=ps.created_at,
        updated_at=ps.updated_at,
        permissions=[
            PermissionResponse(
                id=psp.permission.id,
                code=psp.permission.code,
                name=psp.permission.name,
                description=psp.permission.description,
                category=psp.permission.category,
                is_system=psp.permission.is_system,
            )
            for psp in ps.permission_set_permissions
        ],
    )


@router.get("/sets/{id}", response_model=PermissionSetResponse)
async def get_permission_set(
    id: UUID,
    user: dict = Depends(require_permission("permission_set.view")),
    session: AsyncSession = Depends(get_session),
):
    """Get a permission set by ID."""
    ps = await permission_service.get_permission_set_by_id(id, session)
    if not ps:
        raise HTTPException(status_code=404, detail="Permission set not found")

    return PermissionSetResponse(
        id=ps.id,
        code=ps.code,
        name=ps.name,
        description=ps.description,
                created_at=ps.created_at,
        updated_at=ps.updated_at,
        permissions=[
            PermissionResponse(
                id=psp.permission.id,
                code=psp.permission.code,
                name=psp.permission.name,
                description=psp.permission.description,
                category=psp.permission.category,
                is_system=psp.permission.is_system,
            )
            for psp in ps.permission_set_permissions
        ],
    )


@router.put("/sets/{id}", response_model=PermissionSetResponse)
async def update_permission_set(
    id: UUID,
    data: PermissionSetUpdate,
    user: dict = Depends(require_permission("permission_set.edit")),
    session: AsyncSession = Depends(get_session),
):
    """Update a permission set."""
    try:
        ps = await permission_service.update_permission_set(
            id=id,
            name=data.name,
            description=data.description,
            permission_codes=data.permission_codes,
            session=session,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not ps:
        raise HTTPException(status_code=404, detail="Permission set not found")

    # Reload with permissions
    ps = await permission_service.get_permission_set_by_id(ps.id, session)
    return PermissionSetResponse(
        id=ps.id,
        code=ps.code,
        name=ps.name,
        description=ps.description,
                created_at=ps.created_at,
        updated_at=ps.updated_at,
        permissions=[
            PermissionResponse(
                id=psp.permission.id,
                code=psp.permission.code,
                name=psp.permission.name,
                description=psp.permission.description,
                category=psp.permission.category,
                is_system=psp.permission.is_system,
            )
            for psp in ps.permission_set_permissions
        ],
    )


@router.delete("/sets/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_permission_set(
    id: UUID,
    user: dict = Depends(require_permission("permission_set.delete")),
    session: AsyncSession = Depends(get_session),
):
    """Delete a permission set."""
    try:
        deleted = await permission_service.delete_permission_set(id, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not deleted:
        raise HTTPException(status_code=404, detail="Permission set not found")


# ==================== Role Endpoints ====================

@router.get("/roles", response_model=RoleListResponse)
async def list_roles(
    user: dict = Depends(require_permission("role.view")),
    session: AsyncSession = Depends(get_session),
):
    """List all roles."""
    roles = await permission_service.get_all_roles(session)
    return RoleListResponse(
        roles=[
            RoleResponse(
                id=r.id,
                name=r.name,
                description=r.description,
                                created_at=r.created_at,
                updated_at=r.updated_at,
                permission_sets=[
                    PermissionSetBriefResponse(
                        id=rps.permission_set.id,
                        code=rps.permission_set.code,
                        name=rps.permission_set.name,
                        description=rps.permission_set.description,
                                            )
                    for rps in r.role_permission_sets
                    if rps.permission_set.deleted_at is None
                ],
            )
            for r in roles
        ]
    )


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    data: RoleCreate,
    user: dict = Depends(require_permission("role.create")),
    session: AsyncSession = Depends(get_session),
):
    """Create a new role."""
    # Check if name already exists
    existing = await permission_service.get_role_by_name(data.name, session)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role with name '{data.name}' already exists",
        )

    try:
        role = await permission_service.create_role(
            name=data.name,
            permission_set_codes=data.permission_set_codes,
            description=data.description,
            session=session,
        )
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role with name '{data.name}' already exists",
        )

    # Reload with permission sets
    role = await permission_service.get_role_by_id(role.id, session)
    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
                created_at=role.created_at,
        updated_at=role.updated_at,
        permission_sets=[
            PermissionSetBriefResponse(
                id=rps.permission_set.id,
                code=rps.permission_set.code,
                name=rps.permission_set.name,
                description=rps.permission_set.description,
                            )
            for rps in role.role_permission_sets
        ],
    )


@router.get("/roles/{id}", response_model=RoleResponse)
async def get_role(
    id: UUID,
    user: dict = Depends(require_permission("role.view")),
    session: AsyncSession = Depends(get_session),
):
    """Get a role by ID."""
    role = await permission_service.get_role_by_id(id, session)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
                created_at=role.created_at,
        updated_at=role.updated_at,
        permission_sets=[
            PermissionSetBriefResponse(
                id=rps.permission_set.id,
                code=rps.permission_set.code,
                name=rps.permission_set.name,
                description=rps.permission_set.description,
                            )
            for rps in role.role_permission_sets
        ],
    )


@router.put("/roles/{id}", response_model=RoleResponse)
async def update_role(
    id: UUID,
    data: RoleUpdate,
    user: dict = Depends(require_permission("role.edit")),
    session: AsyncSession = Depends(get_session),
):
    """Update a role."""
    try:
        role = await permission_service.update_role(
            id=id,
            name=data.name,
            description=data.description,
            permission_set_codes=data.permission_set_codes,
            session=session,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    # Reload with permission sets
    role = await permission_service.get_role_by_id(role.id, session)
    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
                created_at=role.created_at,
        updated_at=role.updated_at,
        permission_sets=[
            PermissionSetBriefResponse(
                id=rps.permission_set.id,
                code=rps.permission_set.code,
                name=rps.permission_set.name,
                description=rps.permission_set.description,
                            )
            for rps in role.role_permission_sets
        ],
    )


@router.delete("/roles/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    id: UUID,
    user: dict = Depends(require_permission("role.delete")),
    session: AsyncSession = Depends(get_session),
):
    """Delete a role."""
    try:
        deleted = await permission_service.delete_role(id, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not deleted:
        raise HTTPException(status_code=404, detail="Role not found")


@router.get("/roles/{id}/permissions", response_model=RoleEffectivePermissionsResponse)
async def get_role_effective_permissions(
    id: UUID,
    user: dict = Depends(require_permission("role.view")),
    session: AsyncSession = Depends(get_session),
):
    """Get all effective permissions for a role."""
    role = await permission_service.get_role_by_id(id, session)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    permissions = await permission_service.get_role_permissions(id, session)
    return RoleEffectivePermissionsResponse(
        role_id=role.id,
        role_name=role.name,
        permissions=list(permissions),
    )
