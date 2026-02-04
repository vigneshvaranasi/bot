"""Golden Example model for storing admin-curated ideal responses."""
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ...db.base import Base


class GoldenExample(Base):
    """
    Stores admin-curated ideal responses that the AI uses as few-shot examples.
    
    Golden examples can be created from:
    - positive feedback: Admin approves the original AI response as ideal
    - negative feedback: Admin writes a corrected response
    - manual: Admin creates without associated feedback
    
    These examples are embedded in Qdrant and retrieved via semantic search
    to enhance the AI's responses for similar queries.
    """
    __tablename__ = "golden_examples"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    
    feedback_id = Column(UUID(as_uuid=True), ForeignKey("message_feedback.id", ondelete="SET NULL"), nullable=True)
    
    source_type = Column(String(20), nullable=False)
    
    approval_type = Column(String(20), nullable=False, default="manual")
    
    original_query = Column(Text, nullable=False)
    
    original_response = Column(Text, nullable=False)
    
    golden_response = Column(Text, nullable=False)
    
    qdrant_point_id = Column(String(100), nullable=True)
    
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    feedback = relationship("MessageFeedback", backref="golden_example")
    creator = relationship("User", backref="created_golden_examples")
