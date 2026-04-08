"""Service layer for Model Routing Configuration CRUD and routing decisions."""

import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.db.models.model_routing_config import ModelRoutingConfig

logger = logging.getLogger(__name__)


class ModelRoutingService:
    """CRUD operations for model routing configurations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_configs(self, enabled_only: bool = False) -> List[ModelRoutingConfig]:
        """List all routing configs, optionally filtered to enabled only."""
        query = select(ModelRoutingConfig).order_by(ModelRoutingConfig.created_at)
        if enabled_only:
            query = query.where(ModelRoutingConfig.is_enabled == True)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_config(self, config_id: UUID) -> Optional[ModelRoutingConfig]:
        """Get a single routing config by ID."""
        result = await self.session.execute(
            select(ModelRoutingConfig).where(ModelRoutingConfig.id == config_id)
        )
        return result.scalars().first()

    async def get_fallback_config(self) -> Optional[ModelRoutingConfig]:
        """Get the fallback routing config."""
        result = await self.session.execute(
            select(ModelRoutingConfig).where(
                ModelRoutingConfig.is_fallback == True,
                ModelRoutingConfig.is_enabled == True,
            )
        )
        return result.scalars().first()

    async def upsert_config(
        self,
        provider_id: UUID,
        model_id: str,
        task_types: List[str],
        prompt_sizes: List[str],
        cost_tier: str,
        latency_tier: str,
        quality_tier: str,
        is_enabled: bool = True,
        is_fallback: bool = False,
        config_id: Optional[UUID] = None,
    ) -> ModelRoutingConfig:
        """Create or update a routing config."""
        if is_fallback:
            await self._unset_current_fallback(exclude_id=config_id)

        if config_id:
            result = await self.session.execute(
                select(ModelRoutingConfig).where(ModelRoutingConfig.id == config_id)
            )
            config = result.scalars().first()
            if config:
                config.provider_id = provider_id
                config.model_id = model_id
                config.task_types = task_types
                config.prompt_sizes = prompt_sizes
                config.cost_tier = cost_tier
                config.latency_tier = latency_tier
                config.quality_tier = quality_tier
                config.is_enabled = is_enabled
                config.is_fallback = is_fallback
                await self.session.commit()
                await self.session.refresh(config)
                return config

        config = ModelRoutingConfig(
            provider_id=provider_id,
            model_id=model_id,
            task_types=task_types,
            prompt_sizes=prompt_sizes,
            cost_tier=cost_tier,
            latency_tier=latency_tier,
            quality_tier=quality_tier,
            is_enabled=is_enabled,
            is_fallback=is_fallback,
        )
        self.session.add(config)
        await self.session.commit()
        await self.session.refresh(config)
        return config

    async def bulk_upsert(self, items: list) -> List[ModelRoutingConfig]:
        """Bulk create/update routing configs. Handles fallback invariant."""
        fallback_requested = any(item.is_fallback for item in items)
        if fallback_requested:
            upsert_ids = [UUID(item.id) for item in items if item.id]
            await self._unset_current_fallback_bulk(exclude_ids=upsert_ids)

        results = []
        for item in items:
            config_id = UUID(item.id) if item.id else None
            config = await self.upsert_config(
                provider_id=UUID(item.provider_id),
                model_id=item.model_id,
                task_types=item.task_types,
                prompt_sizes=item.prompt_sizes,
                cost_tier=item.cost_tier,
                latency_tier=item.latency_tier,
                quality_tier=item.quality_tier,
                is_enabled=item.is_enabled,
                is_fallback=item.is_fallback,
                config_id=config_id,
            )
            results.append(config)
        return results

    async def delete_config(self, config_id: UUID) -> bool:
        """Delete a routing config."""
        result = await self.session.execute(
            delete(ModelRoutingConfig).where(ModelRoutingConfig.id == config_id)
        )
        await self.session.commit()
        return result.rowcount > 0

    async def get_all_task_types(self) -> List[str]:
        """Get all unique task types across all configs (for global dropdown)."""
        configs = await self.list_configs()
        all_types = set()
        for cfg in configs:
            if cfg.task_types:
                all_types.update(cfg.task_types)
        defaults = {"general", "reasoning", "summarization", "incident-analysis"}
        all_types.update(defaults)
        return sorted(all_types)

    async def get_routing_metadata(self) -> dict:
        """Get static routing option metadata exposed by backend."""
        return {
            "tier_options": [
                {"value": "low", "label": "Low"},
                {"value": "medium", "label": "Medium"},
                {"value": "high", "label": "High"},
            ],
            "latency_options": [
                {"value": "fast", "label": "Fast"},
                {"value": "medium", "label": "Medium"},
                {"value": "slow", "label": "Slow"},
            ],
            "prompt_size_options": [
                {"value": "short", "label": "Short"},
                {"value": "medium", "label": "Medium"},
                {"value": "long", "label": "Long"},
            ],
        }

    async def _unset_current_fallback(self, exclude_id: Optional[UUID] = None):
        """Ensure only one config is marked as fallback."""
        query = select(ModelRoutingConfig).where(ModelRoutingConfig.is_fallback == True)
        if exclude_id:
            query = query.where(ModelRoutingConfig.id != exclude_id)
        result = await self.session.execute(query)
        for config in result.scalars().all():
            config.is_fallback = False

    async def _unset_current_fallback_bulk(self, exclude_ids: List[UUID]):
        """Unset fallback for all configs not in the exclude list."""
        query = select(ModelRoutingConfig).where(ModelRoutingConfig.is_fallback == True)
        if exclude_ids:
            query = query.where(ModelRoutingConfig.id.notin_(exclude_ids))
        result = await self.session.execute(query)
        for config in result.scalars().all():
            config.is_fallback = False