"""Feedback API router for user feedback and admin management."""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth.dependencies import get_current_user, require_permission
from src.api.db.session import get_session
from src.api.schemas.feedback_schemas import (
    FeedbackCreate,
    FeedbackResponse,
    FeedbackWithContext,
    FeedbackListResponse,
    FeedbackResolveRequest,
    FeedbackDismissRequest,
    FeedbackSettingsResponse,
    FeedbackSettingsUpdate,
    FeedbackStats,
    GoldenExampleCreate,
    GoldenExampleUpdate,
    GoldenExampleResponse,
    GoldenExampleListResponse,
    GenerateResponseResult,
)
from src.api.services.feedback_service import (
    FeedbackService,
    run_deferred_feedback_ai_processing,
)
from src.api.services.golden_example_service import GoldenExampleService
from src.api.services.golden_response_generator import get_golden_response_generator
from src.api.utils.llm_provider_helper import get_provider_config_for_chat

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    data: FeedbackCreate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """
    Submit feedback (thumbs up/down) for a message.
    
    If auto-approval is enabled for the feedback type, a golden example
    will be automatically created.
    """
    try:
        service = FeedbackService(db)
        user_id = UUID(current_user["user_id"])
        
        # Validate message_id is a valid UUID format
        try:
            message_id = UUID(data.message_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid message ID format. Feedback can only be submitted for saved messages."
            )

        feedback, _golden_example, deferred_ai = await service.create_feedback(
            message_id=message_id,
            user_id=user_id,
            feedback_type=data.feedback_type,
            reason=data.reason,
        )
        if deferred_ai:
            background_tasks.add_task(
                run_deferred_feedback_ai_processing, feedback.id
            )

        return FeedbackResponse(
            id=str(feedback.id),
            message_id=str(feedback.message_id),
            user_id=str(feedback.user_id) if feedback.user_id else None,
            feedback_type=feedback.feedback_type,
            reason=feedback.reason,
            status=feedback.status,
            reviewed_by=str(feedback.reviewed_by) if feedback.reviewed_by else None,
            reviewed_at=feedback.reviewed_at,
            created_at=feedback.created_at,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Error submitting feedback")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit feedback"
        )


@router.get("/message/{message_id}", response_model=Optional[FeedbackResponse])
async def get_feedback_for_message(
    message_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get the current user's feedback for a specific message."""
    try:
        try:
            message_uuid = UUID(message_id)
        except ValueError:
            return None
        
        service = FeedbackService(db)
        user_id = UUID(current_user["user_id"])
        
        feedback = await service.get_feedback_by_message(message_uuid, user_id)
        if not feedback:
            return None

        return FeedbackResponse(
            id=str(feedback.id),
            message_id=str(feedback.message_id),
            user_id=str(feedback.user_id) if feedback.user_id else None,
            feedback_type=feedback.feedback_type,
            reason=feedback.reason,
            status=feedback.status,
            reviewed_by=str(feedback.reviewed_by) if feedback.reviewed_by else None,
            reviewed_at=feedback.reviewed_at,
            created_at=feedback.created_at,
        )
    except Exception as e:
        logger.exception("Error getting feedback")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get feedback"
        )


@router.get("/admin/list", response_model=FeedbackListResponse)
async def list_feedback(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    type_filter: Optional[str] = Query(default=None, alias="type"),
    search: Optional[str] = Query(default=None),
    current_user: dict = Depends(require_permission("feedback.view")),
    db: AsyncSession = Depends(get_session),
):
    """
    List all feedback with message context for admin review.
    
    Filters:
    - status: pending, auto_approved, reviewed, dismissed
    - type: positive, negative
    - search: search in query, response, or reason
    """
    try:
        service = FeedbackService(db)
        items, total = await service.list_feedback(
            limit=limit,
            offset=offset,
            status_filter=status_filter,
            type_filter=type_filter,
            search=search,
        )

        return FeedbackListResponse(
            items=[FeedbackWithContext(**item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.exception("Error listing feedback")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list feedback"
        )


@router.get("/admin/stats", response_model=FeedbackStats)
async def get_feedback_stats(
    current_user: dict = Depends(require_permission("feedback.view")),
    db: AsyncSession = Depends(get_session),
):
    """Get feedback statistics."""
    try:
        service = FeedbackService(db)
        stats = await service.get_feedback_stats()
        return FeedbackStats(**stats)
    except Exception as e:
        logger.exception("Error getting feedback stats")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get feedback stats: {str(e)}"
        )


@router.get("/admin/settings", response_model=FeedbackSettingsResponse)
async def get_feedback_settings(
    current_user: dict = Depends(require_permission("feedback.manage")),
    db: AsyncSession = Depends(get_session),
):
    """Get current feedback auto-approval settings."""
    try:
        service = FeedbackService(db)
        settings = await service.get_feedback_settings()
        return FeedbackSettingsResponse(**settings)
    except Exception as e:
        logger.exception("Error getting feedback settings")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get feedback settings: {str(e)}"
        )


