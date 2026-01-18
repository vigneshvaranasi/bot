"""Pydantic schemas for LLM Provider API.

Defines request/response schemas for CRUD operations, health checks,
and model discovery for LLM providers.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID


class ProviderType(str, Enum):
    """Supported LLM provider types."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    CUSTOM = "custom"


class CustomAuthType(str, Enum):
    """Authentication types for custom providers."""
    NONE = "none"
    BEARER = "bearer"
    BASIC = "basic"
    API_KEY_HEADER = "api_key_header"


# Predefined model lists for each provider
ANTHROPIC_MODELS = [
    "claude-opus-4-5-20251101",
    "claude-sonnet-4-20250514",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
]

OPENAI_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-4",
    "gpt-3.5-turbo",
    "o1-preview",
    "o1-mini",
]

GOOGLE_MODELS = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite-001",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
]


class LlmProviderBase(BaseModel):
    """Base schema for LLM provider data."""
    name: str = Field(..., min_length=1, max_length=100, description="Display name for the provider")
    provider_type: ProviderType = Field(..., description="Type of LLM provider")
    base_url: Optional[str] = Field(None, description="Base URL for API (optional for proxies/custom endpoints)")
    config: Dict[str, Any] = Field(default_factory=dict, description="Provider-specific configuration")
    models: List[str] = Field(default_factory=list, description="List of available model identifiers")
    is_active: bool = Field(True, description="Whether the provider is enabled")
    is_default: bool = Field(False, description="Whether this is the default provider")


class LlmProviderCreate(LlmProviderBase):
    """Schema for creating a new LLM provider."""
    api_key: Optional[str] = Field(None, description="API key (will be encrypted before storage)")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Production Claude",
                "provider_type": "anthropic",
                "api_key": "sk-ant-...",
                "models": ["claude-3-5-sonnet-20241022"],
                "is_active": True,
                "is_default": True
            }
        }


class LlmProviderUpdate(BaseModel):
    """Schema for updating an LLM provider."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    base_url: Optional[str] = None
    api_key: Optional[str] = Field(None, description="Set to update API key")
    config: Optional[Dict[str, Any]] = None
    models: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class LlmProviderResponse(BaseModel):
    """Schema for LLM provider API response."""
    id: UUID
    name: str
    provider_type: ProviderType
    base_url: Optional[str]
    has_api_key: bool = Field(..., description="Indicates if API key is configured (never exposes actual key)")
    config: Dict[str, Any]
    models: List[str]
    is_active: bool
    is_default: bool
    last_health_check_at: Optional[datetime]
    last_health_check_status: Optional[str]
    last_health_check_error: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LlmProviderListResponse(BaseModel):
    """Schema for listing LLM providers."""
    providers: List[LlmProviderResponse]
    total: int


class HealthCheckResponse(BaseModel):
    """Schema for health check result."""
    success: bool
    provider_id: UUID
    status: str = Field(..., description="Status: 'success' or 'error'")
    message: Optional[str] = Field(None, description="Error message if failed")
    response_time_ms: Optional[float] = Field(None, description="Response time in milliseconds")


class AvailableModel(BaseModel):
    """Schema for a single available model."""
    provider_id: str
    provider_name: str
    provider_type: ProviderType
    model_id: str
    display_name: str
    is_default_provider: bool


class AvailableModelsResponse(BaseModel):
    """Schema for available models across all active providers."""
    models: List[AvailableModel]


def get_default_models(provider_type: ProviderType) -> List[str]:
    """Get default models for a provider type.

    Args:
        provider_type: The type of provider.

    Returns:
        List of default model identifiers for the provider type.
    """
    if provider_type == ProviderType.ANTHROPIC:
        return ANTHROPIC_MODELS.copy()
    elif provider_type == ProviderType.OPENAI:
        return OPENAI_MODELS.copy()
    elif provider_type == ProviderType.GOOGLE:
        return GOOGLE_MODELS.copy()
    return []
