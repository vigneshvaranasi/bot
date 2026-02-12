import uuid
from sqlalchemy import Column, String, DateTime, Text, Index, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ...db.base import Base


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (
        Index("uq_roles_name_active", "name", unique=True,
              postgresql_where=text("deleted_at IS NULL")),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime, nullable=True)

    # Legacy relationship (deprecated, kept for backward compatibility)
    users = relationship("User", back_populates="role")

    # New RBAC relationships
    role_permission_sets = relationship(
        "RolePermissionSet",
        back_populates="role",
        cascade="all, delete-orphan"
    )
    user_roles = relationship(
        "UserRole",
        back_populates="role",
        cascade="all, delete-orphan"
    )
