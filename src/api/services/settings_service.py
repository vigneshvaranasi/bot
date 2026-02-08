"""Settings service layer for handling segment updates, merging, and rollback."""

import logging
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

from src.api.db.models import Setting, User
from src.api.schemas.setting_schemas import (
    SettingSegment,
    ChangeType,
    ChangeDescription,
    AiMlSettingsResponse,
    AuthSettingsResponse,
)

logger = logging.getLogger(__name__)

# Define which fields belong to each segment
SEGMENT_FIELDS = {
    SettingSegment.AIML: ["model", "temperature", "deny_words", "langfuse_enabled"],
    SettingSegment.AUTH: ["auth_google_enabled", "auth_github_enabled", "auth_microsoft_enabled", "auth_local_enabled"],
}

# Human-readable labels for fields
FIELD_LABELS = {
    "model": "Model",
    "temperature": "Temperature",
    "deny_words": "Deny Words",
    "langfuse_enabled": "Langfuse Enabled",
    "auth_google_enabled": "Google Auth",
    "auth_github_enabled": "GitHub Auth",
    "auth_microsoft_enabled": "Microsoft Auth",
    "auth_local_enabled": "Local Auth",
}

# All trackable fields
ALL_FIELDS = SEGMENT_FIELDS[SettingSegment.AIML] + SEGMENT_FIELDS[SettingSegment.AUTH]

# Default values for settings
DEFAULT_SETTINGS = {
    "model": "gpt-oss:20b",
    "temperature": "0.33",
    "deny_words": "",
    "langfuse_enabled": False,
    "auth_google_enabled": True,
    "auth_github_enabled": True,
    "auth_microsoft_enabled": True,
    "auth_local_enabled": True,
}


def get_field_segment(field: str) -> SettingSegment:
    """Get the segment a field belongs to."""
    if field in SEGMENT_FIELDS[SettingSegment.AIML]:
        return SettingSegment.AIML
    return SettingSegment.AUTH


