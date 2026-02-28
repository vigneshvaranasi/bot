"""Feedback service layer for handling user feedback and golden examples."""

import logging
from typing import Optional, List, Tuple
from uuid import UUID
from datetime import datetime, UTC

from sqlalchemy import func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

from src.api.db.models import MessageFeedback, GoldenExample, Message, User, Setting

logger = logging.getLogger(__name__)


class FeedbackService:
    """Service class for feedback operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_feedback_settings(self) -> dict:
        """Get the current feedback settings."""
        result = await self.session.execute(
            select(Setting)
            .order_by(Setting.updated_at.desc())
            .limit(1)
        )
        setting = result.scalars().first()
        
        if setting:
            return {
                "auto_approve_positive": setting.feedback_auto_approve_positive if setting.feedback_auto_approve_positive is not None else True,
                "auto_approve_negative": setting.feedback_auto_approve_negative if setting.feedback_auto_approve_negative is not None else False,
                "require_reason_positive": setting.feedback_require_reason_positive if setting.feedback_require_reason_positive is not None else False,
                "require_reason_negative": setting.feedback_require_reason_negative if setting.feedback_require_reason_negative is not None else False,
            }
        
        return {
            "auto_approve_positive": True,
            "auto_approve_negative": False,
            "require_reason_positive": False,
            "require_reason_negative": False,
        }

    async def get_message_with_context(self, message_id: UUID) -> Optional[Message]:
        """Get a message with its chat context."""
        result = await self.session.execute(
            select(Message)
            .options(joinedload(Message.chat))
            .where(Message.id == message_id)
        )
        return result.scalars().first()

    async def get_feedback_by_message(self, message_id: UUID, user_id: UUID) -> Optional[MessageFeedback]:
        """Get existing feedback for a message by a specific user."""
        result = await self.session.execute(
            select(MessageFeedback)
            .where(
                and_(
                    MessageFeedback.message_id == message_id,
                    MessageFeedback.user_id == user_id
                )
            )
        )
        return result.scalars().first()

    async def get_feedback_by_id(self, feedback_id: UUID) -> Optional[MessageFeedback]:
        """Get feedback by ID."""
        result = await self.session.execute(
            select(MessageFeedback)
            .where(MessageFeedback.id == feedback_id)
        )
        return result.scalars().first()

    async def create_feedback(
        self,
        message_id: UUID,
        user_id: UUID,
        feedback_type: str,
        reason: Optional[str] = None
    ) -> Tuple[MessageFeedback, Optional[GoldenExample]]:
        """
        Create feedback for a message.
        
        Returns:
            Tuple of (feedback, golden_example if auto-approved)
        """
        message = await self.get_message_with_context(message_id)
        if not message:
            raise ValueError(f"Message {message_id} not found")

        if not message.chat or str(message.chat.user_id) != str(user_id):
            raise ValueError(f"Message {message_id} not found")
        existing = await self.get_feedback_by_message(message_id, user_id)
        if existing:
            raise ValueError("You have already submitted feedback for this message")

        settings = await self.get_feedback_settings()

        auto_approve = (
            (feedback_type == "positive" and settings["auto_approve_positive"]) or
            (feedback_type == "negative" and settings["auto_approve_negative"])
        )

        feedback = MessageFeedback(
            message_id=message_id,
            user_id=user_id,
            feedback_type=feedback_type,
            reason=reason,
            status="auto_approved" if auto_approve else "pending"
        )
        self.session.add(feedback)
        await self.session.flush()

        golden_example = None
        if auto_approve:
            golden_example = await self._create_golden_example_from_feedback(
                feedback=feedback,
                message=message,
                golden_response=message.bot,
                created_by=None,
                approval_type="auto"
            )

        await self.session.commit()
        await self.session.refresh(feedback)
        if golden_example:
            await self.session.refresh(golden_example)

        logger.info(
            f"Created {feedback_type} feedback {feedback.id} for message {message_id} "
            f"(auto_approved={auto_approve})"
        )

        return feedback, golden_example

    async def update_feedback(
        self,
        feedback_id: UUID,
        user_id: UUID,
        feedback_type: Optional[str] = None,
        reason: Optional[str] = None
    ) -> Optional[MessageFeedback]:
        """Update existing feedback (only if still pending)."""
        feedback = await self.get_feedback_by_id(feedback_id)
        if not feedback:
            return None
        
        if feedback.user_id != user_id:
            raise ValueError("You can only update your own feedback")
        
        if feedback.status != "pending":
            raise ValueError("Cannot update feedback that has already been processed")

        if feedback_type:
            feedback.feedback_type = feedback_type
        if reason is not None:
            feedback.reason = reason

        await self.session.commit()
        await self.session.refresh(feedback)
        return feedback

    async def list_feedback(
        self,
        limit: int = 20,
        offset: int = 0,
        status_filter: Optional[str] = None,
        type_filter: Optional[str] = None,
        search: Optional[str] = None
    ) -> Tuple[List[dict], int]:
        """
        List all feedback with message context for admin review.
        
        Returns:
            Tuple of (list of feedback with context, total count)
        """
        base_query = (
            select(
                MessageFeedback,
                Message.human.label("original_query"),
                Message.bot.label("original_response"),
                Message.chat_id,
                User.email.label("user_email")
            )
            .join(Message, MessageFeedback.message_id == Message.id)
            .join(User, MessageFeedback.user_id == User.id, isouter=True)
        )

        filters = []
        if status_filter:
            filters.append(MessageFeedback.status == status_filter)
        if type_filter:
            filters.append(MessageFeedback.feedback_type == type_filter)
        if search:
            search_pattern = f"%{search}%"
            filters.append(
                or_(
                    Message.human.ilike(search_pattern),
                    Message.bot.ilike(search_pattern),
                    MessageFeedback.reason.ilike(search_pattern)
                )
            )

        if filters:
            base_query = base_query.where(and_(*filters))

        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        query = (
            base_query
            .order_by(MessageFeedback.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(query)
        rows = result.all()

        items = []
        for row in rows:
            feedback = row[0]
            
            ge_result = await self.session.execute(
                select(GoldenExample.id, GoldenExample.golden_response)
                .where(GoldenExample.feedback_id == feedback.id)
            )
            golden_example_row = ge_result.first()
            golden_example_id = golden_example_row[0] if golden_example_row else None
            golden_response = golden_example_row[1] if golden_example_row else None

            reviewer_email = None
            if feedback.reviewed_by:
                reviewer_result = await self.session.execute(
                    select(User.email).where(User.id == feedback.reviewed_by)
                )
                reviewer_email = reviewer_result.scalar()

            items.append({
                "id": str(feedback.id),
                "message_id": str(feedback.message_id),
                "user_id": str(feedback.user_id) if feedback.user_id else None,
                "user_email": row.user_email,
                "feedback_type": feedback.feedback_type,
                "reason": feedback.reason,
                "status": feedback.status,
                "reviewed_by": str(feedback.reviewed_by) if feedback.reviewed_by else None,
                "reviewer_email": reviewer_email,
                "reviewed_at": feedback.reviewed_at,
                "created_at": feedback.created_at,
                "original_query": row.original_query,
                "original_response": row.original_response,
                "chat_id": str(row.chat_id),
                "has_golden_example": golden_example_id is not None,
                "golden_example_id": str(golden_example_id) if golden_example_id else None,
                "golden_response": golden_response,
            })

        return items, total

    async def get_feedback_with_context(self, feedback_id: UUID) -> Optional[dict]:
        """Get a single feedback with full context for admin review."""
        result = await self.session.execute(
            select(
                MessageFeedback,
                Message.human.label("original_query"),
                Message.bot.label("original_response"),
                Message.chat_id,
                User.email.label("user_email")
            )
            .join(Message, MessageFeedback.message_id == Message.id)
            .join(User, MessageFeedback.user_id == User.id, isouter=True)
            .where(MessageFeedback.id == feedback_id)
        )
        row = result.first()
        if not row:
            return None

        feedback = row[0]

        ge_result = await self.session.execute(
            select(GoldenExample)
            .where(GoldenExample.feedback_id == feedback.id)
        )
        golden_example = ge_result.scalars().first()

        reviewer_email = None
        if feedback.reviewed_by:
            reviewer_result = await self.session.execute(
                select(User.email).where(User.id == feedback.reviewed_by)
            )
            reviewer_email = reviewer_result.scalar()

        return {
            "id": str(feedback.id),
            "message_id": str(feedback.message_id),
            "user_id": str(feedback.user_id) if feedback.user_id else None,
            "user_email": row.user_email,
            "feedback_type": feedback.feedback_type,
            "reason": feedback.reason,
            "status": feedback.status,
            "reviewed_by": str(feedback.reviewed_by) if feedback.reviewed_by else None,
            "reviewer_email": reviewer_email,
            "reviewed_at": feedback.reviewed_at,
            "created_at": feedback.created_at,
            "original_query": row.original_query,
            "original_response": row.original_response,
            "chat_id": str(row.chat_id),
            "has_golden_example": golden_example is not None,
            "golden_example_id": str(golden_example.id) if golden_example else None,
        }

    async def resolve_feedback(
        self,
        feedback_id: UUID,
        reviewer_id: UUID,
        golden_response: Optional[str] = None
    ) -> Tuple[MessageFeedback, GoldenExample]:
        """
        Resolve feedback by creating a golden example.
        
        For positive feedback: uses original response if golden_response not provided
        For negative feedback: requires golden_response (corrected response)
        """
        feedback = await self.get_feedback_by_id(feedback_id)
        if not feedback:
            raise ValueError(f"Feedback {feedback_id} not found")

        if feedback.status in ["reviewed", "auto_approved"]:
            raise ValueError("Feedback has already been processed")

        message = await self.get_message_with_context(feedback.message_id)
        if not message:
            raise ValueError("Associated message not found")

        if golden_response is None:
            if feedback.feedback_type == "negative":
                raise ValueError("Golden response is required for negative feedback")
            golden_response = message.bot  # Use original for positive

        feedback.status = "reviewed"
        feedback.reviewed_by = reviewer_id
        feedback.reviewed_at = datetime.now(UTC)

        golden_example = await self._create_golden_example_from_feedback(
            feedback=feedback,
            message=message,
            golden_response=golden_response,
            created_by=reviewer_id,
            approval_type="manual"
        )

        await self.session.commit()
        await self.session.refresh(feedback)
        await self.session.refresh(golden_example)

        logger.info(f"Resolved feedback {feedback_id}, created golden example {golden_example.id}")

        return feedback, golden_example

    async def dismiss_feedback(
        self,
        feedback_id: UUID,
        reviewer_id: UUID,
        reason: Optional[str] = None
    ) -> MessageFeedback:
        """Dismiss feedback without creating a golden example."""
        feedback = await self.get_feedback_by_id(feedback_id)
        if not feedback:
            raise ValueError(f"Feedback {feedback_id} not found")

        if feedback.status in ["reviewed", "dismissed"]:
            raise ValueError("Feedback has already been processed")

        feedback.status = "dismissed"
        feedback.reviewed_by = reviewer_id
        feedback.reviewed_at = datetime.now(UTC)
        if reason:
            if feedback.reason:
                feedback.reason = f"{feedback.reason}\n\n[Dismissed: {reason}]"
            else:
                feedback.reason = f"[Dismissed: {reason}]"

        await self.session.commit()
        await self.session.refresh(feedback)

        logger.info(f"Dismissed feedback {feedback_id}")

        return feedback

    async def restore_feedback(self, feedback_id: UUID) -> MessageFeedback:
        """Restore dismissed feedback back to pending status."""
        feedback = await self.get_feedback_by_id(feedback_id)
        if not feedback:
            raise ValueError(f"Feedback {feedback_id} not found")

        if feedback.status != "dismissed":
            raise ValueError("Only dismissed feedback can be restored")

        feedback.status = "pending"
        feedback.reviewed_by = None
        feedback.reviewed_at = None
        if feedback.reason and "[Dismissed:" in feedback.reason:
            parts = feedback.reason.split("\n\n[Dismissed:")
            feedback.reason = parts[0] if parts[0] else None

        await self.session.commit()
        await self.session.refresh(feedback)

        logger.info(f"Restored feedback {feedback_id} to pending")

        return feedback

    async def delete_feedback(self, feedback_id: UUID) -> bool:
        """
        Delete feedback and its associated golden example if exists.
        
        Returns:
            True if deleted, False if not found
        """
        feedback = await self.get_feedback_by_id(feedback_id)
        if not feedback:
            return False

        ge_result = await self.session.execute(
            select(GoldenExample).where(GoldenExample.feedback_id == feedback_id)
        )
        golden_example = ge_result.scalars().first()

        if golden_example:
            if golden_example.qdrant_point_id:
                try:
                    from src.api.services.golden_example_service import GoldenExampleService
                    ge_service = GoldenExampleService(self.session)
                    await ge_service._delete_from_qdrant(golden_example.qdrant_point_id)
                except Exception as e:
                    logger.warning(f"Failed to delete golden example from Qdrant: {e}")

            await self.session.delete(golden_example)
            logger.info(f"Deleted golden example {golden_example.id} associated with feedback {feedback_id}")

        await self.session.delete(feedback)
        await self.session.commit()

        logger.info(f"Deleted feedback {feedback_id}")

        return True


    async def get_feedback_stats(self) -> dict:
        """Get feedback statistics."""
        total_result = await self.session.execute(
            select(func.count()).select_from(MessageFeedback)
        )
        total = total_result.scalar() or 0

        positive_result = await self.session.execute(
            select(func.count()).select_from(MessageFeedback)
            .where(MessageFeedback.feedback_type == "positive")
        )
        positive_count = positive_result.scalar() or 0

        negative_result = await self.session.execute(
            select(func.count()).select_from(MessageFeedback)
            .where(MessageFeedback.feedback_type == "negative")
        )
        negative_count = negative_result.scalar() or 0

        pending_result = await self.session.execute(
            select(func.count()).select_from(MessageFeedback)
            .where(MessageFeedback.status == "pending")
        )
        pending_count = pending_result.scalar() or 0

        auto_approved_result = await self.session.execute(
            select(func.count()).select_from(MessageFeedback)
            .where(MessageFeedback.status == "auto_approved")
        )
        auto_approved_count = auto_approved_result.scalar() or 0

        reviewed_result = await self.session.execute(
            select(func.count()).select_from(MessageFeedback)
            .where(MessageFeedback.status == "reviewed")
        )
        reviewed_count = reviewed_result.scalar() or 0

        dismissed_result = await self.session.execute(
            select(func.count()).select_from(MessageFeedback)
            .where(MessageFeedback.status == "dismissed")
        )
        dismissed_count = dismissed_result.scalar() or 0

        golden_result = await self.session.execute(
            select(func.count()).select_from(GoldenExample)
            .where(GoldenExample.is_active == True)
        )
        golden_count = golden_result.scalar() or 0

        return {
            "total_feedback": total,
            "positive_count": positive_count,
            "negative_count": negative_count,
            "pending_count": pending_count,
            "auto_approved_count": auto_approved_count,
            "reviewed_count": reviewed_count,
            "dismissed_count": dismissed_count,
            "golden_examples_count": golden_count,
        }


    async def _create_golden_example_from_feedback(
        self,
        feedback: MessageFeedback,
        message: Message,
        golden_response: str,
        created_by: Optional[UUID],
        approval_type: str
    ) -> GoldenExample:
        """Create a golden example from feedback and embed in Qdrant."""
        from src.api.services.golden_example_service import GoldenExampleService
        
        # Use GoldenExampleService to create and embed the example
        golden_service = GoldenExampleService(self.session)
        golden_example = await golden_service.create_example(
            original_query=message.human,
            golden_response=golden_response,
            created_by=created_by,
            original_response=message.bot,
            feedback_id=feedback.id,
            source_type=feedback.feedback_type,
            approval_type=approval_type,
        )

        return golden_example
