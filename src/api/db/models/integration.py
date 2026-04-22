import uuid
from sqlalchemy import JSON, Boolean, Column, String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ...db.base import Base

class Integration(Base):
    __tablename__ = "integrations"

    id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )

    service_name = Column(String, nullable=False)
    connector_type = Column(String, nullable=False)

    is_active = Column(Boolean, default=False)

    auth_type = Column(String, nullable=False)

    config = Column(JSON, nullable=False)

    last_synced_at = Column(DateTime, nullable=True)
    last_sync_status = Column(String, nullable=True)
    last_sync_error = Column(String, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime, nullable=True)

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    user = relationship("User")