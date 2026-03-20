"""Shared utilities for incident tools.

This module provides common components used by all incident search tools,
including lazy-initialized clients, embeddings, and formatting utilities.
"""

import logging
import os
from typing import List, Optional

from langchain.chains.query_constructor.base import (
    AttributeInfo,
    StructuredQueryOutputParser,
)
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain.schema import Document
from langchain_community.query_constructors.qdrant import QdrantTranslator
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

import src.copilot.config as config

logger = logging.getLogger(__name__)

# Metadata field definitions for self-query retriever
METADATA_FIELD_INFO = [
    AttributeInfo(
        name="incident_id",
        description="The unique identifier for an incident, e.g., 'INC-2025-08-24-001'",
        type="string",
    ),
    AttributeInfo(
        name="incident_title",
        description="The high-level title of the incident, e.g., 'Swift Transfer Delay' or 'HTTP 403'",
        type="string",
    ),
    AttributeInfo(
        name="impacted_application",
        description="The name of the software or system that was impacted, e.g., 'PayU Core Payments' or 'Settlement & Reporting'",
        type="string",
    ),
    AttributeInfo(
        name="root_cause",
        description="A summary of the root cause of the incident",
        type="string",
    ),
    AttributeInfo(
        name="mitigation",
        description="The steps taken to resolve or mitigate the incident",
        type="string",
    ),
    AttributeInfo(
        name="accountable_party",
        description="The team or entity responsible for the incident, e.g., 'DevOps/CI-CD' or 'Cloud Provider'",
        type="string",
    ),
    AttributeInfo(
        name="source_system",
        description="The system that reported the incident, e.g., 'Monitoring', 'PagerDuty', or 'ServiceNow'",
        type="string",
    ),
    AttributeInfo(
        name="repeat_incident",
        description="A boolean (as a string) indicating if this was a repeat incident, e.g., 'True.' or 'False.'",
        type="string",
    ),
    AttributeInfo(
        name="opened_at",
        description="Date/time when the incident was opened, in ISO 8601 format (e.g. '2025-01-15T10:30:00'). Use for filtering incidents by date range.",
        type="string",
    ),
    AttributeInfo(
        name="updated_at",
        description="Date/time when the incident was last updated, in ISO 8601 format.",
        type="string",
    ),
]

DOCUMENT_CONTENT_DESCRIPTION = (
    "A chunk of text from an incident report, containing details, actions taken, and analysis."
)

# Lazy-initialized components
_llm: Optional[BaseChatModel] = None
_embeddings: Optional[HuggingFaceEmbeddings] = None
_qdrant_client: Optional[QdrantClient] = None
_vector_store: Optional[QdrantVectorStore] = None
_retriever: Optional[SelfQueryRetriever] = None
_initialization_error: Optional[str] = None


def _get_provider_config_sync() -> dict:
    """Fetch LLM provider config from the DB using a sync connection.

    Returns a dict with provider_type, model_id, api_key, base_url,
    provider_config, and temperature.  Returns empty-ish config when
    the DB is unreachable or no provider is configured.
    """
    empty: dict = {"provider_type": None, "model_id": None, "api_key": None,
                    "base_url": None, "provider_config": {}, "temperature": 0}
    try:
        from sqlalchemy import create_engine, text

        db_url = os.getenv("DATABASE_URL", "")
        if not db_url:
            return empty

        sync_url = (db_url
                    .replace("postgresql+asyncpg", "postgresql")
                    .replace("postgresql+aiopg", "postgresql"))
        engine = create_engine(sync_url)

        with engine.connect() as conn:
            # Get settings
            row = conn.execute(
                text("SELECT provider_id, model, temperature FROM settings ORDER BY updated_at DESC LIMIT 1")
            ).fetchone()
            if not row:
                return empty

            provider_id = row[0]
            model_id = row[1]
            temperature = float(row[2]) if row[2] is not None else 0

            # Resolve provider
            if provider_id:
                prov = conn.execute(
                    text("SELECT provider_type, base_url, api_key_encrypted, config, models "
                         "FROM llm_providers WHERE id = :pid AND is_active = true"),
                    {"pid": str(provider_id)},
                ).fetchone()
            else:
                prov = conn.execute(
                    text("SELECT provider_type, base_url, api_key_encrypted, config, models "
                         "FROM llm_providers WHERE is_default = true AND is_active = true LIMIT 1")
                ).fetchone()

            if not prov:
                return empty

            # Decrypt api key
            api_key = None
            if prov[2]:
                try:
                    from src.api.services.encryption_service import decrypt_value
                    api_key = decrypt_value(prov[2])
                except Exception as e:
                    logger.error(f"Failed to decrypt API key for SelfQueryRetriever LLM: {e}")
                    return empty

            import json
            provider_config = prov[3] if isinstance(prov[3], dict) else (
                json.loads(prov[3]) if prov[3] else {}
            )
            models_list = prov[4] if isinstance(prov[4], list) else (
                json.loads(prov[4]) if prov[4] else []
            )

            # Validate model_id against provider's models
            if model_id and model_id in models_list:
                pass
            elif models_list:
                model_id = models_list[0]
            else:
                return empty

            return {
                "provider_type": prov[0],
                "model_id": model_id,
                "api_key": api_key,
                "base_url": prov[1],
                "provider_config": provider_config,
                "temperature": temperature,
            }
    except Exception as e:
        logger.warning(f"Could not fetch provider config for SelfQueryRetriever: {e}")
        return empty


