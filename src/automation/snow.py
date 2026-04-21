"""ServiceNow connector — fetches and normalises incidents via the Table API."""

import logging
from typing import Any

import requests

from src.automation.base import BaseConnector

logger = logging.getLogger(__name__)

_PAGE_SIZE = 500
_REQUEST_TIMEOUT = 100  # seconds

class ServiceNowConnector(BaseConnector):
    CONNECTOR_TYPE = "servicenow"
    REQUIRED_CONFIG: set[str] = {"url"}
    AUTH_TYPES: set[str] = {"basic_auth", "api_token", "oauth2"}

    _FIELDS = (
        "sys_id,"
        "number,"
        "short_description,"
        "description,"
        "state,"
        "impact,"
        "urgency,"
        "priority,"
        "category,"
        "subcategory,"
        "assigned_to,"
        "assignment_group,"
        "comments,"
        "work_notes,"
        "comments_and_work_notes,"
        "opened_at,"
        "resolved_at,"
        "closed_at,"
        "close_notes,"
        "resolution_code,"
        "sys_updated_on"
    )

    def __init__(self, config: dict[str, Any]):
        self.url = config["url"].rstrip("/")
        self.table_api = f"{self.url}/api/now/table/incident"
        self._auth = self._build_auth(config)
        self._headers: dict[str, str] = {"Accept": "application/json"}
    @staticmethod
    def _build_auth(config: dict) -> tuple | dict:
        """Build requests auth from config. Supports basic_auth and api_token."""
        auth_type = config.get("auth_type", "basic_auth")

        if auth_type == "basic_auth":
            username = config.get("username")
            password = config.get("password")
            if not username or not password:
                raise ValueError("basic_auth requires 'username' and 'password' in config")
            return (username, password)

        if auth_type == "api_token":
            email = config.get("email")
            api_token = config.get("api_token")
            if not email or not api_token:
                raise ValueError("api_token auth requires 'email' and 'api_token' in config")
            return (email, api_token)

        if auth_type == "oauth2":
            # OAuth2: expect an access_token already obtained
            access_token = config.get("access_token")
            if not access_token:
                raise ValueError("oauth2 auth requires 'access_token' in config")
            return {"Authorization": f"Bearer {access_token}"}

        raise ValueError(f"Unsupported auth type: {auth_type}")

    def fetch_incidents(self, last_synced: str) -> list[dict[str, Any]]:
        """Fetch all incidents updated after *last_synced* with full pagination."""
        all_records: list[dict] = []
        offset = 0

        while True:
            params = {
                "sysparm_query": f"sys_updated_on>={last_synced}^ORDERBYsys_updated_on",
                "sysparm_fields": self._FIELDS,
                "sysparm_limit": _PAGE_SIZE,
                "sysparm_offset": offset,
            }

            headers = dict(self._headers)
            if isinstance(self._auth, dict):
                headers.update(self._auth)
                auth = None
            else:
                auth = self._auth

            response = requests.get(
                self.table_api,
                auth=auth,
                params=params,
                headers=headers,
                timeout=_REQUEST_TIMEOUT,
            )

            if response.status_code == 401:
                raise PermissionError("Authentication failed — check credentials")
            if response.status_code == 429:
                raise RuntimeError("ServiceNow rate limit exceeded — retry later")
            if response.status_code != 200:
                raise RuntimeError(
                    f"ServiceNow API error {response.status_code}: {response.text[:500]}"
                )

            records = response.json().get("result", [])
            if not records:
                break

            all_records.extend(records)
            logger.info(
                "SNOW fetch page offset=%d returned %d records (total so far: %d)",
                offset, len(records), len(all_records),
            )

            if len(records) < _PAGE_SIZE:
                break
            offset += _PAGE_SIZE

        return all_records


    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Map a raw SNOW incident record to the standard schema."""
        lines = []
        if raw.get("short_description"):
            lines.append(raw["short_description"])
        if raw.get("description"):
            lines.append(f"Details: {raw['description']}")
        if raw.get("category"):
            lines.append(f"Category: {raw['category']}")
        if raw.get("subcategory"):
            lines.append(f"Subcategory: {raw['subcategory']}")
        if raw.get("priority"):
            lines.append(f"Priority: {raw['priority']}")
        if raw.get("impact"):
            lines.append(f"Impact: {raw['impact']}")
        if raw.get("urgency"):
            lines.append(f"Urgency: {raw['urgency']}")
        if raw.get("state"):
            lines.append(f"State: {raw['state']}")
        if raw.get("assigned_to"):
            assigned = raw["assigned_to"]
            if isinstance(assigned, dict):
                assigned = assigned.get("display_value", assigned.get("value", str(assigned)))
            lines.append(f"Assigned To: {assigned}")
        if raw.get("assignment_group"):
            group = raw["assignment_group"]
            if isinstance(group, dict):
                group = group.get("display_value", group.get("value", str(group)))
            lines.append(f"Assignment Group: {group}")

        description = "\n".join(lines) if lines else "No description available"

        actions = []
        if raw.get("work_notes"):
            actions.append(f"Work Notes: {raw['work_notes']}")
        if raw.get("comments"):
            actions.append(f"Comments: {raw['comments']}")
        if raw.get("comments_and_work_notes"):
            actions.append(f"Combined Notes: {raw['comments_and_work_notes']}")
        if raw.get("close_notes"):
            actions.append(f"Resolution: {raw['close_notes']}")

        action_taken = "\n".join(actions) if actions else "No actions recorded"

        return {
            "incident_id": raw.get("number"),
            "source_id": raw.get("sys_id"),
            "title": raw.get("short_description", "No title"),
            "description": description,
            "action_taken": action_taken,
            "state": raw.get("state"),
            "category": raw.get("category"),
            "subcategory": raw.get("subcategory"),
            "priority": raw.get("priority"),
            "impact": raw.get("impact"),
            "urgency": raw.get("urgency"),
            "assigned_to": _extract_display(raw.get("assigned_to")),
            "assignment_group": _extract_display(raw.get("assignment_group")),
            "resolution_code": raw.get("resolution_code"),
            "opened_at": raw.get("opened_at"),
            "resolved_at": raw.get("resolved_at"),
            "closed_at": raw.get("closed_at"),
            "updated_at": raw.get("sys_updated_on"),
        }

    @classmethod
    def validate_config(cls, config: dict, auth_type: str) -> str | None:
        if not config.get("url"):
            return "Instance URL is required"

        if auth_type == "basic_auth":
            if not config.get("username") or not config.get("password"):
                return "Basic auth requires username and password"
        elif auth_type == "api_token":
            if not config.get("email") or not config.get("api_token"):
                return "API token auth requires email and api_token"
        elif auth_type == "oauth2":
            if not config.get("client_id") or not config.get("client_secret"):
                return "OAuth2 requires client_id and client_secret"
        else:
            return f"Unsupported auth type: {auth_type}"

        return None


def _extract_display(value: Any) -> str | None:
    """Extract display value from a SNOW reference field (may be dict or string)."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get("display_value") or value.get("value")
    return str(value) if value else None
