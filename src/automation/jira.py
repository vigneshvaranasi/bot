"""Jira connector — fetches and normalises issues via the Jira REST API."""

import base64
import logging
from typing import Any

import requests

from src.automation.base import BaseConnector

logger = logging.getLogger(__name__)

_PAGE_SIZE = 100
_REQUEST_TIMEOUT = 100  # seconds

_FIELDS = (
    "summary,"
    "description,"
    "status,"
    "priority,"
    "assignee,"
    "reporter,"
    "issuetype,"
    "labels,"
    "components,"
    "created,"
    "updated,"
    "resolutiondate,"
    "resolution,"
    "comment"
)


class JiraConnector(BaseConnector):
    CONNECTOR_TYPE = "jira"
    REQUIRED_CONFIG: set[str] = {"url"}
    AUTH_TYPES: set[str] = {"api_token", "basic_auth", "pat"}

    def __init__(self, config: dict[str, Any]):
        self.url = config["url"].rstrip("/")
        self.search_api = f"{self.url}/rest/api/3/search/jql"
        self.project_key = (config.get("project_key") or "").strip() or None
        self.user_jql = (config.get("jql") or "").strip() or None
        self._headers = self._build_headers(config)

    @staticmethod
    def _build_headers(config: dict) -> dict[str, str]:
        """Return the auth+accept headers for every request."""
        headers: dict[str, str] = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        auth_type = config.get("auth_type", "api_token")

        if auth_type == "api_token":
            email = config.get("email")
            api_token = config.get("api_token")
            if not email or not api_token:
                raise ValueError("api_token auth requires 'email' and 'api_token'")
            token = base64.b64encode(f"{email}:{api_token}".encode()).decode()
            headers["Authorization"] = f"Basic {token}"
            return headers

        if auth_type == "basic_auth":
            username = config.get("username")
            password = config.get("password")
            if not username or not password:
                raise ValueError("basic_auth requires 'username' and 'password'")
            token = base64.b64encode(f"{username}:{password}".encode()).decode()
            headers["Authorization"] = f"Basic {token}"
            return headers

        if auth_type == "pat":
            access_token = config.get("access_token")
            if not access_token:
                raise ValueError("pat auth requires 'access_token'")
            headers["Authorization"] = f"Bearer {access_token}"
            return headers

        raise ValueError(f"Unsupported auth type: {auth_type}")

    def _build_jql(self, last_synced: str) -> str:
        """Build the JQL query for incremental fetch.

        Jira's JQL date format is 'yyyy-MM-dd HH:mm' (minute precision).
        The incoming last_synced is 'yyyy-MM-dd HH:mm:ss', so we trim seconds.
        """
        ts = last_synced.strip()
        if len(ts) >= 16 and ts[4] == "-" and ts[10] == " ":
            ts = ts[:16]

        clauses: list[str] = []
        if self.project_key:
            clauses.append(f'project = "{self.project_key}"')
        if self.user_jql:
            clauses.append(f"({self.user_jql})")
        clauses.append(f'updated >= "{ts}"')

        return " AND ".join(clauses) + " ORDER BY updated ASC"

    def fetch_incidents(self, last_synced: str) -> list[dict[str, Any]]:
        """Fetch all issues updated after *last_synced* with full pagination.

        Uses the cursor-based /rest/api/3/search/jql endpoint. Pagination is
        driven by ``nextPageToken``; the response no longer returns a ``total``.
        """
        jql = self._build_jql(last_synced)
        all_issues: list[dict] = []
        next_page_token: str | None = None
        page = 0

        while True:
            body: dict[str, Any] = {
                "jql": jql,
                "maxResults": _PAGE_SIZE,
                "fields": _FIELDS.split(","),
            }
            if next_page_token:
                body["nextPageToken"] = next_page_token

            response = requests.post(
                self.search_api,
                headers=self._headers,
                json=body,
                timeout=_REQUEST_TIMEOUT,
            )

            if response.status_code == 401:
                raise PermissionError("Authentication failed — check Jira credentials")
            if response.status_code == 403:
                raise PermissionError(
                    "Jira rejected the request (403). Verify the user has "
                    "'Browse Projects' permission on the target project."
                )
            if response.status_code == 429:
                raise RuntimeError("Jira rate limit exceeded — retry later")
            if response.status_code != 200:
                raise RuntimeError(
                    f"Jira API error {response.status_code}: {response.text[:500]}"
                )

            payload = response.json()
            issues = payload.get("issues", []) or []
            all_issues.extend(issues)
            page += 1
            logger.info(
                "Jira fetch page=%d returned %d issues (fetched so far: %d)",
                page, len(issues), len(all_issues),
            )

            next_page_token = payload.get("nextPageToken")
            is_last = payload.get("isLast")
            if is_last or not next_page_token:
                break

        return all_issues

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Map a raw Jira issue to the standard incident schema."""
        fields = raw.get("fields") or {}

        status = _ref_name(fields.get("status"))
        priority = _ref_name(fields.get("priority"))
        issue_type = _ref_name(fields.get("issuetype"))
        resolution = _ref_name(fields.get("resolution"))
        assignee = _user_display(fields.get("assignee"))

        components = [
            _ref_name(c) for c in (fields.get("components") or []) if _ref_name(c)
        ]
        labels = [str(l) for l in (fields.get("labels") or []) if l]

        summary = fields.get("summary") or ""
        description_text = _adf_to_text(fields.get("description"))

        lines: list[str] = []
        if summary:
            lines.append(summary)
        if description_text:
            lines.append(f"Details: {description_text}")
        if issue_type:
            lines.append(f"Type: {issue_type}")
        if status:
            lines.append(f"Status: {status}")
        if priority:
            lines.append(f"Priority: {priority}")
        if components:
            lines.append(f"Components: {', '.join(components)}")
        if labels:
            lines.append(f"Labels: {', '.join(labels)}")
        if assignee:
            lines.append(f"Assignee: {assignee}")
        if resolution:
            lines.append(f"Resolution: {resolution}")

        description = "\n".join(lines) if lines else "No description available"

        action_lines: list[str] = []
        comment_block = fields.get("comment") or {}
        for comment in comment_block.get("comments", []) or []:
            author = _user_display(comment.get("author")) or "unknown"
            created = comment.get("created") or ""
            body = _adf_to_text(comment.get("body"))
            if not body:
                continue
            header = f"[{author} @ {created}]" if created else f"[{author}]"
            action_lines.append(f"{header} {body}")

        action_taken = "\n".join(action_lines) if action_lines else "No actions recorded"

        resolved_at = fields.get("resolutiondate")
        closed_at = resolved_at if status and status.lower() in {"done", "closed", "resolved"} else None

        return {
            "incident_id": raw.get("key"),
            "source_id": str(raw.get("id")) if raw.get("id") is not None else None,
            "title": summary or "No title",
            "description": description,
            "action_taken": action_taken,
            "state": status,
            "category": issue_type,
            "subcategory": components[0] if components else None,
            "priority": priority,
            "impact": None,
            "urgency": None,
            "assigned_to": assignee,
            "assignment_group": ", ".join(components) if components else None,
            "resolution_code": resolution,
            "opened_at": fields.get("created"),
            "resolved_at": resolved_at,
            "closed_at": closed_at,
            "updated_at": fields.get("updated"),
        }

    @classmethod
    def validate_config(cls, config: dict, auth_type: str) -> str | None:
        if not config.get("url"):
            return "Instance URL is required"

        if auth_type == "api_token":
            if not config.get("email") or not config.get("api_token"):
                return "API token auth requires email and api_token"
        elif auth_type == "basic_auth":
            if not config.get("username") or not config.get("password"):
                return "Basic auth requires username and password"
        elif auth_type == "pat":
            if not config.get("access_token"):
                return "PAT auth requires access_token"
        else:
            return f"Unsupported auth type: {auth_type}"

        if not (config.get("project_key") or config.get("jql")):
            return "Provide either a project_key or a custom jql query"

        return None


def _ref_name(value: Any) -> str | None:
    """Pull the human-readable name from a Jira reference object."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get("name") or value.get("value") or None
    return str(value) if value else None


