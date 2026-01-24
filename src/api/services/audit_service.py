"""RBAC Audit Service for tracking all RBAC changes.

This service provides functions to:
- Log RBAC changes (roles, permission sets, user assignments)
- Query audit logs with filters
- Get entity change history
"""

import logging
from typing import Optional, Any, Dict, List
from uuid import UUID

from sqlalchemy import desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..db.models import RbacAuditLog

logger = logging.getLogger(__name__)


class AuditEntityType:
    """Entity types for RBAC audit logging."""
    ROLE = "role"
    PERMISSION_SET = "permission_set"
    USER_ROLE = "user_role"
    USER_PERMISSION = "user_permission"
    USER_PERMISSION_SET = "user_permission_set"


class AuditAction:
    """Action types for RBAC audit logging."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ASSIGN = "assign"
    UNASSIGN = "unassign"


async def log_rbac_change(
    session: AsyncSession,
    entity_type: str,
    entity_id: UUID,
    action: str,
    changed_by: Optional[UUID] = None,
    old_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None,
    secondary_entity_id: Optional[UUID] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> RbacAuditLog:
    """Log an RBAC change to the audit trail.

    Args:
        session: Database session
        entity_type: Type of entity (use AuditEntityType constants)
        entity_id: Primary entity ID (user_id for assignments, entity id for others)
        action: Action performed (use AuditAction constants)
        changed_by: User who made the change
        old_value: Previous state as dict (null for create/assign)
        new_value: New state as dict (null for delete/unassign)
        secondary_entity_id: Secondary ID for junction tables (role_id, permission_id, etc.)
        ip_address: IP address of the request
        user_agent: User agent of the request

    Returns:
        The created RbacAuditLog record
    """
    audit_log = RbacAuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        secondary_entity_id=secondary_entity_id,
        action=action,
        old_value=old_value,
        new_value=new_value,
        changed_by=changed_by,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    session.add(audit_log)
    # Don't commit - let the caller handle transaction
    await session.flush()
    logger.info(
        f"RBAC audit: {action} on {entity_type} "
        f"(entity_id={entity_id}, secondary_id={secondary_entity_id}, by={changed_by})"
    )
    return audit_log


async def get_audit_logs(
    session: AsyncSession,
    entity_type: Optional[str] = None,
    entity_id: Optional[UUID] = None,
    action: Optional[str] = None,
    changed_by: Optional[UUID] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[RbacAuditLog]:
    """Query audit logs with optional filters.

    Args:
        session: Database session
        entity_type: Filter by entity type
        entity_id: Filter by entity ID
        action: Filter by action
        changed_by: Filter by user who made the change
        limit: Maximum number of records to return
        offset: Number of records to skip

    Returns:
        List of RbacAuditLog records
    """
    query = select(RbacAuditLog)

    if entity_type:
        query = query.where(RbacAuditLog.entity_type == entity_type)
    if entity_id:
        query = query.where(RbacAuditLog.entity_id == entity_id)
    if action:
        query = query.where(RbacAuditLog.action == action)
    if changed_by:
        query = query.where(RbacAuditLog.changed_by == changed_by)

    query = query.order_by(desc(RbacAuditLog.changed_at))
    query = query.offset(offset).limit(limit)

    result = await session.execute(query)
    return list(result.scalars().all())


async def get_entity_history(
    session: AsyncSession,
    entity_type: str,
    entity_id: UUID,
    secondary_entity_id: Optional[UUID] = None,
) -> List[RbacAuditLog]:
    """Get complete change history for a specific entity.

    Args:
        session: Database session
        entity_type: Type of entity
        entity_id: Primary entity ID
        secondary_entity_id: Secondary entity ID (for junction tables)

    Returns:
        List of RbacAuditLog records for this entity, ordered by time desc
    """
    query = (
        select(RbacAuditLog)
        .where(RbacAuditLog.entity_type == entity_type)
        .where(RbacAuditLog.entity_id == entity_id)
    )

    if secondary_entity_id:
        query = query.where(RbacAuditLog.secondary_entity_id == secondary_entity_id)

    query = query.order_by(desc(RbacAuditLog.changed_at))

    result = await session.execute(query)
    return list(result.scalars().all())


async def get_user_rbac_history(
    session: AsyncSession,
    user_id: UUID,
    limit: int = 100,
    offset: int = 0,
) -> List[RbacAuditLog]:
    """Get all RBAC changes related to a specific user.

    This includes:
    - Role assignments/removals
    - Direct permission assignments/removals
    - Direct permission set assignments/removals

    Args:
        session: Database session
        user_id: User ID to get history for
        limit: Maximum number of records to return
        offset: Number of records to skip

    Returns:
        List of RbacAuditLog records
    """
    query = (
        select(RbacAuditLog)
        .where(RbacAuditLog.entity_type.in_([
            AuditEntityType.USER_ROLE,
            AuditEntityType.USER_PERMISSION,
            AuditEntityType.USER_PERMISSION_SET,
        ]))
        .where(RbacAuditLog.entity_id == user_id)
        .order_by(desc(RbacAuditLog.changed_at))
        .offset(offset)
        .limit(limit)
    )

    result = await session.execute(query)
    return list(result.scalars().all())
