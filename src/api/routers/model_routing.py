"""Model Routing Configuration API router.

Provides CRUD endpoints for managing per-model routing metadata.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth.dependencies import require_permission
from src.api.db.session import get_session
from src.api.schemas.model_routing_schemas import (
    ModelRoutingConfigCreate,
    ModelRoutingConfigUpdate,
    ModelRoutingConfigResponse,
    ModelRoutingConfigListResponse,
    BulkUpsertRequest,
    RoutingMetadataResponse,
)
from src.api.services.model_routing_service import ModelRoutingService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=ModelRoutingConfigListResponse)
async def list_routing_configs(
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_permission("llm_provider.view")),
):
    """List all model routing configurations."""
    service = ModelRoutingService(db)
    configs = await service.list_configs()
    return ModelRoutingConfigListResponse(
        configs=[ModelRoutingConfigResponse.model_validate(c) for c in configs],
        total=len(configs),
    )


@router.post("/", response_model=ModelRoutingConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_routing_config(
    data: ModelRoutingConfigCreate,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_permission("llm_provider.edit")),
):
    """Create a new model routing configuration."""
    service = ModelRoutingService(db)
    config = await service.upsert_config(
        provider_id=UUID(data.provider_id),
        model_id=data.model_id,
        task_types=data.task_types,
        prompt_sizes=data.prompt_sizes,
        cost_tier=data.cost_tier,
        latency_tier=data.latency_tier,
        quality_tier=data.quality_tier,
        is_enabled=data.is_enabled,
        is_fallback=data.is_fallback,
    )
    logger.info(f"Admin {current_user.get('email')} created routing config for {data.model_id}")
    return ModelRoutingConfigResponse.model_validate(config)


@router.put("/{config_id}", response_model=ModelRoutingConfigResponse)
async def update_routing_config(
    config_id: UUID,
    data: ModelRoutingConfigUpdate,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_permission("llm_provider.edit")),
):
    """Update an existing model routing configuration."""
    service = ModelRoutingService(db)
    existing = await service.get_config(config_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")

    update_fields = data.model_dump(exclude_none=True)
    config = await service.upsert_config(
        provider_id=existing.provider_id,
        model_id=existing.model_id,
        task_types=update_fields.get("task_types", existing.task_types),
        prompt_sizes=update_fields.get("prompt_sizes", existing.prompt_sizes),
        cost_tier=update_fields.get("cost_tier", existing.cost_tier),
        latency_tier=update_fields.get("latency_tier", existing.latency_tier),
        quality_tier=update_fields.get("quality_tier", existing.quality_tier),
        is_enabled=update_fields.get("is_enabled", existing.is_enabled),
        is_fallback=update_fields.get("is_fallback", existing.is_fallback),
        config_id=config_id,
    )
    logger.info(f"Admin {current_user.get('email')} updated routing config {config_id}")
    return ModelRoutingConfigResponse.model_validate(config)


@router.post("/bulk", response_model=ModelRoutingConfigListResponse)
async def bulk_upsert_routing_configs(
    data: BulkUpsertRequest,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_permission("llm_provider.edit")),
):
    """Bulk create/update routing configurations (used by the capabilities table save)."""
    service = ModelRoutingService(db)
    configs = await service.bulk_upsert(data.configs)
    logger.info(f"Admin {current_user.get('email')} bulk-upserted {len(configs)} routing configs")
    return ModelRoutingConfigListResponse(
        configs=[ModelRoutingConfigResponse.model_validate(c) for c in configs],
        total=len(configs),
    )


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_routing_config(
    config_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_permission("llm_provider.edit")),
):
    """Delete a model routing configuration."""
    service = ModelRoutingService(db)
    deleted = await service.delete_config(config_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
    logger.info(f"Admin {current_user.get('email')} deleted routing config {config_id}")


@router.get("/task-types", response_model=list[str])
async def get_all_task_types(
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_permission("llm_provider.view")),
):
    """Get all unique task types across all routing configs (for dropdown options)."""
    service = ModelRoutingService(db)
    return await service.get_all_task_types()


@router.get("/metadata", response_model=RoutingMetadataResponse)
async def get_routing_metadata(
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_permission("llm_provider.view")),
):
    """Get metadata options for routing UI controls."""
    service = ModelRoutingService(db)
    return await service.get_routing_metadata()