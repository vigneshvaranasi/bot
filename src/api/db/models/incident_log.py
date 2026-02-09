import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, func, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ...db.base import Base


class IncidentLog(Base):
    __tablename__ = "incident_logs"

    id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )

    incident_id = Column(String, nullable=False)
    title = Column(String, nullable=False)
    source = Column(String, default="servicenow", nullable=False)
    
    integration_id = Column(
        UUID(as_uuid=True), ForeignKey("integrations.id", ondelete="CASCADE"), nullable=True
    )
    integration = relationship("Integration")

    created_at = Column(DateTime, server_default=func.now())
