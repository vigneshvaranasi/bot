"""Settings router with segment-based endpoints."""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth.dependencies import get_current_user, require_permission, require_any_permission
from src.api.db.models import Setting
from src.api.db.session import get_session
from src.api.schemas.setting_schemas import (
    SettingCreate,
    SettingResponse,
    SettingListResponse,
    SettingSegment,
    ChangeType,
    ChangeDescription,
    AiMlSettingsUpdate,
    AiMlSettingsResponse,
    AuthSettingsUpdate,
    AuthSettingsResponse,
    SettingHistoryResponse,
    SettingHistoryItem,
    SegmentSettingResponse,
    RollbackRequest,
)
from src.api.services.settings_service import SettingsService

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================
# Segment-based endpoints
# ============================================================

@router.get("/segment/{segment}", response_model=SegmentSettingResponse)
async def get_segment_settings(
    segment: SettingSegment,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_any_permission("aiml.view", "auth.view"))
):
    """Get settings for a specific segment.

    Returns default values if no settings have been configured yet.
    """
    service = SettingsService(db)
    setting = await service.get_latest_setting()

    if not setting:
        # Return default values when no settings exist
        segment_data = SettingsService.get_default_segment_fields(segment)
        return SegmentSettingResponse(
            segment=segment,
            settings=segment_data,
            version_id=None,
            updated_at=None
        )

    segment_data = service.extract_segment_fields(setting, segment)

    return SegmentSettingResponse(
        segment=segment,
        settings=segment_data,
        version_id=setting.id,
        updated_at=setting.updated_at
    )


@router.put("/segment/aiml", response_model=SegmentSettingResponse)
async def update_aiml_settings(
    update_data: AiMlSettingsUpdate,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_permission("aiml.edit"))
):
    """Update AI/ML settings segment."""
    service = SettingsService(db)

    # Convert Pydantic model to dict, excluding None values
    update_dict = update_data.model_dump(exclude_none=True)

    # Convert provider_id string to UUID for DB compatibility
    if "provider_id" in update_dict and update_dict["provider_id"] is not None:
        update_dict["provider_id"] = UUID(update_dict["provider_id"])

    user_id = UUID(current_user["user_id"])
    new_setting = await service.update_segment(
        segment=SettingSegment.AIML,
        update_data=update_dict,
        user_id=user_id
    )

    segment_data = service.extract_segment_fields(new_setting, SettingSegment.AIML)

    return SegmentSettingResponse(
        segment=SettingSegment.AIML,
        settings=segment_data,
        version_id=new_setting.id,
        updated_at=new_setting.updated_at
    )


@router.put("/segment/auth", response_model=SegmentSettingResponse)
async def update_auth_settings(
    update_data: AuthSettingsUpdate,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_permission("auth.edit"))
):
    """Update Auth settings segment."""
    service = SettingsService(db)

    update_dict = update_data.model_dump(exclude_none=True)
    user_id = UUID(current_user["user_id"])

    new_setting = await service.update_segment(
        segment=SettingSegment.AUTH,
        update_data=update_dict,
        user_id=user_id
    )

    segment_data = service.extract_segment_fields(new_setting, SettingSegment.AUTH)

    return SegmentSettingResponse(
        segment=SettingSegment.AUTH,
        settings=segment_data,
        version_id=new_setting.id,
        updated_at=new_setting.updated_at
    )


# ============================================================
# History and rollback endpoints
# ============================================================

@router.get("/history", response_model=SettingHistoryResponse)
async def get_settings_history(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    segment: Optional[SettingSegment] = Query(default=None, description="Filter changes by segment"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_permission("history.view"))
):
    """Get settings version history with pagination and computed changes.

    Returns history items with:
    - User email for attribution
    - Change type (create, update, rollback)
    - Source/target version IDs for audit trail
    - Computed changes compared to previous version
    """
    service = SettingsService(db)
    history_data, total = await service.get_settings_history(
        limit=limit,
        offset=offset,
        segment_filter=segment
    )

    history_items = [
        SettingHistoryItem(
            id=item["setting"].id,
            user_id=item["setting"].user_id,
            user_email=item["user_email"],
            created_at=item["setting"].created_at,
            updated_at=item["setting"].updated_at,
            # Audit trail fields
            change_type=ChangeType(item["setting"].change_type),
            source_version_id=item["setting"].source_version_id,
            target_version_id=item["setting"].target_version_id,
            change_reason=item["setting"].change_reason,
            # Computed changes
            changes=item["changes"],
            # Settings values
            model=item["setting"].model,
            temperature=item["setting"].temperature,
            deny_words=item["setting"].deny_words,
            langfuse_enabled=item["setting"].langfuse_enabled,
            auth_google_enabled=item["setting"].auth_google_enabled,
            auth_github_enabled=item["setting"].auth_github_enabled,
            auth_microsoft_enabled=item["setting"].auth_microsoft_enabled,
            auth_local_enabled=item["setting"].auth_local_enabled,
        )
        for item in history_data
    ]

    return SettingHistoryResponse(history=history_items, total=total)


