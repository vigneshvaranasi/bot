"""LLM Provider database model.

Stores configuration for different LLM providers (Anthropic, OpenAI, Google, Custom).
API keys are stored encrypted using Fernet encryption.
"""

import uuid
from sqlalchemy import JSON, Boolean, Column, String, DateTime, ForeignKey, func, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ..base import Base


class LlmProvider(Base):
    """Model for storing LLM provider configurations.

    Attributes:
        id: Unique identifier for the provider.
        name: User-friendly name (e.g., "Production Claude").
        provider_type: Type of provider (anthropic, openai, google, custom).
        base_url: Optional base URL for proxies or custom endpoints.
        api_key_encrypted: Fernet-encrypted API key.
        config: Provider-specific configuration as JSON.
        models: List of available model identifiers as JSON array.
        is_active: Whether the provider is enabled.
        is_default: Whether this is the default provider (only one can be default).
        last_health_check_at: Timestamp of last health check.
        last_health_check_status: Result of last health check (success/error).
        last_health_check_error: Error message if last health check failed.
        created_by: User who created this provider.
        updated_by: User who last updated this provider.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "llm_providers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Provider identification
    name = Column(String(100), nullable=False)
    provider_type = Column(String(50), nullable=False)  # anthropic, openai, google, custom

    # Connection configuration
    base_url = Column(String(500), nullable=True)
    api_key_encrypted = Column(Text, nullable=True)

    # Provider-specific config (JSON)
    # For anthropic/openai: {"organization_id": "..."}
    # For custom: {"auth_type": "bearer|basic|api_key_header|none", "auth_header_name": "...", "custom_headers": {...}}
    config = Column(JSON, nullable=False, default=dict)

    # Available models for this provider (JSON array)
    models = Column(JSON, nullable=False, default=list)

    # Status flags
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)

    # Health check tracking
    last_health_check_at = Column(DateTime(timezone=True), nullable=True)
    last_health_check_status = Column(String(20), nullable=True)  # success, error
    last_health_check_error = Column(Text, nullable=True)

    # Audit fields
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    updated_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])

    def __repr__(self):
        return f"<LlmProvider(id={self.id}, name='{self.name}', type='{self.provider_type}')>"
