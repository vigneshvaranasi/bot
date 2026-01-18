"""Settings router with segment-based endpoints."""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth.dependencies import get_current_user, require_role
from src.api.db.models import Setting
from src.api.db.session import get_session
from src.api.schemas.setting_schemas import (
    SettingCreate,
    SettingResponse,
    SettingListResponse,
    SettingSegment,
    AiMlSettingsUpdate,
    AiMlSettingsResponse,
    AuthSettingsUpdate,
    AuthSettingsResponse,
    SettingHistoryResponse,
    SettingHistoryItem,
    SegmentSettingResponse,
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
    current_user: dict = Depends(require_role("admin"))
):
    """Get settings for a specific segment."""
    service = SettingsService(db)
    setting = await service.get_latest_setting()

    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No settings found"
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
    current_user: dict = Depends(require_role("admin"))
):
    """Update AI/ML settings segment."""
    service = SettingsService(db)

    # Convert Pydantic model to dict, excluding None values
    update_dict = update_data.model_dump(exclude_none=True)

    # Handle ModelEnum serialization
    if "model" in update_dict and update_dict["model"] is not None:
        update_dict["model"] = update_dict["model"].value if hasattr(update_dict["model"], "value") else update_dict["model"]

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
    current_user: dict = Depends(require_role("admin"))
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
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_role("admin"))
):
    """Get settings version history with pagination."""
    service = SettingsService(db)
    settings, total = await service.get_settings_history(limit=limit, offset=offset)

    history_items = [
        SettingHistoryItem(
            id=s.id,
            user_id=s.user_id,
            created_at=s.created_at,
            updated_at=s.updated_at,
            model=s.model,
            temperature=s.temperature,
            deny_words=s.deny_words,
            langfuse_enabled=s.langfuse_enabled,
            auth_google_enabled=s.auth_google_enabled,
            auth_github_enabled=s.auth_github_enabled,
            auth_microsoft_enabled=s.auth_microsoft_enabled,
            auth_local_enabled=s.auth_local_enabled,
        )
        for s in settings
    ]

    return SettingHistoryResponse(history=history_items, total=total)


@router.post("/rollback/{version_id}", response_model=SettingResponse)
async def rollback_to_version(
    version_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_role("admin"))
):
    """Rollback all settings to a specific version."""
    service = SettingsService(db)
    user_id = UUID(current_user["user_id"])

    new_setting = await service.rollback_to_version(version_id, user_id)

    if not new_setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Settings version {version_id} not found"
        )

    return SettingResponse.model_validate(new_setting)


# ============================================================
# Legacy endpoints
# ============================================================

@router.post("/", response_model=SettingResponse, status_code=status.HTTP_201_CREATED)
async def create_setting(
    setting: SettingCreate,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_role("admin"))
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


@router.get("/", response_model=SettingResponse)
async def get_latest_setting(
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_role("admin"))
):
    """Get the latest settings version (legacy endpoint)."""
    service = SettingsService(db)
    setting = await service.get_latest_setting()

    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No settings found"
        )

    return SettingResponse.model_validate(setting)


@router.get("/all", response_model=SettingListResponse)
async def list_settings(
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_role("admin"))
):
    """List all settings versions (legacy endpoint)."""
    service = SettingsService(db)
    settings, _ = await service.get_settings_history(limit=100, offset=0)
    return SettingListResponse(settings=[SettingResponse.model_validate(s) for s in settings])


@router.get("/last", response_model=SettingResponse)
async def get_last_setting(
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_role("admin"))
):
    """Get the last setting (alias for get_latest_setting)."""
    service = SettingsService(db)
    setting = await service.get_latest_setting()

    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No settings found"
        )

    return SettingResponse.model_validate(setting)


@router.put("/rollback", response_model=SettingResponse)
async def rollback_setting(
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_role("admin"))
):
    """Rollback to previous settings by deleting the latest (legacy endpoint)."""
    service = SettingsService(db)
    setting = await service.delete_latest_setting()

    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No previous settings found"
        )

    return SettingResponse.model_validate(setting)
