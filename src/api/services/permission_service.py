"""Permission service for RBAC operations.

This service provides functions to:
- Resolve user permissions from roles AND direct assignments
- CRUD operations for permissions, permission sets, and roles
- Direct user permission and permission set assignments
"""

import logging
from typing import List, Optional, Set
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from ..db.models import (
    Permission,
    PermissionSet,
    PermissionSetPermission,
    Role,
    RolePermissionSet,
    UserPermission,
    UserPermissionSet,
    UserRole,
)
from .audit_service import AuditAction, AuditEntityType, log_rbac_change

logger = logging.getLogger(__name__)


async def get_user_permissions(user_id: UUID, session: AsyncSession) -> Set[str]:
    """Get all permission codes for a user from ALL sources.

    Sources (UNION of all):
    1. Permissions from roles (Role -> PermissionSet -> Permission)
    2. Permissions from direct permission set assignments (User -> PermissionSet -> Permission)
    3. Permissions from direct permission assignments (User -> Permission)
    """
    # Source 1: Permissions via roles
    role_query = (
        select(Permission.code)
        .join(PermissionSetPermission, Permission.id == PermissionSetPermission.permission_id)
        .join(PermissionSet, PermissionSetPermission.permission_set_id == PermissionSet.id)
        .join(RolePermissionSet, RolePermissionSet.permission_set_id == PermissionSet.id)
        .join(UserRole, UserRole.role_id == RolePermissionSet.role_id)
        .where(UserRole.user_id == user_id)
        .where(Permission.deleted_at.is_(None))
    )
    role_result = await session.execute(role_query)
    from_roles = {row[0] for row in role_result.all()}

    # Source 2: Permissions via direct permission set assignments
    direct_set_query = (
        select(Permission.code)
        .join(PermissionSetPermission, Permission.id == PermissionSetPermission.permission_id)
        .join(PermissionSet, PermissionSetPermission.permission_set_id == PermissionSet.id)
        .join(UserPermissionSet, UserPermissionSet.permission_set_id == PermissionSet.id)
        .where(UserPermissionSet.user_id == user_id)
        .where(Permission.deleted_at.is_(None))
    )
    direct_set_result = await session.execute(direct_set_query)
    from_direct_sets = {row[0] for row in direct_set_result.all()}

    # Source 3: Direct permission assignments
    direct_perm_query = (
        select(Permission.code)
        .join(UserPermission, Permission.id == UserPermission.permission_id)
        .where(UserPermission.user_id == user_id)
        .where(Permission.deleted_at.is_(None))
    )
    direct_perm_result = await session.execute(direct_perm_query)
    from_direct_permissions = {row[0] for row in direct_perm_result.all()}

    return from_roles | from_direct_sets | from_direct_permissions


async def get_role_permissions(role_id: UUID, session: AsyncSession) -> Set[str]:
    """Get all permission codes for a role."""
    query = (
        select(Permission.code)
        .join(PermissionSetPermission, Permission.id == PermissionSetPermission.permission_id)
        .join(PermissionSet, PermissionSetPermission.permission_set_id == PermissionSet.id)
        .join(RolePermissionSet, RolePermissionSet.permission_set_id == PermissionSet.id)
        .where(RolePermissionSet.role_id == role_id)
        .where(Permission.deleted_at.is_(None))
    )
    result = await session.execute(query)
    return {row[0] for row in result.all()}


# ==================== Permission CRUD ====================

async def get_all_permissions(session: AsyncSession) -> List[Permission]:
    """Get all active permissions."""
    result = await session.execute(
        select(Permission)
        .where(Permission.deleted_at.is_(None))
        .order_by(Permission.category, Permission.code)
    )
    return list(result.scalars().all())


