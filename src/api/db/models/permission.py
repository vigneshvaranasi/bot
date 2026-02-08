import uuid
from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ...db.base import Base


class Permission(Base):
    """Atomic permission definition."""
    __tablename__ = "permissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    code = Column(String(100), unique=True, nullable=False)  # e.g., 'aiml.view'
    name = Column(String(200), nullable=False)  # e.g., 'View AI/ML Settings'
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False)  # e.g., 'aiml', 'auth', 'integration'
    is_system = Column(Boolean, default=True, nullable=False)  # System permissions can't be deleted
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    permission_set_permissions = relationship(
        "PermissionSetPermission",
        back_populates="permission",
        cascade="all, delete-orphan"
    )

    # Direct user assignments (bypassing roles)
    user_permissions = relationship(
        "UserPermission",
        back_populates="permission",
        cascade="all, delete-orphan"
    )


class PermissionSet(Base):
    """Groups of permissions."""
    __tablename__ = "permission_sets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    code = Column(String(100), unique=True, nullable=False)  # e.g., 'aiml_manager'
    name = Column(String(200), nullable=False)  # e.g., 'AI/ML Manager'
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    permission_set_permissions = relationship(
        "PermissionSetPermission",
        back_populates="permission_set",
        cascade="all, delete-orphan"
    )
    role_permission_sets = relationship(
        "RolePermissionSet",
        back_populates="permission_set",
        cascade="all, delete-orphan"
    )

    # Direct user assignments (bypassing roles)
    user_permission_sets = relationship(
        "UserPermissionSet",
        back_populates="permission_set",
        cascade="all, delete-orphan"
    )


class PermissionSetPermission(Base):
    """Junction table linking permission sets to permissions."""
    __tablename__ = "permission_set_permissions"

    permission_set_id = Column(
        UUID(as_uuid=True),
        ForeignKey("permission_sets.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False
    )
    permission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False
    )

    # Relationships
    permission_set = relationship("PermissionSet", back_populates="permission_set_permissions")
    permission = relationship("Permission", back_populates="permission_set_permissions")