@router.post("/rollback/{version_id}", response_model=SettingResponse)
async def rollback_to_version(
    version_id: UUID,
    request: Optional[RollbackRequest] = None,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_permission("history.rollback"))
):
    """Rollback all settings to a specific version.

    Creates a new version with the same values as the target version.
    The rollback is recorded with:
    - change_type: 'rollback'
    - source_version_id: the version being replaced (current)
    - target_version_id: the version being restored
    - change_reason: optional reason for the rollback
    """
    service = SettingsService(db)
    user_id = UUID(current_user["user_id"])

    # Extract reason from request body if provided
    reason = request.reason if request else None

    new_setting = await service.rollback_to_version(version_id, user_id, reason=reason)

    if not new_setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Settings version {version_id} not found"
        )

    logger.info(f"Admin {current_user.get('email')} rolled back to version {version_id}")
    return SettingResponse.model_validate(new_setting)


# ============================================================
# Legacy endpoints
# ============================================================

@router.post("/", response_model=SettingResponse, status_code=status.HTTP_201_CREATED)
async def create_setting(
    setting: SettingCreate,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_any_permission("aiml.edit", "auth.edit"))
):
    """Create a new settings version (legacy endpoint)."""
    service = SettingsService(db)
    latest_setting = await service.get_latest_setting()

    # Check if there are actual changes
    if latest_setting and (
        latest_setting.deny_words == setting.deny_words and
        latest_setting.model == setting.model and
        latest_setting.temperature == setting.temperature and
        latest_setting.langfuse_enabled == setting.langfuse_enabled and
        latest_setting.auth_google_enabled == setting.auth_google_enabled and
        latest_setting.auth_github_enabled == setting.auth_github_enabled and
        latest_setting.auth_microsoft_enabled == setting.auth_microsoft_enabled and
        latest_setting.auth_local_enabled == setting.auth_local_enabled
    ):
        logger.debug("No changes detected, returning existing setting")
        return SettingResponse.model_validate(latest_setting)

    # Create new setting
    new_setting = Setting(
        user_id=UUID(current_user["user_id"]),
        deny_words=setting.deny_words,
        model=setting.model,
        temperature=setting.temperature,
        langfuse_enabled=setting.langfuse_enabled,
        auth_google_enabled=setting.auth_google_enabled,
        auth_github_enabled=setting.auth_github_enabled,
        auth_microsoft_enabled=setting.auth_microsoft_enabled,
        auth_local_enabled=setting.auth_local_enabled
    )
    db.add(new_setting)
    await db.commit()
    await db.refresh(new_setting)
    logger.debug("Created new setting")
    return SettingResponse.model_validate(new_setting)


@router.get("/", response_model=Optional[SettingResponse])
async def get_latest_setting(
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_any_permission("aiml.view", "auth.view"))
):
    """Get the latest settings version (legacy endpoint).

    Returns null if no settings have been configured yet.
    """
    service = SettingsService(db)
    setting = await service.get_latest_setting()

    if not setting:
        return None

    return SettingResponse.model_validate(setting)


@router.get("/all", response_model=SettingListResponse)
async def list_settings(
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_permission("history.view"))
):
    """List all settings versions (legacy endpoint)."""
    service = SettingsService(db)
    settings, _ = await service.get_settings_history(limit=100, offset=0)
    return SettingListResponse(settings=[SettingResponse.model_validate(s) for s in settings])


@router.get("/last", response_model=Optional[SettingResponse])
async def get_last_setting(
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_any_permission("aiml.view", "auth.view"))
):
    """Get the last setting (alias for get_latest_setting).

    Returns null if no settings have been configured yet.
    """
    service = SettingsService(db)
    setting = await service.get_latest_setting()

    if not setting:
        return None

    return SettingResponse.model_validate(setting)


# Legacy PUT /rollback endpoint removed - use POST /rollback/{version_id} instead
# The old endpoint was destructive (deleted rows) which violates append-only history
