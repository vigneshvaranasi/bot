from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, UUID4


class ModelEnum(str, Enum):
    GEMMA3_1B = "gemma3:1b"
    GEMMA3_4B = "gemma3:4b"
    GEMINI_2_0_FLASH = "gemini-2.0-flash"
    GEMINI_2_5_FLASH = "gemini-2.5-flash"
    GEMINI_2_0_FLASH_LITE_001 = "gemini-2.0-flash-lite-001"
    GEMINI_2_5_PRO = "gemini-2.5-pro"
    GPT_OSS_20B = "gpt-oss:20b"


class SettingSegment(str, Enum):
    """Available settings segments."""
    AIML = "aiml"
    AUTH = "auth"


# ============================================================
# Segment-specific schemas for request/response
# ============================================================

class AiMlSettingsUpdate(BaseModel):
    """Schema for updating AI/ML settings segment."""
    model: Optional[ModelEnum] = None
    temperature: Optional[str] = None
    deny_words: Optional[str] = None
    langfuse_enabled: Optional[bool] = None


class AiMlSettingsResponse(BaseModel):
    """Schema for AI/ML settings segment response."""
    model: ModelEnum
    temperature: str
    deny_words: str
    langfuse_enabled: bool


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

class SettingCreate(BaseModel):
    deny_words: str = ""
    model: ModelEnum = ModelEnum.GEMINI_2_5_FLASH
    temperature: str = "0.2"
    langfuse_enabled: bool = True
    auth_google_enabled: bool = True
    auth_github_enabled: bool = True
    auth_microsoft_enabled: bool = True
    auth_local_enabled: bool = True


class SettingResponse(BaseModel):
    id: UUID4
    user_id: UUID4
    deny_words: str
    model: ModelEnum
    temperature: str
    langfuse_enabled: bool
    auth_google_enabled: bool
    auth_github_enabled: bool
    auth_microsoft_enabled: bool
    auth_local_enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SettingUpdate(BaseModel):
    deny_words: Optional[str] = None
    model: Optional[ModelEnum] = None
    temperature: Optional[str] = None
    langfuse_enabled: Optional[bool] = None
    auth_google_enabled: Optional[bool] = None
    auth_github_enabled: Optional[bool] = None
    auth_microsoft_enabled: Optional[bool] = None
    auth_local_enabled: Optional[bool] = None


class SettingListResponse(BaseModel):
    settings: List[SettingResponse]


# ============================================================
# History and rollback schemas
# ============================================================

class SettingHistoryItem(BaseModel):
    """Schema for a single history item."""
    id: UUID4
    user_id: UUID4
    created_at: datetime
    updated_at: datetime
    # Include all fields for reference
    model: ModelEnum
    temperature: str
    deny_words: str
    langfuse_enabled: bool
    auth_google_enabled: bool
    auth_github_enabled: bool
    auth_microsoft_enabled: bool
    auth_local_enabled: bool

    class Config:
        from_attributes = True


class SettingHistoryResponse(BaseModel):
    """Response for settings history endpoint."""
    history: List[SettingHistoryItem]
    total: int


class RollbackRequest(BaseModel):
    """Request for rollback endpoint."""
    version_id: UUID4


class SegmentSettingResponse(BaseModel):
    """Generic response wrapper for segment settings."""
    segment: SettingSegment
    settings: dict
    version_id: UUID4
    updated_at: datetime
