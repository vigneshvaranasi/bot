"""Connector registry  maps integration type slugs to connector classes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.automation.base import BaseConnector

_CONNECTOR_MAP: dict[str, tuple[str, str]] = {
    "servicenow": ("src.automation.snow", "ServiceNowConnector"),
}


def get_connector(connector_type: str, config: dict) -> "BaseConnector":
    """Instantiate and return the connector for the given type.

    Raises ValueError if the connector type is unknown.
    """
    key = connector_type.lower().strip()
    entry = _CONNECTOR_MAP.get(key)
    if entry is None:
        raise ValueError(
            f"Unknown connector type: '{connector_type}'. "
            f"Available: {', '.join(sorted(_CONNECTOR_MAP))}"
        )
    module_path, class_name = entry
    import importlib
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    return cls(config)


def get_connector_type(service_name: str) -> str:
    """Resolve a free-form service_name to a registered connector type slug.

    Uses case-insensitive prefix matching so "ServiceNow Production" -> "servicenow".
    Returns the slug, or raises ValueError if no match is found.
    """
    lowered = service_name.lower().strip()
    for key in _CONNECTOR_MAP:
        if lowered.startswith(key) or key.startswith(lowered):
            return key
    raise ValueError(
        f"No connector registered for service '{service_name}'. "
        f"Available: {', '.join(sorted(_CONNECTOR_MAP))}"
    )


def list_connector_types() -> list[str]:
    """Return all registered connector type slugs."""
    return sorted(_CONNECTOR_MAP.keys())