"""Specialized tools for incident knowledge base search.

This module provides specialized tools for different types of incident queries,
improving LLM tool selection accuracy and maintainability.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Callable

from langchain.schema import Document
from langchain_core.tools import tool
from langgraph.config import get_stream_writer
from collections import defaultdict

from qdrant_client.http.models import DatetimeRange, FieldCondition, Filter, MatchValue

from src.copilot.tools._base import (
    _get_metadata_value,
    _get_retriever,
    _get_vector_store,
    _scroll_all_incidents,
    format_incidents_response,
)

logger = logging.getLogger(__name__)


def _get_safe_stream_writer() -> Callable:
    """Get stream writer if available, otherwise return a no-op function.
    
    This allows tools to work both within LangGraph context (with streaming)
    and outside of it
    """
    try:
        writer = get_stream_writer()
        return writer
    except Exception:
        return lambda x: None


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
    writer = _get_safe_stream_writer()
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
    writer = _get_safe_stream_writer()
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
    writer = _get_safe_stream_writer()
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
    writer = _get_safe_stream_writer()
    writer({"status": f"Searching incidents from the last {days} days..."})

    try:
        now = datetime.now()
        cutoff_date = (now - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00")
        today_end = now.strftime("%Y-%m-%dT23:59:59")

        # Filter by opened_at metadata with both lower and upper bounds
        qdrant_filter = Filter(
            must=[
                FieldCondition(
                    key="metadata.opened_at",
                    range=DatetimeRange(gte=cutoff_date),
                ),
                FieldCondition(
                    key="metadata.opened_at",
                    range=DatetimeRange(lte=today_end),
                ),
            ]
        )

        docs = _scroll_qdrant_with_filter(qdrant_filter, limit=limit * 3)

        # Deduplicate by incident_id
        seen: set = set()
        unique_docs: List[Document] = []
        for doc in docs:
            inc_id = _get_metadata_value(doc.metadata, "incident_id")
            if inc_id and inc_id not in seen:
                seen.add(inc_id)
                unique_docs.append(doc)
                if len(unique_docs) >= limit:
                    break

        if unique_docs:
            writer({"status": f"Found {len(unique_docs)} incidents from the last {days} days"})
            return format_incidents_response(unique_docs)

        # Fallback: no opened_at data matched — return latest by scroll order
        writer({"status": "No date-filtered incidents found, returning latest incidents"})
        fallback_docs = _scroll_qdrant_with_filter(Filter(must=[]), limit=limit * 3)
        seen_fb: set = set()
        unique_fb: List[Document] = []
        for doc in fallback_docs:
            inc_id = _get_metadata_value(doc.metadata, "incident_id")
            if inc_id and inc_id not in seen_fb:
                seen_fb.add(inc_id)
                unique_fb.append(doc)
                if len(unique_fb) >= limit:
                    break
        return format_incidents_response(unique_fb)

    except Exception as e:
        logger.error(f"Error in get_recent_incidents: {e}")
        return (
            "An error occurred while searching for recent incidents. "
            "Please try again or contact support if the issue persists."
        )


@tool
def get_incident_statistics(
    start_date: str,
    end_date: str,
    group_by: str = "month",
) -> str:
    """Get incident counts grouped by time period or category.

    Use this for reports, counts, and trends:
    - "Monthly report of incidents from last 2 years"
    - "How many incidents this week?"
    - "Incidents grouped by month for last 6 months"
    - "Incidents by application this year"

    Args:
        start_date: Start date in ISO format (YYYY-MM-DD).
        end_date: End date in ISO format (YYYY-MM-DD).
        group_by: How to group results. Options: "day", "week", "month", "year", "application".

    Returns:
        Formatted markdown table with grouped counts.
    """
    writer = _get_safe_stream_writer()
    writer({"status": f"Generating incident report ({start_date} to {end_date}, grouped by {group_by})..."})

    try:
        # Build Qdrant range filter on opened_at
        qdrant_filter = Filter(
            must=[
                FieldCondition(key="metadata.opened_at", range=DatetimeRange(gte=start_date)),
                FieldCondition(key="metadata.opened_at", range=DatetimeRange(lt=end_date)),
            ]
        )

        # Scroll all matching incidents (deduplicated)
        incidents = _scroll_all_incidents(qdrant_filter=qdrant_filter, limit=10000)

        if not incidents:
            return f"No incidents found between {start_date} and {end_date}."

        # Group by the requested dimension
        groups: dict = defaultdict(int)

        for inc in incidents:
            opened = inc.get("opened_at") or ""

            if group_by == "application":
                key = inc.get("impacted_application") or "Unknown"
            elif group_by == "day":
                key = opened[:10] if len(opened) >= 10 else "Unknown"
            elif group_by == "week":
                if len(opened) >= 10:
                    try:
                        dt = datetime.fromisoformat(opened[:19])
                        key = f"{dt.year}-W{dt.isocalendar()[1]:02d}"
                    except (ValueError, TypeError):
                        key = "Unknown"
                else:
                    key = "Unknown"
            elif group_by == "year":
                key = opened[:4] if len(opened) >= 4 else "Unknown"
            else:  # month (default)
                key = opened[:7] if len(opened) >= 7 else "Unknown"

            groups[key] += 1

        # Sort groups
        if group_by == "application":
            sorted_groups = sorted(groups.items(), key=lambda x: x[1], reverse=True)
        else:
            sorted_groups = sorted(groups.items(), key=lambda x: x[0])

        total = sum(groups.values())

        # Format as markdown table
        if group_by == "application":
            header = "| Application | Count |"
            separator = "|-------------|-------|"
        else:
            header = "| Period | Count |"
            separator = "|--------|-------|"

        lines = [
            f"Incident Report ({start_date} to {end_date}) — Grouped by {group_by}",
            "",
            header,
            separator,
        ]
        for key, count in sorted_groups:
            lines.append(f"| {key} | {count} |")
        lines.append(f"| **Total** | **{total}** |")

        writer({"status": f"Found {total} incidents in {len(groups)} groups"})
        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error in get_incident_statistics: {e}")
        return "An error occurred while generating incident statistics."


@tool
def get_recurring_incidents(
    start_date: str,
    end_date: str,
    limit: int = 10,
) -> str:
    """Find the most frequently recurring incidents.

    Use this for questions like:
    - "What are the most recurring incidents?"
    - "Top repeated issues in the last 6 months"
    - "Which incidents keep happening?"

    Args:
        start_date: Start date in ISO format (YYYY-MM-DD).
        end_date: End date in ISO format (YYYY-MM-DD).
        limit: Max number of results to return (default: 10).

    Returns:
        Formatted table of recurring incidents ranked by frequency.
    """
    writer = _get_safe_stream_writer()
    writer({"status": f"Analyzing recurring incidents ({start_date} to {end_date})..."})

    try:
        qdrant_filter = Filter(
            must=[
                FieldCondition(key="metadata.opened_at", range=DatetimeRange(gte=start_date)),
                FieldCondition(key="metadata.opened_at", range=DatetimeRange(lt=end_date)),
            ]
        )

        incidents = _scroll_all_incidents(qdrant_filter=qdrant_filter, limit=10000)

        if not incidents:
            return f"No incidents found between {start_date} and {end_date}."

        # Group by title (normalized) to find repeats
        title_groups: dict = defaultdict(list)
        for inc in incidents:
            title_key = (inc.get("title") or "Unknown").strip().lower()
            title_groups[title_key].append(inc)

        # Filter to recurring (2+ occurrences), sort by count
        recurring = [
            (title, incs)
            for title, incs in title_groups.items()
            if len(incs) >= 2
        ]
        recurring.sort(key=lambda x: len(x[1]), reverse=True)
        recurring = recurring[:limit]

        if not recurring:
            return f"No recurring incidents found between {start_date} and {end_date}. All incidents were unique."

        total_recurring = sum(len(incs) for _, incs in recurring)

        lines = [
            f"Recurring Incidents ({start_date} to {end_date})",
            "",
            "| Title | App | Count | First Seen | Last Seen |",
            "|-------|-----|-------|------------|-----------|",
        ]

        for _, incs in recurring:
            rep = incs[0]
            title = rep.get("title", "Unknown")
            app = rep.get("impacted_application") or "—"
            count = len(incs)
            dates = sorted(i.get("opened_at") or "" for i in incs)
            first = dates[0][:10] if dates[0] else "—"
            last = dates[-1][:10] if dates[-1] else "—"
            if len(title) > 50:
                title = title[:47] + "..."
            lines.append(f"| {title} | {app} | {count} | {first} | {last} |")

        lines.append(f"\n**Total:** {total_recurring} incidents across {len(recurring)} recurring patterns")

        writer({"status": f"Found {len(recurring)} recurring patterns"})
        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error in get_recurring_incidents: {e}")
        return "An error occurred while analyzing recurring incidents."
