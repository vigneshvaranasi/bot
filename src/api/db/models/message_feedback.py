"""Message Feedback model for storing user feedback on AI responses."""
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ...db.base import Base


class MessageFeedback(Base):
    """
    Stores user feedback (thumbs up/down) on AI responses.
    
    Feedback can be:
    - positive: User liked the response
    - negative: User disliked the response
    
    Status flow:
    - pending: Waiting for admin review
    - auto_approved: Automatically created golden example (based on settings)
    - reviewed: Admin manually approved/corrected
    - dismissed: Admin rejected without creating golden example
    """
    __tablename__ = "message_feedback"
    __table_args__ = (
        Index("idx_message_feedback_created_at", "created_at"),
        Index("idx_message_feedback_message_id", "message_id"),
        Index("idx_message_feedback_status", "status"),
        Index("idx_message_feedback_status_type", "status", "feedback_type"),
        Index("idx_message_feedback_type", "feedback_type"),
        Index("idx_message_feedback_user_id", "user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    feedback_type = Column(String(20), nullable=False, comment="positive or negative")
    reason = Column(Text, nullable=True, comment="Optional user explanation")
    status = Column(String(20), default="pending", nullable=False, comment="pending, auto_approved, reviewed, dismissed")
    
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    message = relationship("Message", backref="feedback")
    user = relationship("User", foreign_keys=[user_id], backref="submitted_feedback")
    reviewer = relationship("User", foreign_keys=[reviewed_by], backref="reviewed_feedback")