async def get_permission_by_code(code: str, session: AsyncSession) -> Optional[Permission]:
    """Get a permission by its code."""
    result = await session.execute(
        select(Permission)
        .where(Permission.code == code)
        .where(Permission.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def get_permission_by_id(id: UUID, session: AsyncSession) -> Optional[Permission]:
    """Get a permission by its ID."""
    result = await session.execute(
        select(Permission)
        .where(Permission.id == id)
        .where(Permission.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def get_permission_categories(session: AsyncSession) -> List[str]:
    """Get all unique permission categories."""
    result = await session.execute(
        select(Permission.category)
        .where(Permission.deleted_at.is_(None))
        .distinct()
        .order_by(Permission.category)
    )
    return [row[0] for row in result.fetchall()]


# ==================== Permission Set CRUD ====================

async def get_all_permission_sets(session: AsyncSession) -> List[PermissionSet]:
    """Get all active permission sets with their permissions."""
    result = await session.execute(
        select(PermissionSet)
        .where(PermissionSet.deleted_at.is_(None))
        .options(
            selectinload(PermissionSet.permission_set_permissions)
            .selectinload(PermissionSetPermission.permission)
        )
        .order_by(PermissionSet.name)
    )
    return list(result.scalars().all())


async def get_permission_set_by_id(id: UUID, session: AsyncSession) -> Optional[PermissionSet]:
    """Get a permission set by ID with its permissions."""
    result = await session.execute(
        select(PermissionSet)
        .where(PermissionSet.id == id)
        .where(PermissionSet.deleted_at.is_(None))
        .options(
            selectinload(PermissionSet.permission_set_permissions)
            .selectinload(PermissionSetPermission.permission)
        )
    )
    return result.scalar_one_or_none()


async def get_permission_set_by_code(code: str, session: AsyncSession) -> Optional[PermissionSet]:
    """Get a permission set by its code."""
    result = await session.execute(
        select(PermissionSet)
        .where(PermissionSet.code == code)
        .where(PermissionSet.deleted_at.is_(None))
        .options(
            selectinload(PermissionSet.permission_set_permissions)
            .selectinload(PermissionSetPermission.permission)
        )
    )
    return result.scalar_one_or_none()


async def create_permission_set(
    code: str,
    name: str,
    permission_codes: List[str],
    description: Optional[str] = None,
    session: AsyncSession = None
) -> PermissionSet:
    """Create a new permission set with specified permissions."""
    # Get permission IDs for the codes
    permissions_result = await session.execute(
        select(Permission)
        .where(Permission.code.in_(permission_codes))
        .where(Permission.deleted_at.is_(None))
    )
    permissions = list(permissions_result.scalars().all())

    # Create the permission set
    permission_set = PermissionSet(
        code=code,
        name=name,
        description=description,
    )
    session.add(permission_set)
    await session.flush()  # Get the ID

    # Add permissions to the set
    for perm in permissions:
        psp = PermissionSetPermission(
            permission_set_id=permission_set.id,
            permission_id=perm.id
        )
        session.add(psp)

    await session.commit()
    await session.refresh(permission_set)
    return permission_set


async def update_permission_set(
    id: UUID,
    name: Optional[str] = None,
    description: Optional[str] = None,
    permission_codes: Optional[List[str]] = None,
    session: AsyncSession = None
) -> Optional[PermissionSet]:
    """Update a permission set."""
    permission_set = await get_permission_set_by_id(id, session)
    if not permission_set:
        return None

    if name is not None:
        permission_set.name = name
    if description is not None:
        permission_set.description = description

    if permission_codes is not None:
        # Remove existing permissions
        await session.execute(
            text("DELETE FROM permission_set_permissions WHERE permission_set_id = :ps_id"),
            {"ps_id": str(id)}
        )

        # Add new permissions
        permissions_result = await session.execute(
            select(Permission)
            .where(Permission.code.in_(permission_codes))
            .where(Permission.deleted_at.is_(None))
        )
        permissions = list(permissions_result.scalars().all())

        for perm in permissions:
            psp = PermissionSetPermission(
                permission_set_id=permission_set.id,
                permission_id=perm.id
            )
            session.add(psp)

    await session.commit()
    await session.refresh(permission_set)
    return permission_set


async def delete_permission_set(id: UUID, session: AsyncSession) -> bool:
    """Soft delete a permission set."""
    permission_set = await get_permission_set_by_id(id, session)
    if not permission_set:
        return False

    from datetime import datetime, UTC
    permission_set.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    await session.commit()
    return True


# ==================== Role CRUD ====================

async def get_all_roles(session: AsyncSession) -> List[Role]:
    """Get all active roles with their permission sets."""
    result = await session.execute(
        select(Role)
        .where(Role.deleted_at.is_(None))
        .options(
            selectinload(Role.role_permission_sets)
            .selectinload(RolePermissionSet.permission_set)
        )
        .order_by(Role.name)
    )
    return list(result.scalars().all())


async def get_role_by_id(id: UUID, session: AsyncSession) -> Optional[Role]:
    """Get a role by ID with its permission sets."""
    result = await session.execute(
        select(Role)
        .where(Role.id == id)
        .where(Role.deleted_at.is_(None))
        .options(
            selectinload(Role.role_permission_sets)
            .selectinload(RolePermissionSet.permission_set)
        )
    )
    return result.scalar_one_or_none()


async def get_role_by_name(name: str, session: AsyncSession) -> Optional[Role]:
    """Get a role by name."""
    result = await session.execute(
        select(Role)
        .where(Role.name == name)
        .where(Role.deleted_at.is_(None))
        .options(
            selectinload(Role.role_permission_sets)
            .selectinload(RolePermissionSet.permission_set)
        )
    )
    return result.scalar_one_or_none()


async def create_role(
    name: str,
    permission_set_codes: List[str],
    description: Optional[str] = None,
    session: AsyncSession = None
) -> Role:
    """Create a new role with specified permission sets."""
    # Get permission set IDs for the codes
    ps_result = await session.execute(
        select(PermissionSet)
        .where(PermissionSet.code.in_(permission_set_codes))
        .where(PermissionSet.deleted_at.is_(None))
    )
    permission_sets = list(ps_result.scalars().all())

    # Create the role
    role = Role(
        name=name,
        description=description,
    )
    session.add(role)
    await session.flush()  # Get the ID

    # Add permission sets to the role
    for ps in permission_sets:
        rps = RolePermissionSet(
            role_id=role.id,
            permission_set_id=ps.id
        )
        session.add(rps)

    await session.commit()
    await session.refresh(role)
    return role


async def update_role(
    id: UUID,
    name: Optional[str] = None,
    description: Optional[str] = None,
    permission_set_codes: Optional[List[str]] = None,
    session: AsyncSession = None
) -> Optional[Role]:
    """Update a role."""
    role = await get_role_by_id(id, session)
    if not role:
        return None

    if name is not None:
        role.name = name
    if description is not None:
        role.description = description

    if permission_set_codes is not None:
        # Remove existing permission sets
        await session.execute(
            text("DELETE FROM role_permission_sets WHERE role_id = :role_id"),
            {"role_id": str(id)}
        )

        # Add new permission sets
        ps_result = await session.execute(
            select(PermissionSet)
            .where(PermissionSet.code.in_(permission_set_codes))
            .where(PermissionSet.deleted_at.is_(None))
        )
        permission_sets = list(ps_result.scalars().all())

        for ps in permission_sets:
            rps = RolePermissionSet(
                role_id=role.id,
                permission_set_id=ps.id
            )
            session.add(rps)

    await session.commit()
    await session.refresh(role)
    return role


async def delete_role(id: UUID, session: AsyncSession) -> bool:
    """Soft delete a role."""
    role = await get_role_by_id(id, session)
    if not role:
        return False

    from datetime import datetime, UTC
    role.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    await session.commit()
    return True


# ==================== Direct User Permission Management ====================

async def get_user_direct_permissions(user_id: UUID, session: AsyncSession) -> List[UserPermission]:
    """Get all permissions directly assigned to a user (bypassing roles)."""
    result = await session.execute(
        select(UserPermission)
        .where(UserPermission.user_id == user_id)
        .options(selectinload(UserPermission.permission))
    )
    return list(result.scalars().all())


async def assign_permission_to_user(
    user_id: UUID,
    permission_id: UUID,
    assigned_by: Optional[UUID] = None,
    session: AsyncSession = None
) -> UserPermission:
    """Assign a permission directly to a user (bypassing roles)."""
    # Check if already assigned
    result = await session.execute(
        select(UserPermission)
        .where(UserPermission.user_id == user_id)
        .where(UserPermission.permission_id == permission_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    # Get permission info for audit
    permission = await get_permission_by_id(permission_id, session)
    perm_code = permission.code if permission else "Unknown"

    user_permission = UserPermission(
        user_id=user_id,
        permission_id=permission_id,
        assigned_by=assigned_by
    )
    session.add(user_permission)

    # Audit log
    await log_rbac_change(
        session=session,
        entity_type=AuditEntityType.USER_PERMISSION,
        entity_id=user_id,
        secondary_entity_id=permission_id,
        action=AuditAction.ASSIGN,
        changed_by=assigned_by,
        new_value={"permission_id": str(permission_id), "permission_code": perm_code}
    )

    await session.commit()
    await session.refresh(user_permission)
    return user_permission


async def remove_permission_from_user(
    user_id: UUID,
    permission_id: UUID,
    session: AsyncSession,
    removed_by: Optional[UUID] = None
) -> bool:
    """Remove a direct permission assignment from a user."""
    result = await session.execute(
        select(UserPermission)
        .where(UserPermission.user_id == user_id)
        .where(UserPermission.permission_id == permission_id)
        .options(selectinload(UserPermission.permission))
    )
    user_permission = result.scalar_one_or_none()
    if not user_permission:
        return False

    perm_code = user_permission.permission.code if user_permission.permission else "Unknown"

    # Audit log
    await log_rbac_change(
        session=session,
        entity_type=AuditEntityType.USER_PERMISSION,
        entity_id=user_id,
        secondary_entity_id=permission_id,
        action=AuditAction.UNASSIGN,
        changed_by=removed_by,
        old_value={"permission_id": str(permission_id), "permission_code": perm_code}
    )

    await session.delete(user_permission)
    await session.commit()
    return True


async def set_user_direct_permissions(
    user_id: UUID,
    permission_ids: List[UUID],
    assigned_by: Optional[UUID] = None,
    session: AsyncSession = None
) -> List[UserPermission]:
    """Set all direct permissions for a user (replaces existing direct permissions)."""
    # Remove existing direct permissions
    await session.execute(
        text("DELETE FROM user_permissions WHERE user_id = :user_id"),
        {"user_id": str(user_id)}
    )

    # Add new permissions
    user_permissions = []
    for permission_id in permission_ids:
        user_permission = UserPermission(
            user_id=user_id,
            permission_id=permission_id,
            assigned_by=assigned_by
        )
        session.add(user_permission)
        user_permissions.append(user_permission)

    await session.commit()
    return user_permissions


# ==================== Direct User Permission Set Management ====================

async def get_user_direct_permission_sets(user_id: UUID, session: AsyncSession) -> List[UserPermissionSet]:
    """Get all permission sets directly assigned to a user (bypassing roles)."""
    result = await session.execute(
        select(UserPermissionSet)
        .where(UserPermissionSet.user_id == user_id)
        .options(selectinload(UserPermissionSet.permission_set))
    )
    return list(result.scalars().all())


async def assign_permission_set_to_user(
    user_id: UUID,
    permission_set_id: UUID,
    assigned_by: Optional[UUID] = None,
    session: AsyncSession = None
) -> UserPermissionSet:
    """Assign a permission set directly to a user (bypassing roles)."""
    # Check if already assigned
    result = await session.execute(
        select(UserPermissionSet)
        .where(UserPermissionSet.user_id == user_id)
        .where(UserPermissionSet.permission_set_id == permission_set_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    # Get permission set info for audit
    perm_set = await get_permission_set_by_id(permission_set_id, session)
    perm_set_code = perm_set.code if perm_set else "Unknown"

    user_permission_set = UserPermissionSet(
        user_id=user_id,
        permission_set_id=permission_set_id,
        assigned_by=assigned_by
    )
    session.add(user_permission_set)

    # Audit log
    await log_rbac_change(
        session=session,
        entity_type=AuditEntityType.USER_PERMISSION_SET,
        entity_id=user_id,
        secondary_entity_id=permission_set_id,
        action=AuditAction.ASSIGN,
        changed_by=assigned_by,
        new_value={"permission_set_id": str(permission_set_id), "permission_set_code": perm_set_code}
    )

    await session.commit()
    await session.refresh(user_permission_set)
    return user_permission_set


async def remove_permission_set_from_user(
    user_id: UUID,
    permission_set_id: UUID,
    session: AsyncSession,
    removed_by: Optional[UUID] = None
) -> bool:
    """Remove a direct permission set assignment from a user."""
    result = await session.execute(
        select(UserPermissionSet)
        .where(UserPermissionSet.user_id == user_id)
        .where(UserPermissionSet.permission_set_id == permission_set_id)
        .options(selectinload(UserPermissionSet.permission_set))
    )
    user_permission_set = result.scalar_one_or_none()
    if not user_permission_set:
        return False

    perm_set_code = user_permission_set.permission_set.code if user_permission_set.permission_set else "Unknown"

    # Audit log
    await log_rbac_change(
        session=session,
        entity_type=AuditEntityType.USER_PERMISSION_SET,
        entity_id=user_id,
        secondary_entity_id=permission_set_id,
        action=AuditAction.UNASSIGN,
        changed_by=removed_by,
        old_value={"permission_set_id": str(permission_set_id), "permission_set_code": perm_set_code}
    )

    await session.delete(user_permission_set)
    await session.commit()
    return True


async def set_user_direct_permission_sets(
    user_id: UUID,
    permission_set_ids: List[UUID],
    assigned_by: Optional[UUID] = None,
    session: AsyncSession = None
) -> List[UserPermissionSet]:
    """Set all direct permission sets for a user (replaces existing direct permission sets)."""
    # Remove existing direct permission sets
    await session.execute(
        text("DELETE FROM user_permission_sets WHERE user_id = :user_id"),
        {"user_id": str(user_id)}
    )

    # Add new permission sets
    user_permission_sets = []
    for permission_set_id in permission_set_ids:
        user_permission_set = UserPermissionSet(
            user_id=user_id,
            permission_set_id=permission_set_id,
            assigned_by=assigned_by
        )
        session.add(user_permission_set)
        user_permission_sets.append(user_permission_set)

    await session.commit()
    return user_permission_sets


# ==================== Effective Permissions Breakdown ====================

async def get_user_permissions_detailed(user_id: UUID, session: AsyncSession) -> dict:
    """Get user's permissions with breakdown by source.

    Returns:
        Dict with keys:
        - from_roles: Set of permission codes from role assignments
        - from_direct_sets: Set of permission codes from direct permission set assignments
        - from_direct_permissions: Set of permission codes from direct permission assignments
        - effective: Set of all permission codes (union of all sources)
    """
    # Source 1: Permissions from roles
    from_roles_query = (
        select(Permission.code)
        .join(PermissionSetPermission, Permission.id == PermissionSetPermission.permission_id)
        .join(PermissionSet, PermissionSetPermission.permission_set_id == PermissionSet.id)
        .join(RolePermissionSet, RolePermissionSet.permission_set_id == PermissionSet.id)
        .join(UserRole, UserRole.role_id == RolePermissionSet.role_id)
        .where(UserRole.user_id == user_id)
        .where(Permission.deleted_at.is_(None))
    )
    from_roles_result = await session.execute(from_roles_query)
    from_roles = {row[0] for row in from_roles_result.all()}

    # Source 2: Permissions from direct permission sets
    from_direct_sets_query = (
        select(Permission.code)
        .join(PermissionSetPermission, Permission.id == PermissionSetPermission.permission_id)
        .join(PermissionSet, PermissionSetPermission.permission_set_id == PermissionSet.id)
        .join(UserPermissionSet, UserPermissionSet.permission_set_id == PermissionSet.id)
        .where(UserPermissionSet.user_id == user_id)
        .where(Permission.deleted_at.is_(None))
    )
    from_direct_sets_result = await session.execute(from_direct_sets_query)
    from_direct_sets = {row[0] for row in from_direct_sets_result.all()}

    # Source 3: Direct permissions
    from_direct_perms_query = (
        select(Permission.code)
        .join(UserPermission, Permission.id == UserPermission.permission_id)
        .where(UserPermission.user_id == user_id)
        .where(Permission.deleted_at.is_(None))
    )
    from_direct_perms_result = await session.execute(from_direct_perms_query)
    from_direct_permissions = {row[0] for row in from_direct_perms_result.all()}

    return {
        "from_roles": list(from_roles),
        "from_direct_sets": list(from_direct_sets),
        "from_direct_permissions": list(from_direct_permissions),
        "effective": list(from_roles | from_direct_sets | from_direct_permissions),
    }
