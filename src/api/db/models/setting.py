import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ...db.base import Base


class Setting(Base):
    __tablename__ = "settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    deny_words = Column(Text, default="")
    model = Column(String, default="gemini-2.5-flash")
    temperature = Column(String, default="0.2")
    langfuse_enabled = Column(Boolean, default=False)
    auth_google_enabled = Column(Boolean, default=True)
    auth_github_enabled = Column(Boolean, default=True)
    auth_microsoft_enabled = Column(Boolean, default=True)
    auth_local_enabled = Column(Boolean, default=True)
    # LLM Provider selection
    provider_id = Column(UUID(as_uuid=True), ForeignKey("llm_providers.id", ondelete="SET NULL"), nullable=True)

    # Feedback settings for human feedback loop
    feedback_auto_approve_positive = Column(Boolean, default=True, nullable=False)
    feedback_auto_approve_negative = Column(Boolean, default=False, nullable=False)
    feedback_require_reason_positive = Column(Boolean, default=False, nullable=False)
    feedback_require_reason_negative = Column(Boolean, default=False, nullable=False)

    # Audit trail columns
    change_type = Column(String(20), nullable=False, default="update")  # 'create', 'update', 'rollback'
    source_version_id = Column(UUID(as_uuid=True), ForeignKey("settings.id", ondelete="SET NULL"), nullable=True)
    target_version_id = Column(UUID(as_uuid=True), ForeignKey("settings.id", ondelete="SET NULL"), nullable=True)
    change_reason = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="settings")
    provider = relationship("LlmProvider", foreign_keys=[provider_id])
    # Self-referential relationships for audit trail
    source_version = relationship("Setting", foreign_keys=[source_version_id], remote_side=[id])
    target_version = relationship("Setting", foreign_keys=[target_version_id], remote_side=[id])