def _get_llm() -> BaseChatModel:
    """Get or create the LLM instance for query processing.

    Uses the admin-configured provider from the database.
    Falls back to Ollama if no provider is configured.
    """
    global _llm
    if _llm is None:
        provider_cfg = _get_provider_config_sync()
        if provider_cfg.get("provider_type") and provider_cfg.get("model_id"):
            from src.copilot.llm_factory import create_llm_from_provider
            try:
                _llm = create_llm_from_provider(
                    provider_type=provider_cfg["provider_type"],
                    model_id=provider_cfg["model_id"],
                    api_key=provider_cfg.get("api_key"),
                    base_url=provider_cfg.get("base_url"),
                    provider_config=provider_cfg.get("provider_config", {}),
                    temperature=provider_cfg.get("temperature", 0),
                )
                logger.info(
                    f"SelfQueryRetriever using configured LLM: "
                    f"{provider_cfg['provider_type']}/{provider_cfg['model_id']}"
                )
                return _llm
            except Exception as e:
                logger.warning(f"Failed to create configured LLM for SelfQueryRetriever, "
                               f"falling back to Ollama: {e}")

        _llm = ChatOllama(
            model=config.DEFAULT_OLLAMA_MODEL,
            temperature=0,
            base_url=config.OLLAMA_API_URL,
            max_retries=config.DEFAULT_LLM_MAX_RETRIES,
            disable_streaming=True,
        )
    return _llm


def _get_embeddings() -> HuggingFaceEmbeddings:
    """Get or create the embeddings model."""
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    return _embeddings


def _get_qdrant_client() -> QdrantClient:
    """Get or create the Qdrant client with authentication if configured."""
    global _qdrant_client
    if _qdrant_client is None:
        qdrant_url = config.QDRANT_URL
        qdrant_api_key = config.QDRANT_API_KEY

        if not qdrant_url:
            raise ValueError("QDRANT_URL environment variable is not set")

        # Initialize with API key if available
        if qdrant_api_key:
            _qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        else:
            logger.warning("QDRANT_API_KEY not set - connecting without authentication")
            _qdrant_client = QdrantClient(url=qdrant_url)

    return _qdrant_client


def _get_active_collection_name() -> str:
    """Resolve the active dataset collection name from the DB.

    Falls back to the config default (``past_issues_v2``) when no active
    version exists or the DB is unreachable.
    """
    try:
        from src.api.db.base import Base  # noqa: F401 – ensures metadata is loaded
        from sqlalchemy import create_engine, text
        import os

        db_url = os.getenv("DATABASE_URL", "")
        if not db_url:
            return config.QDRANT_COLLECTION_NAME

        # Use a sync engine for this quick lookup (copilot runs sync code)
        sync_url = db_url.replace("postgresql+asyncpg", "postgresql").replace("postgresql+aiopg", "postgresql")
        engine = create_engine(sync_url)
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT collection_name FROM incident_dataset_versions WHERE is_active = true LIMIT 1")
            ).fetchone()
            if row:
                return row[0]
    except Exception:
        pass
    return config.QDRANT_COLLECTION_NAME


def _get_vector_store() -> QdrantVectorStore:
    """Get or create the vector store."""
    global _vector_store
    if _vector_store is None:
        _vector_store = QdrantVectorStore(
            client=_get_qdrant_client(),
            collection_name=_get_active_collection_name(),
            embedding=_get_embeddings(),
        )
    return _vector_store


