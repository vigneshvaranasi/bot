"""LLM Providers API router.

Provides CRUD endpoints for managing LLM providers (Anthropic, OpenAI, Google, Custom).
All endpoints are admin-only.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth.dependencies import require_permission
from src.api.db.session import get_session
from src.api.schemas.llm_provider_schemas import (
    LlmProviderCreate,
    LlmProviderUpdate,
    LlmProviderResponse,
    LlmProviderListResponse,
    HealthCheckResponse,
    AvailableModelsResponse,
)
from src.api.services.llm_provider_service import LlmProviderService

logger = logging.getLogger(__name__)
router = APIRouter()


def _to_response(provider) -> LlmProviderResponse:
    """Convert LlmProvider model to response schema.

    Args:
        provider: LlmProvider database model instance.

    Returns:
        LlmProviderResponse schema instance.
    """
    return LlmProviderResponse(
        id=provider.id,
        name=provider.name,
        provider_type=provider.provider_type,
        base_url=provider.base_url,
        has_api_key=bool(provider.api_key_encrypted),
        config=provider.config or {},
        models=provider.models or [],
        is_active=provider.is_active,
        is_default=provider.is_default,
        last_health_check_at=provider.last_health_check_at,
        last_health_check_status=provider.last_health_check_status,
        last_health_check_error=provider.last_health_check_error,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


@router.get("/", response_model=LlmProviderListResponse)
async def list_providers(
    active_only: bool = Query(False, description="Only return active providers"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_permission("llm_provider.view"))
):
    """List all LLM providers.

    Returns all configured LLM providers. Use active_only=true to filter
    for only enabled providers.
    """
    service = LlmProviderService(db)
    providers = await service.list_providers(active_only=active_only)

    return LlmProviderListResponse(
        providers=[_to_response(p) for p in providers],
        total=len(providers)
    )


@router.post("/", response_model=LlmProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(
    data: LlmProviderCreate,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_permission("llm_provider.create"))
):
    """Create a new LLM provider.

    Creates a new provider configuration. API keys are encrypted before storage.
    If models list is empty, default models for the provider type will be used.
    """
    service = LlmProviderService(db)
    user_id = UUID(current_user["user_id"]) if current_user.get("user_id") else None
    provider = await service.create_provider(data, user_id)

    logger.info(f"Admin {current_user.get('email')} created LLM provider: {provider.name}")
    return _to_response(provider)


@router.get("/models/available", response_model=AvailableModelsResponse)
async def get_available_models(
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_permission("llm_provider.view"))
):
    """Get all available models from active providers.

    Aggregates models from all active providers into a single list.
    Each model includes its provider information for selection UI.
    """
    service = LlmProviderService(db)
    models = await service.get_available_models()

    return AvailableModelsResponse(models=models)


@router.get("/{provider_id}", response_model=LlmProviderResponse)
async def get_provider(
    provider_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_permission("llm_provider.view"))
):
    """Get a specific LLM provider by ID.

    Returns the provider configuration. API keys are never returned,
    only a boolean indicating if one is configured.
    """
    service = LlmProviderService(db)
    provider = await service.get_provider(provider_id)

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )

    return _to_response(provider)


@router.put("/{provider_id}", response_model=LlmProviderResponse)
async def update_provider(
    provider_id: UUID,
    data: LlmProviderUpdate,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_permission("llm_provider.edit"))
):
    """Update an LLM provider.

    Updates the specified provider. Only provided fields are updated.
    To update the API key, include it in the request; otherwise it remains unchanged.
    """
    service = LlmProviderService(db)
    user_id = UUID(current_user["user_id"]) if current_user.get("user_id") else None
    provider = await service.update_provider(provider_id, data, user_id)

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )

    logger.info(f"Admin {current_user.get('email')} updated LLM provider: {provider.name}")
    return _to_response(provider)


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_permission("llm_provider.delete"))
):
    """Delete an LLM provider.

    Permanently removes the provider configuration. This action cannot be undone.
    """
    service = LlmProviderService(db)

    # Get provider name for logging before deletion
    provider = await service.get_provider(provider_id)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )

    provider_name = provider.name
    deleted = await service.delete_provider(provider_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )

    logger.info(f"Admin {current_user.get('email')} deleted LLM provider: {provider_name}")


@router.post("/{provider_id}/test", response_model=HealthCheckResponse)
async def test_provider_connection(
    provider_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_permission("llm_provider.test"))
):
    """Test connection to an LLM provider.

    Performs a health check by attempting to connect to the provider's API.
    Updates the provider's health check status in the database.

    Returns:
        HealthCheckResponse with success status, message, and response time.
    """
    service = LlmProviderService(db)

    # Verify provider exists
    provider = await service.get_provider(provider_id)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )

    result = await service.test_connection(provider_id)

    logger.info(
        f"Admin {current_user.get('email')} tested LLM provider {provider.name}: "
        f"{result['status']} ({result.get('response_time_ms', 0):.1f}ms)"
    )

    return HealthCheckResponse(
        success=result["success"],
        provider_id=provider_id,
        status=result["status"],
        message=result.get("message"),
        response_time_ms=result.get("response_time_ms")
    )


@router.post("/{provider_id}/discover-models")
async def discover_provider_models(
    provider_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_permission("llm_provider.view"))
):
    """Discover available models from a saved provider's API.

    Fetches the list of available models from the provider's API endpoint.
    This requires valid credentials to be configured for the provider.

    Returns:
        Dict with success status, list of model IDs, and message.
    """
    service = LlmProviderService(db)

    # Verify provider exists
    provider = await service.get_provider(provider_id)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )

    result = await service.discover_models(provider_id)

    logger.info(
        f"Admin {current_user.get('email')} discovered models for {provider.name}: "
        f"found {len(result.get('models', []))} models"
    )

    return result


@router.post("/discover-models")
async def discover_models_from_config(
    data: LlmProviderCreate,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_permission("llm_provider.create"))
):
    """Discover available models from provider credentials without saving.

    Use this endpoint to discover models before creating a provider.
    Accepts the same payload as provider creation but only performs discovery.

    Returns:
        Dict with success status, list of model IDs, and message.
    """
    service = LlmProviderService(db)

    result = await service.discover_models_from_config(
        provider_type=data.provider_type.value,
        base_url=data.base_url,
        api_key=data.api_key,
        config=data.config or {}
    )

    logger.info(
        f"Admin {current_user.get('email')} discovered models for new {data.provider_type} provider: "
        f"found {len(result.get('models', []))} models"
    )

    return result
