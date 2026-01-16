import uuid
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, func, Integer, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ...db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    email = Column(String, unique=True, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="NO ACTION"), nullable=False)
    token_version = Column(Integer, default=0, nullable=False) # Used for global revocation
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime, nullable=True)

    role = relationship("Role", back_populates="users")
    auth_identities = relationship("AuthIdentity", back_populates="user", cascade="all, delete-orphan")
    
    chats = relationship("Chat", back_populates="user")
    settings = relationship("Setting", back_populates="user", cascade="all, delete-orphan")
