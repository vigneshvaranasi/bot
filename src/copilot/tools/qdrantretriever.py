"""Qdrant vector retriever tool for incident knowledge base search.

This module provides tools for searching past incident reports using
vector similarity and self-query retrieval.
"""

import logging
import os
import re
from typing import List, Optional

from langchain.chains.query_constructor.base import (
    AttributeInfo,
    StructuredQueryOutputParser,
)
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain.schema import Document
from langchain_community.query_constructors.qdrant import QdrantTranslator
from langchain_core.tools import tool
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama
from langchain_qdrant import QdrantVectorStore
from langgraph.config import get_stream_writer
from qdrant_client import QdrantClient
from qdrant_client.http.models import FieldCondition, Filter, MatchValue

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
]

DOCUMENT_CONTENT_DESCRIPTION = (
    "A chunk of text from an incident report, containing details, actions taken, and analysis."
)

# Lazy-initialized components
_llm: Optional[ChatOllama] = None
_embeddings: Optional[HuggingFaceEmbeddings] = None
_qdrant_client: Optional[QdrantClient] = None
_vector_store: Optional[QdrantVectorStore] = None
_retriever: Optional[SelfQueryRetriever] = None
_initialization_error: Optional[str] = None


def _get_llm() -> ChatOllama:
    """Get or create the LLM instance for query processing."""
    global _llm
    if _llm is None:
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


def _get_vector_store() -> QdrantVectorStore:
    """Get or create the vector store."""
    global _vector_store
    if _vector_store is None:
        _vector_store = QdrantVectorStore(
            client=_get_qdrant_client(),
            collection_name=config.QDRANT_COLLECTION_NAME,
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


@tool
def get_incident_report(message: str) -> str:
    """Search the internal knowledge base for technical incident reports.

    Use this to answer questions about error resolutions, root causes, mitigations,
    known issues, fixes, and workarounds.

    Args:
        message: The reconstructed user message with relevant context.
            Include specific incident IDs, root causes, or application names.

    Returns:
        Context blocks from relevant incident reports, or an error message.
    """
    writer = get_stream_writer()

    retriever = _get_retriever()
    if retriever is None:
        logger.error("Knowledge base retriever is not initialized")
        return "The knowledge base is currently unavailable. Please try again later."

    try:
        writer({"status": "Parsing query and searching incidents..."})

        normalized_query = message.replace("‑", "-")
        logger.debug(f"Normalized query: {normalized_query}")

        docs: List[Document] = []

        # Check for explicit incident IDs in the query
        incident_id_pattern = r"\bINC-\d{4}-\d{2}-\d{2}-\d{3,}\b"
        explicit_incident_ids = set(re.findall(incident_id_pattern, normalized_query))

        if explicit_incident_ids:
            writer({"status": "Fetching incident details by ID..."})

            for incident_id in explicit_incident_ids:
                qdrant_filter = Filter(
                    must=[
                        FieldCondition(
                            key="metadata.incident_id",
                            match=MatchValue(value=incident_id),
                        )
                    ]
                )

                try:
                    vector_store = _get_vector_store()
                    next_page = None
                    seen_points = set()

                    while True:
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
                            if point.id in seen_points:
                                continue
                            seen_points.add(point.id)

                            payload = point.payload or {}
                            metadata = payload.get("metadata", {})
                            page_content = payload.get("page_content", "")
                            docs.append(
                                Document(
                                    page_content=page_content,
                                    metadata=metadata,
                                )
                            )

                        if next_page is None:
                            break

                except Exception as scroll_error:
                    logger.error(
                        "Error fetching incident %s via direct lookup: %s",
                        incident_id,
                        scroll_error,
                    )

        # Fall back to semantic search if no direct matches
        if not docs:
            docs = retriever.invoke(
                input=normalized_query,
                config={"stream": False},
            )

        if not docs:
            return "No relevant incident reports found in the knowledge base."

        context_blocks = []
        incident_ids = set()

        for doc in docs:
            page_content = doc.page_content
            metadata = doc.metadata

            incident_id = _get_metadata_value(metadata, "incident_id")
            if incident_id:
                incident_ids.add(incident_id)

            root_cause = _get_metadata_value(metadata, "root_cause")
            mitigation = _get_metadata_value(metadata, "mitigation")
            impacted_application = _get_metadata_value(metadata, "impacted_application")
            accountable_party = _get_metadata_value(metadata, "accountable_party")
            incident_title = _get_metadata_value(metadata, "incident_title")

            # Build context block with available fields
            context_lines = ["---"]
            if incident_id:
                context_lines.append(f"Incident ID: {incident_id}")
            if incident_title:
                context_lines.append(f"Title: {incident_title}")
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

            context_blocks.append("\n".join(context_lines))

        writer({"status": f"Found {len(incident_ids)} relevant incidents..."})
        logger.debug(f"Retrieved incident IDs: {', '.join(incident_ids)}")

        return "\n\n".join(context_blocks)

    except Exception as e:
        logger.error(f"Error in get_incident_report: {e}")
        # Return generic error message - don't expose internal details
        return (
            "An error occurred while searching for incident reports. "
            "Please try rephrasing your query or contact support if the issue persists."
        )


available_tools = [get_incident_report]
