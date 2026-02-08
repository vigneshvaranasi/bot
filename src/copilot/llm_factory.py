"""LLM Provider Factory for dynamic model instantiation.

This module provides factory functions to create LangChain chat models
based on configured providers stored in the database.
"""

import logging
from typing import Any, Dict, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama

import src.copilot.config as config

logger = logging.getLogger(__name__)

# Lazy imports for optional providers to avoid import errors if not installed
_anthropic_available = False
_openai_available = False
_google_available = False

try:
    from langchain_anthropic import ChatAnthropic
    _anthropic_available = True
except ImportError:
    logger.debug("langchain-anthropic not installed, Anthropic provider unavailable")

try:
    from langchain_openai import ChatOpenAI
    _openai_available = True
except ImportError:
    logger.debug("langchain-openai not installed, OpenAI provider unavailable")

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    _google_available = True
except ImportError:
    logger.debug("langchain-google-genai not installed, Google provider unavailable")


# Default LLM settings
DEFAULT_TEMPERATURE = 0.33
DEFAULT_MAX_RETRIES = 2


def create_llm_from_provider(
    provider_type: str,
    model_id: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    provider_config: Optional[Dict[str, Any]] = None,
    temperature: float = DEFAULT_TEMPERATURE,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> BaseChatModel:
    """Create a LangChain chat model from provider configuration.

    Args:
        provider_type: Type of provider (anthropic, openai, google, custom).
        model_id: Model identifier (e.g., 'claude-3-opus-20240229', 'gpt-4').
        api_key: API key for the provider (decrypted).
        base_url: Optional base URL for custom endpoints or proxies.
        provider_config: Additional provider-specific configuration.
        temperature: LLM temperature setting.
        max_retries: Maximum retry attempts for API calls.

    Returns:
        Configured BaseChatModel instance.

    Raises:
        ValueError: If provider type is unsupported or required dependencies missing.
    """
    provider_config = provider_config or {}

    if provider_type == "anthropic":
        if not _anthropic_available:
            raise ValueError(
                "Anthropic provider requires langchain-anthropic package. "
                "Install with: pip install langchain-anthropic"
            )
        if not api_key:
            raise ValueError("Anthropic provider requires an API key")

        kwargs = {
            "model": model_id,
            "api_key": api_key,
            "temperature": temperature,
            "max_retries": max_retries,
        }
        if base_url:
            kwargs["base_url"] = base_url

        logger.info(f"Creating Anthropic LLM with model: {model_id}")
        return ChatAnthropic(**kwargs)

    elif provider_type == "openai":
        if not _openai_available:
            raise ValueError(
                "OpenAI provider requires langchain-openai package. "
                "Install with: pip install langchain-openai"
            )
        if not api_key:
            raise ValueError("OpenAI provider requires an API key")

        kwargs = {
            "model": model_id,
            "api_key": api_key,
            "temperature": temperature,
            "max_retries": max_retries,
        }
        if base_url:
            kwargs["base_url"] = base_url

        # Handle organization ID if provided
        if provider_config.get("organization_id"):
            kwargs["organization"] = provider_config["organization_id"]

        logger.info(f"Creating OpenAI LLM with model: {model_id}")
        return ChatOpenAI(**kwargs)

    elif provider_type == "google":
        if not _google_available:
            raise ValueError(
                "Google provider requires langchain-google-genai package. "
                "Install with: pip install langchain-google-genai"
            )
        if not api_key:
            raise ValueError("Google provider requires an API key")

        kwargs = {
            "model": model_id,
            "google_api_key": api_key,
            "temperature": temperature,
            "max_retries": max_retries,
        }

        logger.info(f"Creating Google LLM with model: {model_id}")
        return ChatGoogleGenerativeAI(**kwargs)

    elif provider_type == "custom":
        # Custom provider uses Ollama-compatible or OpenAI-compatible API
        if not base_url:
            raise ValueError("Custom provider requires a base URL")

        auth_type = provider_config.get("auth_type", "none")

        # Check if it's OpenAI-compatible (has /v1/chat/completions endpoint)
        is_openai_compatible = provider_config.get("openai_compatible", False)

        if is_openai_compatible and _openai_available:
            # Use OpenAI client for OpenAI-compatible APIs
            kwargs = {
                "model": model_id,
                "base_url": base_url,
                "temperature": temperature,
                "max_retries": max_retries,
            }

            if auth_type == "bearer" and api_key:
                kwargs["api_key"] = api_key
            elif auth_type == "none":
                # Some local models don't need auth
                kwargs["api_key"] = "not-needed"

            logger.info(f"Creating OpenAI-compatible LLM at {base_url} with model: {model_id}")
            return ChatOpenAI(**kwargs)
        else:
            # Default to Ollama-compatible API
            kwargs = {
                "model": model_id,
                "base_url": base_url,
                "temperature": temperature,
                "max_retries": max_retries,
            }

            logger.info(f"Creating Ollama-compatible LLM at {base_url} with model: {model_id}")
            return ChatOllama(**kwargs)

    else:
        raise ValueError(f"Unsupported provider type: {provider_type}")


def get_default_llm(
    temperature: float = DEFAULT_TEMPERATURE,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> BaseChatModel:
    """Get the default Ollama LLM from environment configuration.

    This is the fallback when no provider is configured in the database.

    Args:
        temperature: LLM temperature setting.
        max_retries: Maximum retry attempts.

    Returns:
        ChatOllama instance configured from environment variables.
    """
    logger.info(
        f"Creating default Ollama LLM: {config.DEFAULT_OLLAMA_MODEL} "
        f"at {config.OLLAMA_API_URL}"
    )
    return ChatOllama(
        model=config.DEFAULT_OLLAMA_MODEL,
        temperature=temperature,
        base_url=config.OLLAMA_API_URL,
        max_retries=max_retries,
    )


def create_llm_from_state(
    state: Dict[str, Any],
    temperature: Optional[float] = None,
) -> BaseChatModel:
    """Create an LLM instance based on agent state configuration.

    This function extracts provider configuration from the agent state
    and creates the appropriate LLM instance.

    Args:
        state: Agent state dictionary containing optional provider config:
            - provider_type: Type of provider
            - model_id: Model identifier
            - api_key: Decrypted API key
            - base_url: Provider base URL
            - provider_config: Additional config
            - temperature: Optional temperature override
        temperature: Override temperature (uses state value or default if None).

    Returns:
        Configured BaseChatModel instance.
    """
    # Check if provider configuration is present in state
    provider_type = state.get("provider_type")
    model_id = state.get("model_id")

    if not provider_type or not model_id:
        # No provider configured, use default
        logger.debug("No provider configuration in state, using default Ollama")
        return get_default_llm(
            temperature=temperature or state.get("temperature", DEFAULT_TEMPERATURE)
        )

    # Use provider from state
    return create_llm_from_provider(
        provider_type=provider_type,
        model_id=model_id,
        api_key=state.get("api_key"),
        base_url=state.get("base_url"),
        provider_config=state.get("provider_config", {}),
        temperature=temperature or state.get("temperature", DEFAULT_TEMPERATURE),
    )
