import json
import os
from typing import Any, Dict, Optional

# Location of cache file
CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "cache.json")


def _load_cache() -> Dict[str, Any]:
    """Load cache from file."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}


def _save_cache(data: Dict[str, Any]) -> None:
    """Save cache back to file."""
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_from_cache(key: str) -> Optional[Any]:
    """Retrieve a value from cache."""
    cache = _load_cache()
    return cache.get(key)


def add_to_cache(key: str, value: Any) -> None:
    """Add or update a cache entry."""
    cache = _load_cache()
    cache[key] = value
    _save_cache(cache)


def delete_from_cache(key: str) -> None:
    """Remove a key from cache if it exists."""
    cache = _load_cache()
    if key in cache:
        del cache[key]
        _save_cache(cache)


def clear_cache() -> None:
    """Clear entire cache file."""
    _save_cache({})
