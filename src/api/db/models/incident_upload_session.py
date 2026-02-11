import uuid
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, func, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ...db.base import Base


class IncidentUploadSession(Base):
    __tablename__ = "incident_upload_sessions"

    id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )

    status = Column(
        String(20), nullable=False, default="pending"
    )  # pending / validating / validated / mapping / confirmed / ingesting / completed / failed

    uploaded_by = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    uploader = relationship("User", foreign_keys=[uploaded_by])

    source = Column(String(20), nullable=False, default="upload")  # "upload" or "servicenow"

    file_metadata = Column(JSON, nullable=True)  # [{filename, size, content_type}]
    raw_data = Column(JSON, nullable=True)  # Parsed records before validation
    validation_report = Column(JSON, nullable=True)  # {valid_count, error_count, errors}
    field_mapping = Column(JSON, nullable=True)  # {source_field: target_field}
    normalized_data = Column(JSON, nullable=True)  # After normalization

    incident_count = Column(Integer, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
