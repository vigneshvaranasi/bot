from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, UUID4, ConfigDict


class SettingSegment(str, Enum):
    """Available settings segments."""
    AIML = "aiml"
    AUTH = "auth"


class ChangeType(str, Enum):
    """Type of configuration change."""
    CREATE = "create"
    UPDATE = "update"
    ROLLBACK = "rollback"


# ============================================================
# Segment-specific schemas for request/response
# ============================================================

class AiMlSettingsUpdate(BaseModel):
    """Schema for updating AI/ML settings segment."""
    model: Optional[str] = None
    temperature: Optional[str] = None
    deny_words: Optional[str] = None
    langfuse_enabled: Optional[bool] = None
    provider_id: Optional[str] = None
    allow_user_model_selection: Optional[bool] = None


class AiMlSettingsResponse(BaseModel):
    """Schema for AI/ML settings segment response."""
    model: str
    temperature: str
    deny_words: str
    langfuse_enabled: bool
    provider_id: Optional[str] = None
    allow_user_model_selection: bool


class AuthSettingsUpdate(BaseModel):
    """Schema for updating Auth settings segment."""
    auth_google_enabled: Optional[bool] = None
    auth_github_enabled: Optional[bool] = None
    auth_microsoft_enabled: Optional[bool] = None
    auth_local_enabled: Optional[bool] = None


class AuthSettingsResponse(BaseModel):
    """Schema for Auth settings segment response."""
    auth_google_enabled: bool
    auth_github_enabled: bool
    auth_microsoft_enabled: bool
    auth_local_enabled: bool


# ============================================================
# Full settings schemas (for internal use and history)
# ============================================================

class SettingResponse(BaseModel):
    id: UUID4
    user_id: UUID4
    deny_words: str
    model: str
    temperature: str
    langfuse_enabled: bool
    allow_user_model_selection: bool
    auth_google_enabled: bool
    auth_github_enabled: bool
    auth_microsoft_enabled: bool
    auth_local_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# History and rollback schemas
# ============================================================

class ChangeDescription(BaseModel):
    """Describes a single field change."""
    field: str
    field_label: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    segment: SettingSegment


class SettingHistoryItem(BaseModel):
    """Schema for a single history item with audit trail info."""
    id: UUID4
    user_id: UUID4
    user_email: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Audit trail fields
    change_type: ChangeType
    source_version_id: Optional[UUID4] = None
    target_version_id: Optional[UUID4] = None
    change_reason: Optional[str] = None

    # Computed changes (compared to previous version)
    changes: List[ChangeDescription] = []

    # Include all settings fields for reference
    model: str
    temperature: str
    deny_words: str
    langfuse_enabled: bool
    allow_user_model_selection: bool
    auth_google_enabled: bool
    auth_github_enabled: bool
    auth_microsoft_enabled: bool
    auth_local_enabled: bool

    model_config = ConfigDict(from_attributes=True)


class SettingHistoryResponse(BaseModel):
    """Response for settings history endpoint."""
    history: List[SettingHistoryItem]
    total: int


class RollbackRequest(BaseModel):
    """Request for rollback endpoint (version_id comes from URL path)."""
    reason: Optional[str] = None


class SegmentSettingResponse(BaseModel):
    """Generic response wrapper for segment settings.

    version_id and updated_at are optional because they are None
    when returning default values (no settings in database yet).
    """
    segment: SettingSegment
    settings: dict
    version_id: Optional[UUID4] = None
    updated_at: Optional[datetime] = None
