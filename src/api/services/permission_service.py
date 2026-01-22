"""Permission service for RBAC operations.

This service provides functions to:
- Resolve user permissions from roles
- Cache permissions for performance
- CRUD operations for permissions, permission sets, and roles
"""

import logging
from typing import List, Set, Optional
from uuid import UUID
from functools import lru_cache
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
    UserRole,
    User,
)

logger = logging.getLogger(__name__)


async def get_user_permissions(user_id: UUID, session: AsyncSession) -> Set[str]:
    """Get all permission codes for a user from all their roles.

    This uses a single efficient query to get all permissions across
    all roles assigned to the user.

    Args:
        user_id: The user's UUID
        session: Database session

    Returns:
        Set of permission code strings
    """
    query = text("""
        SELECT DISTINCT p.code
        FROM permissions p
        JOIN permission_set_permissions psp ON p.id = psp.permission_id
        JOIN role_permission_sets rps ON psp.permission_set_id = rps.permission_set_id
        JOIN user_roles ur ON rps.role_id = ur.role_id
        WHERE ur.user_id = :user_id
        AND p.deleted_at IS NULL
    """)

    result = await session.execute(query, {"user_id": str(user_id)})
    return {row[0] for row in result.fetchall()}


async def get_role_permissions(role_id: UUID, session: AsyncSession) -> Set[str]:
    """Get all permission codes for a role.

    Args:
        role_id: The role's UUID
        session: Database session

    Returns:
        Set of permission code strings
    """
    query = text("""
        SELECT DISTINCT p.code
        FROM permissions p
        JOIN permission_set_permissions psp ON p.id = psp.permission_id
        JOIN role_permission_sets rps ON psp.permission_set_id = rps.permission_set_id
        WHERE rps.role_id = :role_id
        AND p.deleted_at IS NULL
    """)

    result = await session.execute(query, {"role_id": str(role_id)})
    return {row[0] for row in result.fetchall()}


async def user_has_permission(user_id: UUID, permission_code: str, session: AsyncSession) -> bool:
    """Check if a user has a specific permission.

    Args:
        user_id: The user's UUID
        permission_code: The permission code to check
        session: Database session

    Returns:
        True if user has the permission, False otherwise
    """
    permissions = await get_user_permissions(user_id, session)
    return permission_code in permissions


async def user_has_any_permission(user_id: UUID, permission_codes: List[str], session: AsyncSession) -> bool:
    """Check if a user has any of the specified permissions.

    Args:
        user_id: The user's UUID
        permission_codes: List of permission codes to check
        session: Database session

    Returns:
        True if user has at least one permission, False otherwise
    """
    permissions = await get_user_permissions(user_id, session)
    return bool(permissions.intersection(set(permission_codes)))


async def user_has_all_permissions(user_id: UUID, permission_codes: List[str], session: AsyncSession) -> bool:
    """Check if a user has all of the specified permissions.

    Args:
        user_id: The user's UUID
        permission_codes: List of permission codes to check
        session: Database session

    Returns:
        True if user has all permissions, False otherwise
    """
    permissions = await get_user_permissions(user_id, session)
    return set(permission_codes).issubset(permissions)


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

    from datetime import datetime
    permission_set.deleted_at = datetime.utcnow()
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

    from datetime import datetime
    role.deleted_at = datetime.utcnow()
    await session.commit()
    return True


# ==================== User Role Management ====================

async def get_user_roles(user_id: UUID, session: AsyncSession) -> List[UserRole]:
    """Get all roles assigned to a user."""
    result = await session.execute(
        select(UserRole)
        .where(UserRole.user_id == user_id)
        .options(selectinload(UserRole.role))
    )
    return list(result.scalars().all())


async def assign_role_to_user(
    user_id: UUID,
    role_id: UUID,
    assigned_by: Optional[UUID] = None,
    session: AsyncSession = None
) -> UserRole:
    """Assign a role to a user."""
    # Check if already assigned
    result = await session.execute(
        select(UserRole)
        .where(UserRole.user_id == user_id)
        .where(UserRole.role_id == role_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    user_role = UserRole(
        user_id=user_id,
        role_id=role_id,
        assigned_by=assigned_by
    )
    session.add(user_role)
    await session.commit()
    await session.refresh(user_role)
    return user_role


async def remove_role_from_user(user_id: UUID, role_id: UUID, session: AsyncSession) -> bool:
    """Remove a role from a user."""
    result = await session.execute(
        select(UserRole)
        .where(UserRole.user_id == user_id)
        .where(UserRole.role_id == role_id)
    )
    user_role = result.scalar_one_or_none()
    if not user_role:
        return False

    await session.delete(user_role)
    await session.commit()
    return True


async def set_user_roles(
    user_id: UUID,
    role_ids: List[UUID],
    assigned_by: Optional[UUID] = None,
    session: AsyncSession = None
) -> List[UserRole]:
    """Set all roles for a user (replaces existing roles)."""
    # Remove existing roles
    await session.execute(
        text("DELETE FROM user_roles WHERE user_id = :user_id"),
        {"user_id": str(user_id)}
    )

    # Add new roles
    user_roles = []
    for role_id in role_ids:
        user_role = UserRole(
            user_id=user_id,
            role_id=role_id,
            assigned_by=assigned_by
        )
        session.add(user_role)
        user_roles.append(user_role)

    await session.commit()
    return user_roles
