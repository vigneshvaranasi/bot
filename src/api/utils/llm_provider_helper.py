"""Helper utilities for LLM provider configuration.

Provides functions to fetch provider configuration from the database
and prepare it for the copilot graph, including auto-routing support.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.db.models import Setting
from src.api.db.models.llm_provider import LlmProvider
from src.api.db.models.model_routing_config import ModelRoutingConfig
from src.api.services.encryption_service import decrypt_value

logger = logging.getLogger(__name__)


async def get_provider_config_for_chat(
    session: AsyncSession,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch provider configuration for use in the copilot graph.

    Retrieves the configured LLM provider based on user settings or
    falls back to the default provider.

    Args:
        session: Async database session.
        user_id: Optional user ID to fetch user-specific settings.

    Returns:
        Dictionary containing provider configuration fields:
            - provider_type: Type of provider (or None for default)
            - model_id: Model identifier
            - api_key: Decrypted API key
            - base_url: Provider base URL
            - provider_config: Additional provider config
            - temperature: LLM temperature setting
    """
    config: Dict[str, Any] = {
        "provider_type": None,
        "model_id": None,
        "api_key": None,
        "base_url": None,
        "provider_config": {},
        "temperature": 0.33,  # Default temperature
    }

    try:
        # Fetch user settings to get selected provider and model
        settings_query = select(Setting).order_by(Setting.updated_at.desc())
        result = await session.execute(settings_query)
        settings = result.scalars().first()

        if not settings:
            logger.debug("No settings found, using default provider")
            return config

        # Get temperature from settings if available
        if settings.temperature is not None:
            try:
                config["temperature"] = float(settings.temperature)
            except (ValueError, TypeError):
                pass

        # Check if settings has provider_id configured
        provider_id = getattr(settings, "provider_id", None)

        if provider_id:
            # Fetch the specific provider
            provider_result = await session.execute(
                select(LlmProvider).where(
                    LlmProvider.id == provider_id,
                    LlmProvider.is_active == True
                )
            )
            provider = provider_result.scalars().first()
        else:
            # No provider_id in settings, try to get the default active provider
            provider_result = await session.execute(
                select(LlmProvider).where(
                    LlmProvider.is_default == True,
                    LlmProvider.is_active == True
                )
            )
            provider = provider_result.scalars().first()

        if not provider:
            logger.debug("No active provider found, using default Ollama from env")
            return config

        # Extract provider configuration
        config["provider_type"] = provider.provider_type
        config["base_url"] = provider.base_url
        config["provider_config"] = provider.config or {}

        # Get model_id from settings or use first model from provider
        model_id = getattr(settings, "model", None) or getattr(settings, "model_id", None)
        if model_id and model_id in (provider.models or []):
            config["model_id"] = model_id
        elif provider.models:
            # Use first available model from provider
            config["model_id"] = provider.models[0]
        else:
            logger.warning(f"Provider {provider.name} has no models configured")
            return {**config, "provider_type": None}

        # Decrypt API key if present
        if provider.api_key_encrypted:
            try:
                config["api_key"] = decrypt_value(provider.api_key_encrypted)
            except Exception as e:
                logger.error(f"Failed to decrypt API key for provider {provider.name}: {e}")
                return {**config, "provider_type": None}

        logger.info(
            f"Using LLM provider: {provider.name} ({provider.provider_type}) "
            f"with model: {config['model_id']}"
        )

    except Exception as e:
        logger.error(f"Error fetching provider config: {e}")
        # Return empty config to use default

    return config


