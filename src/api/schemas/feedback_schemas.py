"""Pydantic schemas for feedback and golden examples API."""
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID

class FeedbackCreate(BaseModel):
    """Schema for submitting feedback on a message."""
    message_id: str = Field(..., description="ID of the message being rated")
    feedback_type: Literal["positive", "negative"] = Field(..., description="Type of feedback")
    reason: Optional[str] = Field(None, description="Optional reason for the feedback")


class FeedbackResponse(BaseModel):
    """Schema for feedback response."""
    id: str
    message_id: str
    user_id: Optional[str]
    feedback_type: str
    reason: Optional[str]
    status: str
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FeedbackWithContext(BaseModel):
    """Schema for feedback with message context (for admin review)."""
    id: str
    message_id: str
    user_id: Optional[str]
    user_email: Optional[str]
    feedback_type: str
    reason: Optional[str]
    status: str
    reviewed_by: Optional[str]
    reviewer_email: Optional[str]
    reviewed_at: Optional[datetime]
    created_at: datetime
    original_query: str
    original_response: str
    chat_id: str
    has_golden_example: bool = False
    golden_example_id: Optional[str] = None
    golden_response: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class FeedbackListResponse(BaseModel):
    """Schema for paginated feedback list."""
    items: List[FeedbackWithContext]
    total: int
    limit: int
    offset: int


class FeedbackResolveRequest(BaseModel):
    """Schema for resolving feedback (creating golden example)."""
    golden_response: Optional[str] = Field(
        None, 
        description="The ideal response. If not provided for positive feedback, uses original response."
    )


class FeedbackDismissRequest(BaseModel):
    """Schema for dismissing feedback."""
    reason: Optional[str] = Field(None, description="Optional reason for dismissal")


class GoldenExampleCreate(BaseModel):
    """Schema for manually creating a golden example."""
    original_query: str = Field(..., description="The user's original question")
    original_response: Optional[str] = Field(None, description="The original AI response (optional for manual)")
    golden_response: str = Field(..., description="The ideal response")


class GoldenExampleUpdate(BaseModel):
    """Schema for updating a golden example."""
    golden_response: Optional[str] = Field(None, description="Updated ideal response")
    is_active: Optional[bool] = Field(None, description="Whether the example is active")


class GoldenExampleResponse(BaseModel):
    """Schema for golden example response."""
    id: str
    feedback_id: Optional[str]
    source_type: str
    approval_type: str
    original_query: str
    original_response: str
    golden_response: str
    qdrant_point_id: Optional[str]
    created_by: Optional[str]
    creator_email: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class GoldenExampleListResponse(BaseModel):
    """Schema for paginated golden examples list."""
    items: List[GoldenExampleResponse]
    total: int
    limit: int
    offset: int


class FeedbackSettingsResponse(BaseModel):
    """Schema for feedback settings."""
    auto_approve_positive: bool
    auto_approve_negative: bool
    require_reason_positive: bool
    require_reason_negative: bool


class FeedbackSettingsUpdate(BaseModel):
    """Schema for updating feedback settings."""
    auto_approve_positive: Optional[bool] = None
    auto_approve_negative: Optional[bool] = None
    require_reason_positive: Optional[bool] = None
    require_reason_negative: Optional[bool] = None



class FeedbackStats(BaseModel):
    """Schema for feedback statistics."""
    total_feedback: int
    positive_count: int
    negative_count: int
    pending_count: int
    auto_approved_count: int
    reviewed_count: int
    dismissed_count: int
    golden_examples_count: int


class GenerateResponseResult(BaseModel):
    """Schema for AI-generated golden response result."""
    generated_response: str = Field(..., description="The AI-generated improved response")
    tool_calls_made: int = Field(..., description="Number of RAG tool calls made during generation")
    generation_time_ms: int = Field(..., description="Time taken to generate the response in milliseconds")
    success: bool = Field(..., description="Whether generation was successful")
    error: Optional[str] = Field(None, description="Error message if generation failed")
