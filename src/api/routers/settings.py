"""Settings router with segment-based endpoints."""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth.dependencies import get_current_user, require_permission, require_any_permission
from src.api.db.session import get_session
from src.api.schemas.setting_schemas import (
    SettingResponse,
    SettingSegment,
    ChangeType,
    AiMlSettingsUpdate,
    AuthSettingsUpdate,
    ChatConfigResponse,
    SettingHistoryResponse,
    SettingHistoryItem,
    SegmentSettingResponse,
    RollbackRequest,
)
from src.api.services.settings_service import SettingsService
from src.api.services.encryption_service import encrypt_value, decrypt_value

logger = logging.getLogger(__name__)
router = APIRouter()


def _bool_or_default(value: Optional[bool], default: bool = False) -> bool:
    """Normalize nullable legacy boolean values for strict response schemas."""
    return default if value is None else value


# ============================================================
# Chat-config endpoint (any authenticated user)
# ============================================================

@router.get("/chat-config", response_model=ChatConfigResponse)
async def get_chat_config(
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Return the subset of AI/ML settings the chat UI needs.

    Available to any authenticated user so non-admin users can see the model
    picker when admins enable `allow_user_model_selection` or `auto_routing_enabled`.
    """
    service = SettingsService(db)
    setting = await service.get_latest_setting()

    if not setting:
        defaults = SettingsService.get_default_segment_fields(SettingSegment.AIML)
        return ChatConfigResponse(
            allow_user_model_selection=defaults.get("allow_user_model_selection", False),
            auto_routing_enabled=defaults.get("auto_routing_enabled", False),
            model=defaults.get("model"),
            provider_id=defaults.get("provider_id"),
        )

    aiml = service.extract_segment_fields(setting, SettingSegment.AIML)
    return ChatConfigResponse(
        allow_user_model_selection=_bool_or_default(aiml.get("allow_user_model_selection")),
        auto_routing_enabled=_bool_or_default(aiml.get("auto_routing_enabled")),
        model=aiml.get("model"),
        provider_id=aiml.get("provider_id"),
    )


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

    # Encrypt langfuse_secret_key before storage
    if "langfuse_secret_key" in update_dict:
        raw_key = update_dict.pop("langfuse_secret_key")
        if raw_key:
            update_dict["langfuse_secret_key_encrypted"] = encrypt_value(raw_key)

    # Convert provider_id string to UUID for DB compatibility
    if "provider_id" in update_dict and update_dict["provider_id"] is not None:
        update_dict["provider_id"] = UUID(update_dict["provider_id"])

    # Convert router_provider_id string to UUID for DB compatibility
    if "router_provider_id" in update_dict and update_dict["router_provider_id"] is not None:
        update_dict["router_provider_id"] = UUID(update_dict["router_provider_id"])

    # Convert guardrail_provider_id string to UUID for DB compatibility
    if "guardrail_provider_id" in update_dict and update_dict["guardrail_provider_id"] is not None:
        update_dict["guardrail_provider_id"] = UUID(update_dict["guardrail_provider_id"])

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
            langfuse_enabled=_bool_or_default(item["setting"].langfuse_enabled, False),
            langfuse_public_key=item["setting"].langfuse_public_key,
            langfuse_base_url=item["setting"].langfuse_base_url,
            has_langfuse_secret_key=bool(item["setting"].langfuse_secret_key_encrypted),
            allow_user_model_selection=_bool_or_default(item["setting"].allow_user_model_selection, False),
            auth_google_enabled=_bool_or_default(item["setting"].auth_google_enabled, True),
            auth_github_enabled=_bool_or_default(item["setting"].auth_github_enabled, True),
            auth_microsoft_enabled=_bool_or_default(item["setting"].auth_microsoft_enabled, True),
            auth_local_enabled=_bool_or_default(item["setting"].auth_local_enabled, True),
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
    return SettingResponse(
        id=new_setting.id,
        user_id=new_setting.user_id,
        deny_words=new_setting.deny_words,
        model=new_setting.model,
        temperature=new_setting.temperature,
        langfuse_enabled=new_setting.langfuse_enabled,
        langfuse_public_key=new_setting.langfuse_public_key,
        langfuse_base_url=new_setting.langfuse_base_url,
        has_langfuse_secret_key=bool(new_setting.langfuse_secret_key_encrypted),
        allow_user_model_selection=new_setting.allow_user_model_selection,
        auth_google_enabled=new_setting.auth_google_enabled,
        auth_github_enabled=new_setting.auth_github_enabled,
        auth_microsoft_enabled=new_setting.auth_microsoft_enabled,
        auth_local_enabled=new_setting.auth_local_enabled,
        created_at=new_setting.created_at,
        updated_at=new_setting.updated_at,
    )
