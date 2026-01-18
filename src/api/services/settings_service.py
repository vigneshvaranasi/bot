"""Settings service layer for handling segment updates, merging, and rollback."""

import logging
from typing import Optional, Dict, Any, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.api.db.models import Setting
from src.api.schemas.setting_schemas import (
    SettingSegment,
    AiMlSettingsUpdate,
    AiMlSettingsResponse,
    AuthSettingsUpdate,
    AuthSettingsResponse,
    SettingHistoryItem,
)

logger = logging.getLogger(__name__)

# Define which fields belong to each segment
SEGMENT_FIELDS = {
    SettingSegment.AIML: ["model", "temperature", "deny_words", "langfuse_enabled"],
    SettingSegment.AUTH: ["auth_google_enabled", "auth_github_enabled", "auth_microsoft_enabled", "auth_local_enabled"],
}


class SettingsService:
    """Service class for settings operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_latest_setting(self) -> Optional[Setting]:
        """Get the most recent settings version."""
        result = await self.session.execute(
            select(Setting)
            .order_by(Setting.updated_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def get_setting_by_id(self, setting_id: UUID) -> Optional[Setting]:
        """Get a specific setting version by ID."""
        result = await self.session.execute(
            select(Setting).where(Setting.id == setting_id)
        )
        return result.scalars().first()

    async def get_settings_history(self, limit: int = 50, offset: int = 0) -> tuple[List[Setting], int]:
        """Get settings history with pagination."""
        # Get total count
        count_result = await self.session.execute(select(Setting))
        total = len(count_result.scalars().all())

        # Get paginated results
        result = await self.session.execute(
            select(Setting)
            .order_by(Setting.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        settings = result.scalars().all()
        return list(settings), total

    def extract_segment_fields(self, setting: Setting, segment: SettingSegment) -> Dict[str, Any]:
        """Extract only the fields belonging to a specific segment."""
        fields = SEGMENT_FIELDS.get(segment, [])
        return {field: getattr(setting, field) for field in fields}

    def get_segment_response(self, setting: Setting, segment: SettingSegment):
        """Get the appropriate response schema for a segment."""
        if segment == SettingSegment.AIML:
            return AiMlSettingsResponse(
                model=setting.model,
                temperature=setting.temperature,
                deny_words=setting.deny_words,
                langfuse_enabled=setting.langfuse_enabled,
            )
        elif segment == SettingSegment.AUTH:
            return AuthSettingsResponse(
                auth_google_enabled=setting.auth_google_enabled,
                auth_github_enabled=setting.auth_github_enabled,
                auth_microsoft_enabled=setting.auth_microsoft_enabled,
                auth_local_enabled=setting.auth_local_enabled,
            )
        else:
            raise ValueError(f"Unknown segment: {segment}")

    async def update_segment(
        self,
        segment: SettingSegment,
        update_data: Dict[str, Any],
        user_id: UUID
    ) -> Setting:
        """
        Update a specific segment by:
        1. Getting the latest settings
        2. Merging segment updates with existing settings
        3. Creating a new settings version
        """
        latest_setting = await self.get_latest_setting()

        # Build the new setting data by copying from latest (or using defaults)
        new_setting_data = {}

        if latest_setting:
            # Copy all fields from the latest setting
            for field in SEGMENT_FIELDS[SettingSegment.AIML] + SEGMENT_FIELDS[SettingSegment.AUTH]:
                new_setting_data[field] = getattr(latest_setting, field)
        else:
            # Use defaults
            new_setting_data = {
                "model": "gemini-2.5-flash",
                "temperature": "0.2",
                "deny_words": "",
                "langfuse_enabled": True,
                "auth_google_enabled": True,
                "auth_github_enabled": True,
                "auth_microsoft_enabled": True,
                "auth_local_enabled": True,
            }

        # Apply segment-specific updates (only non-None values)
        segment_fields = SEGMENT_FIELDS.get(segment, [])
        for field in segment_fields:
            if field in update_data and update_data[field] is not None:
                new_setting_data[field] = update_data[field]

        # Check if there are actual changes
        if latest_setting:
            has_changes = False
            for field in segment_fields:
                if field in update_data and update_data[field] is not None:
                    if getattr(latest_setting, field) != update_data[field]:
                        has_changes = True
                        break

            if not has_changes:
                logger.debug(f"No changes detected for segment {segment}, returning existing setting")
                return latest_setting

        # Create new setting version
        new_setting = Setting(
            user_id=user_id,
            **new_setting_data
        )

        self.session.add(new_setting)
        await self.session.commit()
        await self.session.refresh(new_setting)

        logger.info(f"Created new settings version {new_setting.id} for segment {segment}")
        return new_setting

    async def rollback_to_version(self, version_id: UUID, user_id: UUID) -> Optional[Setting]:
        """
        Rollback to a previous version by:
        1. Finding the specified version
        2. Creating a new version with the same values
        """
        target_setting = await self.get_setting_by_id(version_id)
        if not target_setting:
            return None

        # Create a new setting version with the same values as the target
        new_setting = Setting(
            user_id=user_id,
            model=target_setting.model,
            temperature=target_setting.temperature,
            deny_words=target_setting.deny_words,
            langfuse_enabled=target_setting.langfuse_enabled,
            auth_google_enabled=target_setting.auth_google_enabled,
            auth_github_enabled=target_setting.auth_github_enabled,
            auth_microsoft_enabled=target_setting.auth_microsoft_enabled,
            auth_local_enabled=target_setting.auth_local_enabled,
        )

        self.session.add(new_setting)
        await self.session.commit()
        await self.session.refresh(new_setting)

        logger.info(f"Rolled back to version {version_id}, created new version {new_setting.id}")
        return new_setting

    async def delete_latest_setting(self) -> Optional[Setting]:
        """
        Delete the latest setting and return the new latest.
        Used for simple rollback (legacy behavior).
        """
        latest_setting = await self.get_latest_setting()
        if not latest_setting:
            return None

        await self.session.delete(latest_setting)
        await self.session.commit()

        # Return the new latest
        return await self.get_latest_setting()
