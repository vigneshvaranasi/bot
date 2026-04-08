"""Model Routing Configuration database model.

Stores per-model routing metadata used by the auto-routing feature
to match incoming queries to the best-suited LLM model.
"""

import uuid
from sqlalchemy import Boolean, Column, String, DateTime, ForeignKey, Index, func, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from ..base import Base


class ModelRoutingConfig(Base):
    """Routing metadata for a specific model within a provider.

    Each row represents one model's capabilities and cost/performance profile,
    used by the router LLM to select the best model for a given query.
    """

    __tablename__ = "model_routing_configs"
    __table_args__ = (
        Index("idx_model_routing_provider", "provider_id"),
        Index("idx_model_routing_enabled", "is_enabled"),
        Index(
            "idx_model_routing_fallback",
            "is_fallback",
            postgresql_where=text("is_fallback = true"),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("llm_providers.id", ondelete="CASCADE"),
        nullable=False,
    )
    model_id = Column(String(200), nullable=False)

    task_types = Column(JSONB, nullable=False, default=list)
    prompt_sizes = Column(JSONB, nullable=False, default=list)
    cost_tier = Column(String(20), nullable=False, default="medium")
    latency_tier = Column(String(20), nullable=False, default="medium")
    quality_tier = Column(String(20), nullable=False, default="medium")

    is_enabled = Column(Boolean, default=True, nullable=False)
    is_fallback = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    provider = relationship("LlmProvider", foreign_keys=[provider_id])

    def __repr__(self):
        return f"<ModelRoutingConfig(provider_id={self.provider_id}, model='{self.model_id}')>"