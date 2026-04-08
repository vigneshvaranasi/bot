"""Pydantic schemas for Model Routing Configuration API."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID


class ModelRoutingConfigCreate(BaseModel):
    """Schema for creating/updating a model routing config."""
    provider_id: str = Field(..., description="Provider UUID")
    model_id: str = Field(..., description="Model identifier")
    task_types: List[str] = Field(default_factory=list)
    prompt_sizes: List[str] = Field(default_factory=list)
    cost_tier: str = Field("medium", pattern="^(low|medium|high)$")
    latency_tier: str = Field("medium", pattern="^(fast|medium|slow)$")
    quality_tier: str = Field("medium", pattern="^(low|medium|high)$")
    is_enabled: bool = True
    is_fallback: bool = False


class ModelRoutingConfigUpdate(BaseModel):
    """Schema for partial update of a model routing config."""
    task_types: Optional[List[str]] = None
    prompt_sizes: Optional[List[str]] = None
    cost_tier: Optional[str] = Field(None, pattern="^(low|medium|high)$")
    latency_tier: Optional[str] = Field(None, pattern="^(fast|medium|slow)$")
    quality_tier: Optional[str] = Field(None, pattern="^(low|medium|high)$")
    is_enabled: Optional[bool] = None
    is_fallback: Optional[bool] = None


class ModelRoutingConfigResponse(BaseModel):
    """Schema for model routing config API response."""
    id: UUID
    provider_id: UUID
    model_id: str
    task_types: List[str]
    prompt_sizes: List[str]
    cost_tier: str
    latency_tier: str
    quality_tier: str
    is_enabled: bool
    is_fallback: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ModelRoutingConfigListResponse(BaseModel):
    """Response for listing all routing configs."""
    configs: List[ModelRoutingConfigResponse]
    total: int


class RoutingOption(BaseModel):
    """Dropdown option for routing metadata."""
    value: str
    label: str


class RoutingMetadataResponse(BaseModel):
    """Metadata response for routing UI options."""
    tier_options: List[RoutingOption]
    latency_options: List[RoutingOption]
    prompt_size_options: List[RoutingOption]


class BulkUpsertItem(BaseModel):
    """Single item in a bulk upsert request."""
    id: Optional[str] = None  # If present, update existing; otherwise create
    provider_id: str
    model_id: str
    task_types: List[str] = Field(default_factory=list)
    prompt_sizes: List[str] = Field(default_factory=list)
    cost_tier: str = "medium"
    latency_tier: str = "medium"
    quality_tier: str = "medium"
    is_enabled: bool = True
    is_fallback: bool = False


class BulkUpsertRequest(BaseModel):
    """Request for bulk upsert of routing configs."""
    configs: List[BulkUpsertItem]


class RoutingDecisionResponse(BaseModel):
    """Response from the routing decision (for debugging/logging)."""
    selected_provider_id: str
    selected_model_id: str
    reason: str