@router.put("/admin/settings", response_model=FeedbackSettingsResponse)
async def update_feedback_settings(
    data: FeedbackSettingsUpdate,
    current_user: dict = Depends(require_permission("feedback.manage")),
    db: AsyncSession = Depends(get_session),
):
    """Update feedback auto-approval settings."""
    try:
        from src.api.services.settings_service import SettingsService

        settings_service = SettingsService(db)
        user_id = UUID(current_user["user_id"])
        
        update_data = {}
        if data.auto_approve_positive is not None:
            update_data["feedback_auto_approve_positive"] = data.auto_approve_positive
        if data.auto_approve_negative is not None:
            update_data["feedback_auto_approve_negative"] = data.auto_approve_negative
        if data.require_reason_positive is not None:
            update_data["feedback_require_reason_positive"] = data.require_reason_positive
        if data.require_reason_negative is not None:
            update_data["feedback_require_reason_negative"] = data.require_reason_negative
        if data.auto_approve_by_ai is not None:
            update_data["feedback_auto_approve_by_ai"] = data.auto_approve_by_ai

        latest = await settings_service.get_latest_setting()
        if not latest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No settings found. Please configure settings first."
            )
        for key, value in update_data.items():
            setattr(latest, key, value)
        await db.commit()
        await db.refresh(latest)

        feedback_service = FeedbackService(db)
        settings = await feedback_service.get_feedback_settings()
        return FeedbackSettingsResponse(**settings)
    except Exception as e:
        logger.exception("Error updating feedback settings")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update feedback settings"
        )


@router.get("/admin/{feedback_id}", response_model=FeedbackWithContext)
async def get_feedback_details(
    feedback_id: str,
    current_user: dict = Depends(require_permission("feedback.view")),
    db: AsyncSession = Depends(get_session),
):
    """Get detailed feedback with full message context."""
    try:
        service = FeedbackService(db)
        result = await service.get_feedback_with_context(UUID(feedback_id))
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feedback not found"
            )

        return FeedbackWithContext(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting feedback details")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get feedback details"
        )


@router.post("/admin/{feedback_id}/resolve")
async def resolve_feedback(
    feedback_id: str,
    data: FeedbackResolveRequest,
    current_user: dict = Depends(require_permission("feedback.manage")),
    db: AsyncSession = Depends(get_session),
):
    """
    Resolve feedback by creating a golden example.
    
    For positive feedback: golden_response is optional (uses original if not provided)
    For negative feedback: golden_response is required (the corrected response)
    """
    try:
        service = FeedbackService(db)
        reviewer_id = UUID(current_user["user_id"])

        feedback, golden_example = await service.resolve_feedback(
            feedback_id=UUID(feedback_id),
            reviewer_id=reviewer_id,
            golden_response=data.golden_response,
            query_type=data.query_type,
        )

        return {
            "message": "Feedback resolved successfully",
            "feedback_id": str(feedback.id),
            "golden_example_id": str(golden_example.id),
            "status": feedback.status,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Error resolving feedback")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resolve feedback"
        )


@router.post("/admin/{feedback_id}/dismiss")
async def dismiss_feedback(
    feedback_id: str,
    data: FeedbackDismissRequest,
    current_user: dict = Depends(require_permission("feedback.manage")),
    db: AsyncSession = Depends(get_session),
):
    """Dismiss feedback without creating a golden example."""
    try:
        service = FeedbackService(db)
        reviewer_id = UUID(current_user["user_id"])

        feedback = await service.dismiss_feedback(
            feedback_id=UUID(feedback_id),
            reviewer_id=reviewer_id,
            reason=data.reason,
        )

        return {
            "message": "Feedback dismissed",
            "feedback_id": str(feedback.id),
            "status": feedback.status,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Error dismissing feedback")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to dismiss feedback"
        )


