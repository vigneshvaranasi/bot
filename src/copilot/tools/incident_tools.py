"""Specialized tools for incident knowledge base search.

This module provides specialized tools for different types of incident queries,
improving LLM tool selection accuracy and maintainability.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import List

from langchain.schema import Document
from langchain_core.tools import tool
from langgraph.config import get_stream_writer
from qdrant_client.http.models import FieldCondition, Filter, MatchValue, Range

from src.copilot.tools._base import (
    _get_metadata_value,
    _get_retriever,
    _get_vector_store,
    format_incidents_response,
)

logger = logging.getLogger(__name__)


def _scroll_qdrant_with_filter(qdrant_filter: Filter, limit: int = 100) -> List[Document]:
    """Helper to scroll through Qdrant with a filter and return Documents.

    Args:
        qdrant_filter: The Qdrant filter to apply
        limit: Maximum number of documents to return

    Returns:
        List of matching Documents
    """
    docs: List[Document] = []
    vector_store = _get_vector_store()
    next_page = None
    seen_points = set()

    while len(docs) < limit:
        points, next_page = vector_store.client.scroll(
            collection_name=vector_store.collection_name,
            scroll_filter=qdrant_filter,
            with_payload=True,
            with_vectors=False,
            limit=min(64, limit - len(docs)),
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

    return docs


@tool
def lookup_incident_by_id(incident_id: str) -> str:
    """Fetch a specific incident by its ID (e.g., INC-2025-08-24-001).

    Use this tool when the user mentions a specific incident ID.
    This performs a fast direct lookup without semantic search.

    Args:
        incident_id: The incident ID to look up (e.g., 'INC-2025-08-24-001')

    Returns:
        Detailed incident report or message if not found.
    """
    writer = get_stream_writer()
    writer({"status": f"Searching for {incident_id}..."})

    # Normalize the incident ID (handle unicode hyphens)
    normalized_id = incident_id.replace("‑", "-").strip()

    try:
        qdrant_filter = Filter(
            must=[
                FieldCondition(
                    key="metadata.incident_id",
                    match=MatchValue(value=normalized_id),
                )
            ]
        )

        docs = _scroll_qdrant_with_filter(qdrant_filter)

        if docs:
            incident_ids = set()
            for doc in docs:
                inc_id = _get_metadata_value(doc.metadata, "incident_id")
                if inc_id:
                    incident_ids.add(inc_id)
            writer({"status": f"Found incident {', '.join(incident_ids)}..."})
        else:
            writer({"status": f"No incident found with ID {normalized_id}"})

        return format_incidents_response(docs)

    except Exception as e:
        logger.error(f"Error in lookup_incident_by_id: {e}")
        return (
            f"An error occurred while looking up incident {incident_id}. "
            "Please try again or contact support if the issue persists."
        )


@tool
def search_similar_incidents(query: str, limit: int = 5) -> str:
    """Search for incidents similar to a description or error message.

    Use this tool when the user describes a problem, error, or symptom
    without mentioning a specific incident ID. This performs semantic
    similarity search across all incident reports.

    Args:
        query: The problem description, error message, or search query
        limit: Maximum number of incidents to return (default: 5)

    Returns:
        Matching incident reports or message if none found.
    """
    writer = get_stream_writer()
    writer({"status": "Searching for Similar Incidents..."})

    retriever = _get_retriever()
    vector_store = _get_vector_store()

    if retriever is None and vector_store is None:
        logger.error("Knowledge base retriever is not initialized")
        return "The knowledge base is currently unavailable. Please try again later."

    try:
        # Normalize the query (handle unicode hyphens)
        normalized_query = query.replace("‑", "-")

        docs = []

        # Try SelfQueryRetriever first (for precision with metadata filters)
        if retriever is not None:
            try:
                docs = retriever.invoke(
                    input=normalized_query,
                    config={"stream": False},
                )
            except Exception as retriever_error:
                logger.warning(f"SelfQueryRetriever failed, falling back to vector search: {retriever_error}")

        # Fallback to pure vector search if SelfQueryRetriever returns empty
        if not docs and vector_store is not None:
            logger.info(f"SelfQueryRetriever returned empty, trying pure vector search for: {normalized_query}")
            writer({"status": "Expanding search..."})
            docs = vector_store.similarity_search(
                query=normalized_query,
                k=limit * 2,  # Get more results to dedupe
            )

        # Limit results
        docs = docs[:limit] if len(docs) > limit else docs

        if docs:
            incident_ids = set()
            for doc in docs:
                inc_id = _get_metadata_value(doc.metadata, "incident_id")
                if inc_id:
                    incident_ids.add(inc_id)
            writer({"status": f"Found {len(incident_ids)} relevant incidents..."})
        else:
            writer({"status": "No similar incidents found"})

        return format_incidents_response(docs)

    except Exception as e:
        logger.error(f"Error in search_similar_incidents: {e}")
        return (
            "An error occurred while searching for incidents. "
            "Please try rephrasing your query or contact support if the issue persists."
        )


@tool
def get_incidents_by_application(app_name: str, limit: int = 5) -> str:
    """Find incidents affecting a specific application or system.

    Use this tool when the user asks about incidents for a particular
    application, service, or system (e.g., 'PayU Core', 'Settlement & Reporting').

    Args:
        app_name: The application or system name to search for
        limit: Maximum number of incidents to return (default: 5)

    Returns:
        Incident reports for the application or message if none found.
    """
    writer = get_stream_writer()
    writer({"status": f"Searching incidents for {app_name}..."})

    try:
        # Use text matching for application name (case-insensitive via Qdrant's match)
        qdrant_filter = Filter(
            must=[
                FieldCondition(
                    key="metadata.impacted_application",
                    match=MatchValue(value=app_name),
                )
            ]
        )

        docs = _scroll_qdrant_with_filter(qdrant_filter, limit=limit * 10)

        # Deduplicate by incident_id and limit
        seen_incidents = set()
        unique_docs = []
        for doc in docs:
            inc_id = _get_metadata_value(doc.metadata, "incident_id")
            if inc_id and inc_id not in seen_incidents:
                seen_incidents.add(inc_id)
                unique_docs.append(doc)
                if len(unique_docs) >= limit:
                    break

        if unique_docs:
            writer({"status": f"Found {len(unique_docs)} incidents for {app_name}..."})
        else:
            # Try a partial match using semantic search as fallback
            writer({"status": f"Trying broader search for {app_name}..."})
            retriever = _get_retriever()
            if retriever:
                broader_query = f"incidents affecting {app_name}"
                docs = retriever.invoke(
                    input=broader_query,
                    config={"stream": False},
                )
                unique_docs = docs[:limit] if len(docs) > limit else docs

        if unique_docs:
            incident_ids = set()
            for doc in unique_docs:
                inc_id = _get_metadata_value(doc.metadata, "incident_id")
                if inc_id:
                    incident_ids.add(inc_id)
            writer({"status": f"Found {len(incident_ids)} incidents for {app_name}..."})

        return format_incidents_response(unique_docs)

    except Exception as e:
        logger.error(f"Error in get_incidents_by_application: {e}")
        return (
            f"An error occurred while searching for incidents affecting {app_name}. "
            "Please try again or contact support if the issue persists."
        )


@tool
def get_recent_incidents(days: int = 7, limit: int = 10) -> str:
    """Get incidents from the last N days.

    Use this tool when the user asks about recent incidents or
    incidents within a specific timeframe (e.g., 'last week', 'past month').

    Args:
        days: Number of days to look back (default: 7)
        limit: Maximum number of incidents to return (default: 10)

    Returns:
        Recent incident reports or message if none found.
    """
    writer = get_stream_writer()
    writer({"status": f"Searching incidents from the last {days} days..."})

    try:
        # Calculate the cutoff date
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")

        # Get all incidents and filter by date parsed from incident_id
        # Incident ID format: INC-YYYY-MM-DD-NNN
        # We'll use a broad filter first, then filter in Python

        vector_store = _get_vector_store()
        all_docs: List[Document] = []
        next_page = None
        seen_points = set()

        # Scroll through all incidents (no filter - we'll filter by date in Python)
        while len(all_docs) < 1000:  # Safety limit
            points, next_page = vector_store.client.scroll(
                collection_name=vector_store.collection_name,
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
                all_docs.append(
                    Document(
                        page_content=page_content,
                        metadata=metadata,
                    )
                )

            if next_page is None:
                break

        # Filter by date from incident_id (format: INC-YYYY-MM-DD-NNN)
        date_pattern = r"INC-(\d{4}-\d{2}-\d{2})-\d+"
        recent_docs = []
        seen_incidents = set()

        for doc in all_docs:
            inc_id = _get_metadata_value(doc.metadata, "incident_id")
            if not inc_id or inc_id in seen_incidents:
                continue

            match = re.match(date_pattern, inc_id)
            if match:
                incident_date_str = match.group(1)
                try:
                    incident_date = datetime.strptime(incident_date_str, "%Y-%m-%d")
                    if incident_date >= cutoff_date:
                        seen_incidents.add(inc_id)
                        recent_docs.append(doc)
                        if len(recent_docs) >= limit:
                            break
                except ValueError:
                    continue

        # Sort by date (most recent first)
        def get_incident_date(doc):
            inc_id = _get_metadata_value(doc.metadata, "incident_id") or ""
            match = re.match(date_pattern, inc_id)
            if match:
                try:
                    return datetime.strptime(match.group(1), "%Y-%m-%d")
                except ValueError:
                    pass
            return datetime.min

        recent_docs.sort(key=get_incident_date, reverse=True)

        if recent_docs:
            incident_ids = set()
            for doc in recent_docs:
                inc_id = _get_metadata_value(doc.metadata, "incident_id")
                if inc_id:
                    incident_ids.add(inc_id)
            writer({"status": f"Found {len(incident_ids)} incidents from the last {days} days..."})
        else:
            writer({"status": f"No incidents found in the last {days} days"})

        return format_incidents_response(recent_docs)

    except Exception as e:
        logger.error(f"Error in get_recent_incidents: {e}")
        return (
            f"An error occurred while searching for recent incidents. "
            "Please try again or contact support if the issue persists."
        )
