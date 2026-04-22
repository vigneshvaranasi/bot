"""Connector registry  maps integration type slugs to connector classes."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.automation.base import BaseConnector

_CONNECTOR_MAP: dict[str, tuple[str, str]] = {
    "servicenow": ("src.automation.snow", "ServiceNowConnector"),
    "jira": ("src.automation.jira", "JiraConnector"),
}


def get_connector(connector_type: str, config: dict) -> "BaseConnector":
    """Instantiate and return the connector for the given type.

    Raises ValueError if the connector type is unknown.
    """
    key = (connector_type or "").lower().strip()
    entry = _CONNECTOR_MAP.get(key)
    if entry is None:
        raise ValueError(
            f"Unknown connector type: '{connector_type}'. "
            f"Available: {', '.join(sorted(_CONNECTOR_MAP))}"
        )
    module_path, class_name = entry
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    return cls(config)


def resolve_connector_type(connector_type: str | None, service_name: str | None) -> str:
    """Resolve the effective connector slug for an integration row.

    Prefers the explicit ``connector_type`` column. Falls back to
    case-insensitive prefix matching on ``service_name`` so rows predating the
    column (or future free-form names) still resolve correctly.
    """
    if connector_type:
        key = connector_type.lower().strip()
        if key in _CONNECTOR_MAP:
            return key

    lowered = (service_name or "").lower().strip()
    if lowered:
        for key in _CONNECTOR_MAP:
            if lowered.startswith(key) or key.startswith(lowered):
                return key
    raise ValueError(
        f"No connector registered for connector_type={connector_type!r} "
        f"service_name={service_name!r}. "
        f"Available: {', '.join(sorted(_CONNECTOR_MAP))}"
    )


def list_connector_types() -> list[str]:
    """Return all registered connector type slugs."""
    return sorted(_CONNECTOR_MAP.keys())