@router.post("/admin/{feedback_id}/restore")
async def restore_feedback(
    feedback_id: str,
    current_user: dict = Depends(require_permission("feedback.manage")),
    db: AsyncSession = Depends(get_session),
):
    """Restore dismissed feedback back to pending status."""
    try:
        service = FeedbackService(db)
        
        feedback = await service.restore_feedback(UUID(feedback_id))

        return {
            "message": "Feedback restored to pending",
            "feedback_id": str(feedback.id),
            "status": feedback.status,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Error restoring feedback")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to restore feedback"
        )


@router.delete("/admin/{feedback_id}", status_code=status.HTTP_200_OK)
async def delete_feedback(
    feedback_id: str,
    current_user: dict = Depends(require_permission("feedback.manage")),
    db: AsyncSession = Depends(get_session),
):
    """
    Delete feedback and its associated golden example if exists.
    This permanently removes the feedback from the system.
    """
    try:
        service = FeedbackService(db)
        deleted = await service.delete_feedback(UUID(feedback_id))
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feedback not found"
            )

        return {
            "message": "Feedback deleted successfully",
            "feedback_id": feedback_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error deleting feedback")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete feedback"
        )


@router.post("/admin/{feedback_id}/generate-response", response_model=GenerateResponseResult)
async def generate_golden_response(
    feedback_id: str,
    current_user: dict = Depends(require_permission("feedback.manage")),
    db: AsyncSession = Depends(get_session),
):
    """
    Generate an AI-suggested golden response based on feedback context.
    
    Uses the configured LLM with full RAG tool access. The LLM decides
    autonomously whether to use tools for additional context.
    
    Features:
    - Specialized prompt for response improvement
    - Full access to incident lookup tools
    - Timeout protection (60s)
    - Concurrency control
    """
    try:
        service = FeedbackService(db)
        feedback_data = await service.get_feedback_with_context(UUID(feedback_id))
        
        if not feedback_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feedback not found"
            )
        
        
        llm_config = await get_provider_config_for_chat(db)

        # Bypass golden example search: fetch existing golden responses for this
        # query so the generator can explicitly avoid reproducing them.
        existing_golden_responses = []
        try:
            ge_service = GoldenExampleService(db)
            similar = await ge_service.search_similar_examples(
                query=feedback_data["original_query"],
                top_k=3,
                score_threshold=0.6,
            )
            existing_golden_responses = [
                ex["golden_response"] for ex in similar if ex.get("golden_response")
            ]
        except Exception as e:
            logger.warning(f"Could not fetch existing golden examples: {e}")

        generator = get_golden_response_generator()
        result = await generator.generate(
            original_query=feedback_data["original_query"],
            original_response=feedback_data["original_response"],
            feedback_reason=feedback_data.get("reason"),
            feedback_type=feedback_data["feedback_type"],
            llm_config=llm_config,
            existing_golden_responses=existing_golden_responses or None,
        )
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.error or "Failed to generate response"
            )
        
        return GenerateResponseResult(
            generated_response=result.generated_response,
            tool_calls_made=result.tool_calls_made,
            generation_time_ms=result.generation_time_ms,
            success=result.success,
            error=result.error,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error generating golden response")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate response: {str(e)}"
        )


