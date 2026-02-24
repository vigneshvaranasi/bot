from sqlalchemy import Column, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ...db.base import Base


class UserPermissionSet(Base):
    """Junction table for direct user -> permission_set assignment (bypassing roles)."""
    __tablename__ = "user_permission_sets"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False
    )
    permission_set_id = Column(
        UUID(as_uuid=True),
        ForeignKey("permission_sets.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False
    )
    assigned_at = Column(DateTime, server_default=func.now())
    assigned_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    # Relationships
    user = relationship("User", back_populates="user_permission_sets", foreign_keys=[user_id])
    permission_set = relationship("PermissionSet", back_populates="user_permission_sets")
    assigner = relationship("User", foreign_keys=[assigned_by])
