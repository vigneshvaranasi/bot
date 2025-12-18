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
    langfuse_enabled = Column(Boolean, default=True)
    auth_google_enabled = Column(Boolean, default=True)
    auth_github_enabled = Column(Boolean, default=True)
    auth_microsoft_enabled = Column(Boolean, default=True)
    auth_local_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="settings")