def format_value_for_display(field: str, value: Any) -> str:
    """Format a field value for display in change descriptions."""
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "On" if value else "Off"
    if field == "deny_words":
        if not value:
            return "(empty)"
        # Truncate long deny words lists
        if len(value) > 50:
            return value[:50] + "..."
        return value
    return str(value)


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

    async def get_settings_history(
        self,
        limit: int = 50,
        offset: int = 0,
        segment_filter: Optional[SettingSegment] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get settings history with pagination, user info, and computed changes.

        Args:
            limit: Maximum number of records to return.
            offset: Number of records to skip.
            segment_filter: Optional segment to filter changes by.

        Returns:
            Tuple of (list of history items with changes, total count).
        """
        # Get total count
        count_query = select(func.count()).select_from(Setting)
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        # Get paginated results with user join
        query = (
            select(Setting, User.email)
            .join(User, Setting.user_id == User.id, isouter=True)
            .order_by(Setting.updated_at.desc())
            .offset(offset)
            .limit(limit + 1)  # Fetch one extra to compare with previous
        )
        result = await self.session.execute(query)
        rows = result.all()

        # Build history items with computed changes
        history_items = []
        for i, (setting, user_email) in enumerate(rows[:limit]):
            # Get the previous version (next in our desc-ordered list)
            previous_setting = rows[i + 1][0] if i + 1 < len(rows) else None

            # Compute changes
            changes = self.compute_changes(previous_setting, setting, segment_filter)

            history_items.append({
                "setting": setting,
                "user_email": user_email,
                "changes": changes,
            })

        return history_items, total

    def compute_changes(
        self,
        old_setting: Optional[Setting],
        new_setting: Setting,
        segment_filter: Optional[SettingSegment] = None
    ) -> List[ChangeDescription]:
        """Compute the differences between two settings versions.

        Args:
            old_setting: The previous setting (None for initial creation).
            new_setting: The new setting.
            segment_filter: Optional segment to filter changes by.

        Returns:
            List of ChangeDescription objects.
        """
        changes = []

        # Determine which fields to check
        if segment_filter:
            fields_to_check = SEGMENT_FIELDS.get(segment_filter, [])
        else:
            fields_to_check = ALL_FIELDS

        for field in fields_to_check:
            old_value = getattr(old_setting, field, None) if old_setting else None
            new_value = getattr(new_setting, field, None)

            # Check if value changed
            if old_value != new_value:
                changes.append(ChangeDescription(
                    field=field,
                    field_label=FIELD_LABELS.get(field, field),
                    old_value=format_value_for_display(field, old_value),
                    new_value=format_value_for_display(field, new_value),
                    segment=get_field_segment(field),
                ))

        return changes

    def extract_segment_fields(self, setting: Setting, segment: SettingSegment) -> Dict[str, Any]:
        """Extract only the fields belonging to a specific segment."""
        fields = SEGMENT_FIELDS.get(segment, [])
        return {field: getattr(setting, field) for field in fields}

    @staticmethod
    def get_default_segment_fields(segment: SettingSegment) -> Dict[str, Any]:
        """Get default values for a specific segment when no settings exist."""
        fields = SEGMENT_FIELDS.get(segment, [])
        return {field: DEFAULT_SETTINGS.get(field) for field in fields}

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
        user_id: UUID,
        reason: Optional[str] = None
    ) -> Setting:
        """
        Update a specific segment by:
        1. Getting the latest settings
        2. Merging segment updates with existing settings
        3. Creating a new settings version with audit trail
        """
        latest_setting = await self.get_latest_setting()

        # Build the new setting data by copying from latest (or using defaults)
        new_setting_data = {}

        if latest_setting:
            # Copy all fields from the latest setting
            for field in ALL_FIELDS:
                new_setting_data[field] = getattr(latest_setting, field)
        else:
            # Use defaults
            new_setting_data = DEFAULT_SETTINGS.copy()

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

        # Determine change type
        change_type = ChangeType.CREATE.value if not latest_setting else ChangeType.UPDATE.value

        # Create new setting version with audit trail
        new_setting = Setting(
            user_id=user_id,
            change_type=change_type,
            source_version_id=latest_setting.id if latest_setting else None,
            target_version_id=None,  # Not a rollback
            change_reason=reason,
            **new_setting_data
        )

        self.session.add(new_setting)
        await self.session.commit()
        await self.session.refresh(new_setting)

        logger.info(f"Created new settings version {new_setting.id} ({change_type}) for segment {segment}")
        return new_setting

    async def rollback_to_version(
        self,
        version_id: UUID,
        user_id: UUID,
        reason: Optional[str] = None
    ) -> Optional[Setting]:
        """
        Rollback to a previous version by:
        1. Finding the specified version (target)
        2. Getting the current latest version (source)
        3. Creating a new version with the target's values and audit trail
        """
        target_setting = await self.get_setting_by_id(version_id)
        if not target_setting:
            return None

        # Get current latest for source tracking
        current_setting = await self.get_latest_setting()

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
            # Audit trail
            change_type=ChangeType.ROLLBACK.value,
            source_version_id=current_setting.id if current_setting else None,
            target_version_id=version_id,
            change_reason=reason,
        )

        self.session.add(new_setting)
        await self.session.commit()
        await self.session.refresh(new_setting)

        logger.info(
            f"Rolled back to version {version_id}, created new version {new_setting.id}. "
            f"Source: {current_setting.id if current_setting else 'None'}"
        )
        return new_setting

    async def get_version_for_comparison(self, version_id: UUID) -> Optional[Dict[str, Any]]:
        """Get a specific version with user info for comparison."""
        result = await self.session.execute(
            select(Setting, User.email)
            .join(User, Setting.user_id == User.id, isouter=True)
            .where(Setting.id == version_id)
        )
        row = result.first()
        if not row:
            return None

        setting, user_email = row
        return {
            "setting": setting,
            "user_email": user_email,
        }
