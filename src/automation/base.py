"""Base connector interface for third-party integrations."""

from abc import ABC, abstractmethod
from typing import Any


class BaseConnector(ABC):
    """Abstract base class for all integration connectors.

    Every connector must implement:
      - fetch_incidents(last_synced) -> list of raw dicts from the external API
      - normalize(raw_record)        -> standardised incident dict

    Subclasses should also declare:
      - CONNECTOR_TYPE  : slug used in the registry (e.g. "servicenow", "jira")
      - REQUIRED_CONFIG : set of config keys required for this connector
      - AUTH_TYPES       : set of supported auth_type values
    """

    CONNECTOR_TYPE: str = ""
    REQUIRED_CONFIG: set[str] = set()
    AUTH_TYPES: set[str] = set()

    @abstractmethod
    def fetch_incidents(self, last_synced: str) -> list[dict[str, Any]]:
        """Fetch raw incidents updated after *last_synced* (UTC string).

        Must handle pagination internally and return the full list.
        """

    @abstractmethod
    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Map a single raw record to the standard incident schema:

        Required keys: incident_id, title, description
        Optional keys: action_taken, opened_at, updated_at, state,
                       assigned_to, assignment_group, resolved_at,
                       closed_at, resolution_code, category, subcategory,
                       priority, impact, urgency, source_id
        """

    def fetch_and_normalize(self, last_synced: str) -> list[dict[str, Any]]:
        """Convenience: fetch + normalize + deduplicate in one call."""
        raw_records = self.fetch_incidents(last_synced)
        seen_ids: set[str] = set()
        results: list[dict[str, Any]] = []
        for raw in raw_records:
            normalized = self.normalize(raw)
            inc_id = normalized.get("incident_id")
            if inc_id and inc_id in seen_ids:
                continue
            if inc_id:
                seen_ids.add(inc_id)
            results.append(normalized)
        return results

    @classmethod
    def validate_config(cls, config: dict, auth_type: str) -> str | None:
        """Return an error message if config is invalid, else None."""
        missing = [k for k in cls.REQUIRED_CONFIG if not config.get(k)]
        if missing:
            return f"Missing required configuration: {', '.join(missing)}"
        if cls.AUTH_TYPES and auth_type not in cls.AUTH_TYPES:
            return f"Unsupported auth type '{auth_type}'. Supported: {', '.join(cls.AUTH_TYPES)}"
        return None