@router.get("/golden-examples/", response_model=GoldenExampleListResponse)
async def list_golden_examples(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    source_type: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    search: Optional[str] = Query(default=None),
    current_user: dict = Depends(require_permission("golden_example.view")),
    db: AsyncSession = Depends(get_session),
):
    """List all golden examples with pagination and filters."""
    try:
        from src.api.services.golden_example_service import GoldenExampleService
        
        service = GoldenExampleService(db)
        items, total = await service.list_examples(
            limit=limit,
            offset=offset,
            source_type_filter=source_type,
            is_active_filter=is_active,
            search=search,
        )

        return GoldenExampleListResponse(
            items=[GoldenExampleResponse(**item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.exception("Error listing golden examples")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list golden examples"
        )


@router.get("/golden-examples/{example_id}", response_model=GoldenExampleResponse)
async def get_golden_example(
    example_id: str,
    current_user: dict = Depends(require_permission("golden_example.view")),
    db: AsyncSession = Depends(get_session),
):
    """Get a specific golden example by ID."""
    try:
        from src.api.services.golden_example_service import GoldenExampleService
        
        service = GoldenExampleService(db)
        example = await service.get_by_id(UUID(example_id))
        
        if not example:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Golden example not found"
            )

        creator_email = None
        if example.created_by:
            from src.api.db.models import User
            result = await db.execute(
                select(User.email).where(User.id == example.created_by)
            )
            creator_email = result.scalar()

        return GoldenExampleResponse(
            id=str(example.id),
            feedback_id=str(example.feedback_id) if example.feedback_id else None,
            source_type=example.source_type,
            approval_type=example.approval_type,
            original_query=example.original_query,
            original_response=example.original_response,
            golden_response=example.golden_response,
            query_type=example.query_type,
            qdrant_point_id=example.qdrant_point_id,
            created_by=str(example.created_by) if example.created_by else None,
            creator_email=creator_email,
            is_active=example.is_active,
            created_at=example.created_at,
            updated_at=example.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting golden example")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get golden example"
        )


@router.post("/golden-examples/", response_model=GoldenExampleResponse, status_code=status.HTTP_201_CREATED)
async def create_golden_example(
    data: GoldenExampleCreate,
    current_user: dict = Depends(require_permission("golden_example.create")),
    db: AsyncSession = Depends(get_session),
):
    """Manually create a new golden example."""
    try:
        from src.api.services.golden_example_service import GoldenExampleService
        
        service = GoldenExampleService(db)
        user_id = UUID(current_user["user_id"])

        example = await service.create_example(
            original_query=data.original_query,
            golden_response=data.golden_response,
            original_response=data.original_response,
            created_by=user_id,
            source_type="manual",
            approval_type="manual",
            query_type=data.query_type,
        )

        return GoldenExampleResponse(
            id=str(example.id),
            feedback_id=None,
            source_type=example.source_type,
            approval_type=example.approval_type,
            original_query=example.original_query,
            original_response=example.original_response,
            golden_response=example.golden_response,
            query_type=example.query_type,
            qdrant_point_id=example.qdrant_point_id,
            created_by=str(example.created_by) if example.created_by else None,
            creator_email=current_user.get("email"),
            is_active=example.is_active,
            created_at=example.created_at,
            updated_at=example.updated_at,
        )
    except Exception as e:
        logger.exception("Error creating golden example")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create golden example"
        )


@router.put("/golden-examples/{example_id}", response_model=GoldenExampleResponse)
async def update_golden_example(
    example_id: str,
    data: GoldenExampleUpdate,
    current_user: dict = Depends(require_permission("golden_example.edit")),
    db: AsyncSession = Depends(get_session),
):
    """Update a golden example."""
    try:
        from src.api.services.golden_example_service import GoldenExampleService
        
        service = GoldenExampleService(db)
        
        example = await service.update_example(
            example_id=UUID(example_id),
            golden_response=data.golden_response,
            is_active=data.is_active,
            query_type=data.query_type,
        )
        
        if not example:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Golden example not found"
            )

        creator_email = None
        if example.created_by:
            from src.api.db.models import User
            result = await db.execute(
                select(User.email).where(User.id == example.created_by)
            )
            creator_email = result.scalar()

        return GoldenExampleResponse(
            id=str(example.id),
            feedback_id=str(example.feedback_id) if example.feedback_id else None,
            source_type=example.source_type,
            approval_type=example.approval_type,
            original_query=example.original_query,
            original_response=example.original_response,
            golden_response=example.golden_response,
            query_type=example.query_type,
            qdrant_point_id=example.qdrant_point_id,
            created_by=str(example.created_by) if example.created_by else None,
            creator_email=creator_email,
            is_active=example.is_active,
            created_at=example.created_at,
            updated_at=example.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error updating golden example")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update golden example"
        )


@router.delete("/golden-examples/{example_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_golden_example(
    example_id: str,
    current_user: dict = Depends(require_permission("golden_example.delete")),
    db: AsyncSession = Depends(get_session),
):
    """Delete a golden example."""
    try:
        from src.api.services.golden_example_service import GoldenExampleService
        
        service = GoldenExampleService(db)
        deleted = await service.delete_example(UUID(example_id))
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Golden example not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error deleting golden example")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete golden example"
        )