async def get_provider_config_for_model(
    session: AsyncSession,
    provider_id: str,
    model_id: str,
) -> Dict[str, Any]:
    """Fetch provider configuration for a specific provider and model override.

    Used when a per-prompt model override is requested. Falls back to
    the default settings-based config if the provider is not found or inactive.

    Args:
        session: Async database session.
        provider_id: The UUID of the provider to use.
        model_id: The model identifier to use.

    Returns:
        Provider configuration dictionary.
    """
    config: Dict[str, Any] = {
        "provider_type": None,
        "model_id": None,
        "api_key": None,
        "base_url": None,
        "provider_config": {},
        "temperature": 0.33,
    }

    try:
        provider_result = await session.execute(
            select(LlmProvider).where(
                LlmProvider.id == provider_id,
                LlmProvider.is_active == True,
            )
        )
        provider = provider_result.scalars().first()

        if not provider:
            logger.warning(
                f"Provider {provider_id} not found or inactive, falling back to default"
            )
            return await get_provider_config_for_chat(session)

        # Validate model_id is in provider's models list
        if model_id not in (provider.models or []):
            logger.warning(
                f"Model {model_id} not in provider {provider.name}'s models, falling back to default"
            )
            return await get_provider_config_for_chat(session)

        config["provider_type"] = provider.provider_type
        config["model_id"] = model_id
        config["base_url"] = provider.base_url
        config["provider_config"] = provider.config or {}

        # Get temperature from settings
        settings_query = select(Setting).order_by(Setting.updated_at.desc())
        result = await session.execute(settings_query)
        settings = result.scalars().first()
        if settings and settings.temperature is not None:
            try:
                config["temperature"] = float(settings.temperature)
            except (ValueError, TypeError):
                pass

        if provider.api_key_encrypted:
            try:
                config["api_key"] = decrypt_value(provider.api_key_encrypted)
            except Exception as e:
                logger.error(f"Failed to decrypt API key for provider {provider.name}: {e}")
                return await get_provider_config_for_chat(session)

        logger.info(
            f"Using per-prompt override: {provider.name} ({provider.provider_type}) "
            f"with model: {model_id}"
        )

    except Exception as e:
        logger.error(f"Error fetching provider config for model override: {e}")
        return await get_provider_config_for_chat(session)

    return config

async def resolve_auto_routed_config(
    session: AsyncSession,
    user_id: Optional[str] = None,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve provider config with auto-routing support.

    If auto_routing_enabled is True in settings, uses the router LLM to
    pick the best model. Falls back to default config on any failure.
    """
    settings_query = select(Setting).order_by(Setting.updated_at.desc())
    result = await session.execute(settings_query)
    settings = result.scalars().first()

    if not settings or not getattr(settings, "auto_routing_enabled", False) or not query:
        return await get_provider_config_for_chat(session, user_id)

    router_provider_id = getattr(settings, "router_provider_id", None)
    router_model_id = getattr(settings, "router_model_id", None)

    if not router_provider_id or not router_model_id:
        logger.debug("Auto-routing enabled but no router model configured, using default")
        return await get_provider_config_for_chat(session, user_id)

    try:
        configs_result = await session.execute(
            select(ModelRoutingConfig).where(ModelRoutingConfig.is_enabled == True)
        )
        routing_configs = list(configs_result.scalars().all())

        if not routing_configs:
            logger.debug("No enabled routing configs, using default")
            return await get_provider_config_for_chat(session, user_id)

        router_provider_result = await session.execute(
            select(LlmProvider).where(
                LlmProvider.id == router_provider_id,
                LlmProvider.is_active == True,
            )
        )
        router_provider = router_provider_result.scalars().first()

        if not router_provider:
            logger.warning("Router provider not found or inactive, using default")
            return await get_provider_config_for_chat(session, user_id)

        router_api_key = None
        if router_provider.api_key_encrypted:
            router_api_key = decrypt_value(router_provider.api_key_encrypted)

        from src.api.services.llm_routing_service import route_query

        loop = asyncio.get_running_loop()
        decision = await loop.run_in_executor(
            None,
            route_query,
            query,
            routing_configs,
            router_provider.provider_type,
            router_model_id,
            router_api_key,
            router_provider.base_url,
            router_provider.config or {},
        )

        if decision and decision.get("provider_id") and decision.get("model_id"):
            logger.info(
                f"Auto-routing selected: {decision['model_id']} "
                f"(reason: {decision.get('reason', 'N/A')})"
            )
            return await get_provider_config_for_model(
                session, decision["provider_id"], decision["model_id"]
            )

        logger.info("Router returned no decision, trying fallback model")
        fallback_result = await session.execute(
            select(ModelRoutingConfig).where(
                ModelRoutingConfig.is_fallback == True,
                ModelRoutingConfig.is_enabled == True,
            )
        )
        fallback = fallback_result.scalars().first()

        if fallback:
            logger.info(f"Using fallback model: {fallback.model_id}")
            return await get_provider_config_for_model(
                session, str(fallback.provider_id), fallback.model_id
            )

    except Exception as e:
        logger.error(f"Auto-routing failed: {e}")
    return await get_provider_config_for_chat(session, user_id)
