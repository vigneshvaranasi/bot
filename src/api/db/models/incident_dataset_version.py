import uuid
from sqlalchemy import Column, String, DateTime, Integer, Boolean, ForeignKey, Text, func, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ...db.base import Base


class IncidentDatasetVersion(Base):
    __tablename__ = "incident_dataset_versions"

    id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )

    version_number = Column(Integer, nullable=False)
    collection_name = Column(String, unique=True, nullable=False)

    status = Column(
        String(20), nullable=False, default="uploaded"
    )  # uploaded / validating / validated / ingesting / active / inactive / archived / failed

    is_active = Column(Boolean, nullable=False, default=False)

    incident_count = Column(Integer, nullable=True)
    file_metadata = Column(JSON, nullable=True)  # [{filename, size, row_count}]
    source = Column(String(20), nullable=False, default="upload")  # "upload" or "servicenow"
    snapshot_name = Column(String, nullable=True)  # Qdrant snapshot name once archived

    upload_session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incident_upload_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    upload_session = relationship("IncidentUploadSession")

    uploaded_by = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    uploader = relationship("User", foreign_keys=[uploaded_by])

    notes = Column(Text, nullable=True)

    activated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index(
            "ix_incident_dataset_versions_is_active",
            is_active,
            unique=True,
            postgresql_where=(is_active == True),
        ),
    )