def _get_retriever() -> Optional[SelfQueryRetriever]:
    """Get or create the self-query retriever."""
    global _retriever, _initialization_error

    if _retriever is not None:
        return _retriever

    if _initialization_error is not None:
        return None

    try:
        _retriever = SelfQueryRetriever.from_llm(
            llm=_get_llm(),
            vectorstore=_get_vector_store(),
            document_contents=DOCUMENT_CONTENT_DESCRIPTION,
            metadata_field_info=METADATA_FIELD_INFO,
            structured_query_translator=QdrantTranslator(metadata_key="metadata"),
            structured_query_parser=StructuredQueryOutputParser.from_components(),
        )
        return _retriever
    except Exception as e:
        _initialization_error = str(e)
        logger.error(f"Error initializing retriever: {e}")
        return None


def _get_metadata_value(metadata: dict, key: str, default: str = None) -> Optional[str]:
    """Safely get a metadata value, returning None for missing fields.

    Args:
        metadata: The metadata dictionary
        key: The key to retrieve
        default: Default value if key is missing (defaults to None)

    Returns:
        The value if present, otherwise the default
    """
    value = metadata.get(key, default)
    if value is None or (isinstance(value, str) and not value.strip()):
        return default
    return value


def format_incident_context(doc: Document) -> str:
    """Format a single incident document into readable context.

    Args:
        doc: The document containing incident data

    Returns:
        Formatted string with incident details
    """
    page_content = doc.page_content
    metadata = doc.metadata

    incident_id = _get_metadata_value(metadata, "incident_id")
    root_cause = _get_metadata_value(metadata, "root_cause")
    mitigation = _get_metadata_value(metadata, "mitigation")
    impacted_application = _get_metadata_value(metadata, "impacted_application")
    accountable_party = _get_metadata_value(metadata, "accountable_party")
    incident_title = _get_metadata_value(metadata, "incident_title")
    opened_at = _get_metadata_value(metadata, "opened_at")
    updated_at = _get_metadata_value(metadata, "updated_at")

    # Build context block with available fields
    context_lines = ["---"]
    if incident_id:
        context_lines.append(f"Incident ID: {incident_id}")
    if incident_title:
        context_lines.append(f"Title: {incident_title}")
    if opened_at:
        context_lines.append(f"Opened At: {opened_at}")
    if updated_at:
        context_lines.append(f"Updated At: {updated_at}")
    if root_cause:
        context_lines.append(f"Root Cause: {root_cause}")
    if mitigation:
        context_lines.append(f"Mitigation: {mitigation}")
    if impacted_application:
        context_lines.append(f"Impacted Application: {impacted_application}")
    if accountable_party:
        context_lines.append(f"Accountable Party: {accountable_party}")

    context_lines.append("")
    context_lines.append("Details and Actions Taken and Steps and Fixes:")
    context_lines.append(page_content)
    context_lines.append("---")

    return "\n".join(context_lines)


def format_incidents_response(docs: List[Document]) -> str:
    """Format multiple incidents into final response.

    Args:
        docs: List of incident documents

    Returns:
        Formatted string with all incident details, or message if none found
    """
    if not docs:
        return "No relevant incident reports found in the knowledge base."
    return "\n\n".join(format_incident_context(doc) for doc in docs)


def _scroll_all_incidents(
    qdrant_filter=None,
    limit: int = 5000,
) -> List[dict]:
    """Scroll Qdrant and return deduplicated incidents as dicts.

    Each incident appears once (deduped by incident_id), with structured
    metadata fields extracted.

    Args:
        qdrant_filter: Optional Qdrant Filter for server-side filtering.
        limit: Max unique incidents to return.

    Returns:
        List of incident dicts, sorted by opened_at descending.
    """
    vector_store = _get_vector_store()
    seen_ids: set = set()
    incidents: List[dict] = []
    next_page = None

    while len(incidents) < limit:
        points, next_page = vector_store.client.scroll(
            collection_name=vector_store.collection_name,
            scroll_filter=qdrant_filter,
            with_payload=True,
            with_vectors=False,
            limit=64,
            offset=next_page,
        )
        if not points:
            break

        for point in points:
            payload = point.payload or {}
            metadata = payload.get("metadata", {})
            inc_id = metadata.get("incident_id")
            if not inc_id or inc_id in seen_ids:
                continue
            seen_ids.add(inc_id)

            incidents.append({
                "incident_id": inc_id,
                "title": metadata.get("incident_title", "Unknown"),
                "opened_at": metadata.get("opened_at"),
                "updated_at": metadata.get("updated_at"),
                "impacted_application": metadata.get("impacted_application"),
                "root_cause": metadata.get("root_cause"),
                "accountable_party": metadata.get("accountable_party"),
                "repeat_incident": metadata.get("repeat_incident"),
            })

            if len(incidents) >= limit:
                break

        if next_page is None:
            break
    incidents.sort(key=lambda x: x.get("opened_at") or "", reverse=True)
    return incidents
