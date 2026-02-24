from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ...db.base import Base


class RolePermissionSet(Base):
    """Junction table linking roles to permission sets."""
    __tablename__ = "role_permission_sets"

    role_id = Column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False
    )
    permission_set_id = Column(
        UUID(as_uuid=True),
        ForeignKey("permission_sets.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False
    )

    # Relationships
    role = relationship("Role", back_populates="role_permission_sets")
    permission_set = relationship("PermissionSet", back_populates="role_permission_sets")
