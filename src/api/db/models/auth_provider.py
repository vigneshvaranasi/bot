import uuid
from sqlalchemy import Column, String, DateTime, Boolean, JSON, func
from sqlalchemy.dialects.postgresql import UUID
from ...db.base import Base

class AuthProvider(Base):
    __tablename__ = "auth_providers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    provider_name = Column(String, unique=True, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    config = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
