import uuid
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from ...db.base import Base


class RbacAuditLog(Base):
    """Audit log for all RBAC changes (roles, permission sets, user assignments)."""
    __tablename__ = "rbac_audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)

    # What changed
    entity_type = Column(
        String(50),
        nullable=False,
        comment="Type of entity: role, permission_set, user_role, user_permission, user_permission_set"
    )
    entity_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        comment="Primary entity ID"
    )
    # For junction tables with composite keys, store secondary ID
    secondary_entity_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Secondary ID for junction tables (e.g., role_id for user_role)"
    )

    # What action was taken
    action = Column(
        String(20),
        nullable=False,
        comment="Action: create, update, delete, assign, unassign"
    )

    # State before and after (JSONB for flexibility)
    old_value = Column(
        JSONB,
        nullable=True,
        comment="Previous state (null for create/assign)"
    )
    new_value = Column(
        JSONB,
        nullable=True,
        comment="New state (null for delete/unassign)"
    )

    # Who and when
    changed_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    changed_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Additional context (optional)
    ip_address = Column(String(45), nullable=True)  # IPv6 max length
    user_agent = Column(Text, nullable=True)

    # Relationships
    changer = relationship("User", foreign_keys=[changed_by])
