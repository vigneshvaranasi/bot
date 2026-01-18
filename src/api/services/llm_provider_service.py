"""Service layer for LLM Provider operations.

Handles CRUD operations, health checks, and model aggregation for LLM providers.
"""

import httpx
import logging
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.api.db.models.llm_provider import LlmProvider
from src.api.services.encryption_service import encrypt_value, decrypt_value
from src.api.schemas.llm_provider_schemas import (
    ProviderType,
    LlmProviderCreate,
    LlmProviderUpdate,
    AvailableModel,
    get_default_models,
)

logger = logging.getLogger(__name__)


class LlmProviderService:
    """Service class for LLM provider operations."""

    def __init__(self, session: AsyncSession):
        """Initialize the service with a database session.

        Args:
            session: AsyncSession for database operations.
        """
        self.session = session

    async def list_providers(self, active_only: bool = False) -> List[LlmProvider]:
        """List all LLM providers.

        Args:
            active_only: If True, only return active providers.

        Returns:
            List of LlmProvider objects.
        """
        query = select(LlmProvider).order_by(LlmProvider.created_at.desc())
        if active_only:
            query = query.where(LlmProvider.is_active == True)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_provider(self, provider_id: UUID) -> Optional[LlmProvider]:
        """Get a provider by ID.

        Args:
            provider_id: UUID of the provider.

        Returns:
            LlmProvider object or None if not found.
        """
        result = await self.session.execute(
            select(LlmProvider).where(LlmProvider.id == provider_id)
        )
        return result.scalars().first()

    async def get_default_provider(self) -> Optional[LlmProvider]:
        """Get the default active provider.

        Returns:
            The default LlmProvider or None if no default is set.
        """
        result = await self.session.execute(
            select(LlmProvider).where(
                LlmProvider.is_default == True,
                LlmProvider.is_active == True
            )
        )
        return result.scalars().first()

    async def create_provider(
        self, data: LlmProviderCreate, user_id: Optional[UUID] = None
    ) -> LlmProvider:
        """Create a new LLM provider.

        Args:
            data: Provider creation data.
            user_id: ID of the user creating the provider.

        Returns:
            Created LlmProvider object.
        """
        # If setting as default, unset current default first
        if data.is_default:
            await self._unset_current_default()

        # Auto-populate models for known providers if not provided
        models = data.models
        if not models:
            models = get_default_models(data.provider_type)

        # Encrypt API key if provided
        api_key_encrypted = None
        if data.api_key:
            api_key_encrypted = encrypt_value(data.api_key)

        provider = LlmProvider(
            name=data.name,
            provider_type=data.provider_type.value,
            base_url=data.base_url,
            api_key_encrypted=api_key_encrypted,
            config=data.config,
            models=models,
            is_active=data.is_active,
            is_default=data.is_default,
            created_by=user_id,
            updated_by=user_id,
        )

        self.session.add(provider)
        await self.session.commit()
        await self.session.refresh(provider)

        logger.info(f"Created LLM provider: {provider.name} ({provider.provider_type})")
        return provider

    async def update_provider(
        self, provider_id: UUID, data: LlmProviderUpdate, user_id: Optional[UUID] = None
    ) -> Optional[LlmProvider]:
        """Update an LLM provider.

        Args:
            provider_id: UUID of the provider to update.
            data: Update data.
            user_id: ID of the user performing the update.

        Returns:
            Updated LlmProvider or None if not found.
        """
        provider = await self.get_provider(provider_id)
        if not provider:
            return None

        # Handle default flag - unset others if becoming default
        if data.is_default is True and not provider.is_default:
            await self._unset_current_default()

        # Update fields if provided
        if data.name is not None:
            provider.name = data.name
        if data.base_url is not None:
            provider.base_url = data.base_url if data.base_url else None
        if data.api_key is not None:
            provider.api_key_encrypted = encrypt_value(data.api_key) if data.api_key else None
        if data.config is not None:
            provider.config = data.config
        if data.models is not None:
            provider.models = data.models
        if data.is_active is not None:
            provider.is_active = data.is_active
        if data.is_default is not None:
            provider.is_default = data.is_default

        provider.updated_by = user_id

        await self.session.commit()
        await self.session.refresh(provider)

        logger.info(f"Updated LLM provider: {provider.name}")
        return provider

    async def delete_provider(self, provider_id: UUID) -> bool:
        """Delete an LLM provider.

        Args:
            provider_id: UUID of the provider to delete.

        Returns:
            True if deleted, False if not found.
        """
        provider = await self.get_provider(provider_id)
        if not provider:
            return False

        provider_name = provider.name
        await self.session.delete(provider)
        await self.session.commit()

        logger.info(f"Deleted LLM provider: {provider_name}")
        return True

    async def test_connection(self, provider_id: UUID) -> Dict[str, Any]:
        """Test connection to an LLM provider.

        Args:
            provider_id: UUID of the provider to test.

        Returns:
            Dict with success, status, message, and response_time_ms.
        """
        provider = await self.get_provider(provider_id)
        if not provider:
            return {
                "success": False,
                "status": "error",
                "message": "Provider not found",
                "response_time_ms": 0
            }

        start_time = time.time()

        try:
            # Decrypt API key if present
            api_key = None
            if provider.api_key_encrypted:
                api_key = decrypt_value(provider.api_key_encrypted)

            success, message = await self._test_provider_connection(
                provider_type=provider.provider_type,
                base_url=provider.base_url,
                api_key=api_key,
                config=provider.config
            )

            response_time = (time.time() - start_time) * 1000
            status = "success" if success else "error"

            # Update health check status in database
            provider.last_health_check_at = datetime.now(timezone.utc)
            provider.last_health_check_status = status
            provider.last_health_check_error = None if success else message
            await self.session.commit()

            logger.info(f"Health check for {provider.name}: {status}")
            return {
                "success": success,
                "status": status,
                "message": message if not success else "Connection successful",
                "response_time_ms": round(response_time, 2)
            }

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            error_msg = str(e)

            # Update health check status
            provider.last_health_check_at = datetime.now(timezone.utc)
            provider.last_health_check_status = "error"
            provider.last_health_check_error = error_msg
            await self.session.commit()

            logger.error(f"Health check failed for {provider.name}: {error_msg}")
            return {
                "success": False,
                "status": "error",
                "message": error_msg,
                "response_time_ms": round(response_time, 2)
            }

    async def get_available_models(self) -> List[AvailableModel]:
        """Get all available models from active providers.

        Returns:
            List of AvailableModel objects aggregated from all active providers.
        """
        providers = await self.list_providers(active_only=True)
        models = []

        for provider in providers:
            for model_id in provider.models:
                models.append(AvailableModel(
                    provider_id=str(provider.id),
                    provider_name=provider.name,
                    provider_type=provider.provider_type,
                    model_id=model_id,
                    display_name=f"{provider.name} - {model_id}",
                    is_default_provider=provider.is_default,
                ))

        return models

    async def get_decrypted_api_key(self, provider_id: UUID) -> Optional[str]:
        """Get decrypted API key for a provider.

        Args:
            provider_id: UUID of the provider.

        Returns:
            Decrypted API key or None if not found/not set.
        """
        provider = await self.get_provider(provider_id)
        if not provider or not provider.api_key_encrypted:
            return None
        return decrypt_value(provider.api_key_encrypted)

    async def _unset_current_default(self) -> None:
        """Unset the current default provider."""
        result = await self.session.execute(
            select(LlmProvider).where(LlmProvider.is_default == True)
        )
        current_default = result.scalars().first()
        if current_default:
            current_default.is_default = False
            logger.info(f"Unset default provider: {current_default.name}")

    async def _test_provider_connection(
        self,
        provider_type: str,
        base_url: Optional[str],
        api_key: Optional[str],
        config: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Test connection to a specific provider.

        Args:
            provider_type: Type of provider (anthropic, openai, google, custom).
            base_url: Base URL for the API.
            api_key: Decrypted API key.
            config: Provider configuration.

        Returns:
            Tuple of (success, message).
        """
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                if provider_type == "anthropic":
                    url = base_url or "https://api.anthropic.com"
                    response = await client.get(
                        f"{url.rstrip('/')}/v1/models",
                        headers={
                            "x-api-key": api_key or "",
                            "anthropic-version": "2023-06-01"
                        }
                    )

                elif provider_type == "openai":
                    url = base_url or "https://api.openai.com"
                    response = await client.get(
                        f"{url.rstrip('/')}/v1/models",
                        headers={"Authorization": f"Bearer {api_key or ''}"}
                    )

                elif provider_type == "google":
                    # Google uses query param for API key
                    url = "https://generativelanguage.googleapis.com"
                    response = await client.get(
                        f"{url}/v1/models",
                        params={"key": api_key or ""}
                    )

                elif provider_type == "custom":
                    if not base_url:
                        return False, "Base URL is required for custom provider"

                    # Build headers based on auth type
                    headers = {}
                    auth_type = config.get("auth_type", "none")

                    if auth_type == "bearer" and api_key:
                        headers["Authorization"] = f"Bearer {api_key}"
                    elif auth_type == "api_key_header" and api_key:
                        header_name = config.get("auth_header_name", "X-API-Key")
                        headers[header_name] = api_key
                    elif auth_type == "basic" and api_key:
                        # Expect api_key to be "username:password"
                        import base64
                        encoded = base64.b64encode(api_key.encode()).decode()
                        headers["Authorization"] = f"Basic {encoded}"

                    # Add custom headers if configured
                    custom_headers = config.get("custom_headers", {})
                    headers.update(custom_headers)

                    # Try Ollama-compatible /api/tags endpoint first
                    try:
                        response = await client.get(
                            f"{base_url.rstrip('/')}/api/tags",
                            headers=headers
                        )
                    except httpx.RequestError:
                        # Fallback to OpenAI-compatible /v1/models
                        response = await client.get(
                            f"{base_url.rstrip('/')}/v1/models",
                            headers=headers
                        )

                else:
                    return False, f"Unknown provider type: {provider_type}"

                if response.status_code == 200:
                    return True, "OK"
                else:
                    error_text = response.text[:200] if response.text else "No response body"
                    return False, f"HTTP {response.status_code}: {error_text}"

            except httpx.TimeoutException:
                return False, "Connection timed out"
            except httpx.ConnectError as e:
                return False, f"Connection failed: {str(e)}"
            except Exception as e:
                return False, f"Request failed: {str(e)}"

    async def discover_models(self, provider_id: UUID) -> Dict[str, Any]:
        """Discover available models from a provider's API.

        Args:
            provider_id: UUID of the provider.

        Returns:
            Dict with success, models list, and optional error message.
        """
        provider = await self.get_provider(provider_id)
        if not provider:
            return {
                "success": False,
                "models": [],
                "message": "Provider not found"
            }

        # Decrypt API key if present
        api_key = None
        if provider.api_key_encrypted:
            api_key = decrypt_value(provider.api_key_encrypted)

        return await self.discover_models_from_config(
            provider_type=provider.provider_type,
            base_url=provider.base_url,
            api_key=api_key,
            config=provider.config or {}
        )

    async def discover_models_from_config(
        self,
        provider_type: str,
        base_url: Optional[str],
        api_key: Optional[str],
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Discover available models from provider config without saving.

        Args:
            provider_type: Type of provider.
            base_url: Base URL for the API.
            api_key: Plaintext API key.
            config: Provider configuration.

        Returns:
            Dict with success, models list, and optional error message.
        """
        try:
            models = await self._fetch_models_from_provider(
                provider_type=provider_type,
                base_url=base_url,
                api_key=api_key,
                config=config
            )

            return {
                "success": True if models else False,
                "models": models,
                "message": f"Found {len(models)} models" if models else "No models found"
            }

        except Exception as e:
            logger.error(f"Model discovery failed for {provider_type}: {e}")
            return {
                "success": False,
                "models": [],
                "message": str(e)
            }

    async def _fetch_models_from_provider(
        self,
        provider_type: str,
        base_url: Optional[str],
        api_key: Optional[str],
        config: Dict[str, Any]
    ) -> List[str]:
        """Fetch available models from a provider's API.

        Args:
            provider_type: Type of provider.
            base_url: Base URL for the API.
            api_key: Decrypted API key.
            config: Provider configuration.

        Returns:
            List of model IDs.
        """
        models: List[str] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            if provider_type == "anthropic":
                url = base_url or "https://api.anthropic.com"
                response = await client.get(
                    f"{url.rstrip('/')}/v1/models",
                    headers={
                        "x-api-key": api_key or "",
                        "anthropic-version": "2023-06-01"
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    # Anthropic returns {"data": [{"id": "model-id", ...}]}
                    models = [m.get("id") for m in data.get("data", []) if m.get("id")]

            elif provider_type == "openai":
                url = base_url or "https://api.openai.com"
                response = await client.get(
                    f"{url.rstrip('/')}/v1/models",
                    headers={"Authorization": f"Bearer {api_key or ''}"}
                )
                if response.status_code == 200:
                    data = response.json()
                    # OpenAI returns {"data": [{"id": "model-id", ...}]}
                    # Filter to only chat models
                    all_models = [m.get("id") for m in data.get("data", []) if m.get("id")]
                    # Prioritize GPT models
                    models = [m for m in all_models if "gpt" in m.lower() or "o1" in m.lower()]
                    if not models:
                        models = all_models[:20]  # Limit if too many

            elif provider_type == "google":
                url = "https://generativelanguage.googleapis.com"
                response = await client.get(
                    f"{url}/v1/models",
                    params={"key": api_key or ""}
                )
                if response.status_code == 200:
                    data = response.json()
                    # Google returns {"models": [{"name": "models/gemini-...", ...}]}
                    for m in data.get("models", []):
                        name = m.get("name", "")
                        # Extract model ID from "models/gemini-pro" format
                        if name.startswith("models/"):
                            model_id = name[7:]  # Remove "models/" prefix
                            # Only include generative models
                            if "gemini" in model_id.lower():
                                models.append(model_id)

            elif provider_type == "custom":
                if not base_url:
                    return []

                # Build headers
                headers = {}
                auth_type = config.get("auth_type", "none")

                if auth_type == "bearer" and api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                elif auth_type == "api_key_header" and api_key:
                    header_name = config.get("auth_header_name", "X-API-Key")
                    headers[header_name] = api_key

                # Try Ollama-compatible /api/tags first
                try:
                    response = await client.get(
                        f"{base_url.rstrip('/')}/api/tags",
                        headers=headers
                    )
                    if response.status_code == 200:
                        data = response.json()
                        # Ollama returns {"models": [{"name": "model:tag", ...}]}
                        models = [m.get("name") for m in data.get("models", []) if m.get("name")]
                        return models
                except httpx.RequestError:
                    pass

                # Fallback to OpenAI-compatible /v1/models
                try:
                    response = await client.get(
                        f"{base_url.rstrip('/')}/v1/models",
                        headers=headers
                    )
                    if response.status_code == 200:
                        data = response.json()
                        models = [m.get("id") for m in data.get("data", []) if m.get("id")]
                except httpx.RequestError:
                    pass

        return models
