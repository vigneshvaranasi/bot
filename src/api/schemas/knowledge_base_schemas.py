"""Pydantic schemas for knowledge base ingestion and version management."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel


# Expected incident schema constants
REQUIRED_FIELDS = {"incident_id", "title", "description"}
OPTIONAL_FIELDS = {
    "action_taken", "opened_at", "updated_at", "impacted_application",
    "root_cause", "mitigation", "accountable_party", "source_system",
    "repeat_incident",
}
ALL_INCIDENT_FIELDS = REQUIRED_FIELDS | OPTIONAL_FIELDS


# Upload
class FileUploadItem(BaseModel):
    filename: str
    size: int
    content: str


class FileUploadRequest(BaseModel):
    files: List[FileUploadItem]


# Validation
class ValidationErrorItem(BaseModel):
    file: str
    row: Optional[int] = None
    field: str
    message: str
    value: Optional[str] = None


class ValidationReport(BaseModel):
    session_id: str
    status: str
    total_records: int
    valid_count: int
    error_count: int
    errors: List[ValidationErrorItem]
    preview: List[Dict[str, Any]]
    file_fields: Optional[Dict[str, List[str]]] = None  # {filename: [fields in that file]}


# Field Mapping
class FieldMappingRequest(BaseModel):
    session_id: str
    mapping: Dict[str, str]  # {source_field: target_field}


# Ingestion
class IngestionConfirmRequest(BaseModel):
    session_id: str
    notes: Optional[str] = None


# Version Management
class DatasetVersionResponse(BaseModel):
    id: str
    version_number: int
    collection_name: str
    status: str
    is_active: bool
    incident_count: Optional[int] = None
    file_metadata: Optional[List[Dict[str, Any]]] = None
    source: str
    snapshot_name: Optional[str] = None
    upload_session_id: Optional[str] = None
    uploader_email: Optional[str] = None
    notes: Optional[str] = None
    activated_at: Optional[str] = None
    created_at: str
    updated_at: str


class DatasetVersionListResponse(BaseModel):
    versions: List[DatasetVersionResponse]
    total: int
    active_version_id: Optional[str] = None


class RollbackVersionRequest(BaseModel):
    notes: Optional[str] = None
