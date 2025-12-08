import uuid
from sqlalchemy import (
    Column, String, DateTime, Boolean, ForeignKey, Table, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .base import Base

RolePermission = Table(
    "role_permission",
    Base.metadata,
    Column(
        "role_id",
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="NO ACTION"),
        primary_key=True
    ),
    Column(
        "permission_id",
        UUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="NO ACTION"),
        primary_key=True
    ),
)

UserPermission = Table(
    "user_permission",
    Base.metadata,
    Column(
        "user_id",
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="NO ACTION"),
        primary_key=True
    ),
    Column(
        "permission_id",
        UUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="NO ACTION"),
        primary_key=True
    ),
)

class Role(Base):
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    name = Column(String, unique=True, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    users = relationship("User", back_populates="role")
    permissions = relationship("Permission", secondary=RolePermission, back_populates="roles")


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    name = Column(String, unique=True, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    roles = relationship("Role", secondary=RolePermission, back_populates="permissions")
    users = relationship("User", secondary=UserPermission, back_populates="permissions")


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="NO ACTION"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime, nullable=True)

    role = relationship("Role", back_populates="users")
    permissions = relationship("Permission", secondary=UserPermission, back_populates="users")
    chats = relationship("Chat", back_populates="user")
    settings = relationship("Setting", back_populates="user")

class Chat(Base):
    __tablename__ = "chats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    title = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    archived_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="chats")
    messages = relationship("Message", back_populates="chat")

class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    chat_id = Column(UUID(as_uuid=True), ForeignKey("chats.id", ondelete="NO ACTION"), nullable=False)
    human = Column(String, nullable=False)
    bot = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    deleted_at = Column(DateTime, nullable=True)

    chat = relationship("Chat", back_populates="messages")

class Setting(Base):
    __tablename__ = "settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    deny_words = Column(String, nullable=True)
    model = Column(String, default="gemini-2.5-flash")
    temperature = Column(String, default="0.2")
    deleted_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=False)
    langfuse_enabled = Column(Boolean, default=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    user = relationship("User", back_populates="settings")