def _user_display(value: Any) -> str | None:
    """Pull a displayable identity from a Jira user object."""
    if value is None:
        return None
    if isinstance(value, dict):
        return (
            value.get("displayName")
            or value.get("emailAddress")
            or value.get("accountId")
        )
    return str(value) if value else None


def _adf_to_text(node: Any) -> str:
    """Flatten an Atlassian Document Format tree (or plain string) to text.

    Jira Cloud returns `description` and `comment.body` as ADF documents. We
    walk the tree emitting text nodes and inserting newlines at block
    boundaries (paragraphs, list items, hard breaks).
    """
    if node is None:
        return ""
    if isinstance(node, str):
        return node

    if not isinstance(node, dict):
        return ""

    node_type = node.get("type")
    pieces: list[str] = []

    if node_type == "text":
        text = node.get("text") or ""
        return text
    if node_type == "hardBreak":
        return "\n"
    if node_type == "mention":
        attrs = node.get("attrs") or {}
        name = attrs.get("text") or attrs.get("displayName") or attrs.get("id") or ""
        return f"@{name}" if name else ""

    for child in node.get("content") or []:
        pieces.append(_adf_to_text(child))

    block_types = {
        "paragraph", "heading", "listItem", "bulletList", "orderedList",
        "blockquote", "codeBlock", "rule",
    }
    joined = "".join(pieces)
    if node_type in block_types and joined and not joined.endswith("\n"):
        joined += "\n"
    return joined