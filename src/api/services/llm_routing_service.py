"""LLM Routing Service — calls a router LLM to pick the best model for a query.

Uses structured output to get a reliable JSON decision from the router LLM.
Includes an LRU cache to avoid redundant routing calls for similar queries.
"""

import hashlib
import json
import logging
import threading
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

from src.copilot.llm_factory import create_llm_from_provider

logger = logging.getLogger(__name__)

_routing_cache: OrderedDict[str, Dict[str, str]] = OrderedDict()
_routing_cache_lock = threading.Lock()
_ROUTING_CACHE_MAX = 100

ROUTER_SYSTEM_PROMPT = """You are a model router. Given a user query, pick the best LLM model from the available options.

Available models (JSON):
{models_json}

Respond with ONLY a JSON object (no markdown, no explanation):
{{"provider_id": "<id>", "model_id": "<model>", "reason": "<short reason>"}}

Selection criteria:
- Match task_types to the query intent (reasoning, summarization, general, incident-analysis, etc.)
- Match prompt_sizes to query length (short: <50 words, medium: 50-200, long: >200)
- Prefer lower cost when quality is similar
- Prefer faster latency for simple queries
- Prefer higher quality for complex reasoning tasks"""


def _cache_key(query: str) -> str:
    """Create a cache key from the query (normalized, hashed)."""
    normalized = query.strip().lower()[:500]
    return hashlib.sha256(normalized.encode()).hexdigest()[:32]


def _get_cached_decision(query: str) -> Optional[Dict[str, str]]:
    """Check cache for a previous routing decision."""
    key = _cache_key(query)
    with _routing_cache_lock:
        if key in _routing_cache:
            _routing_cache.move_to_end(key)
            return _routing_cache[key]
    return None


def _set_cached_decision(query: str, decision: Dict[str, str]):
    """Cache a routing decision."""
    key = _cache_key(query)
    with _routing_cache_lock:
        _routing_cache[key] = decision
        _routing_cache.move_to_end(key)
        while len(_routing_cache) > _ROUTING_CACHE_MAX:
            _routing_cache.popitem(last=False)


def _build_models_summary(configs: list) -> str:
    """Build a compact JSON summary of available models for the router prompt."""
    models = []
    for cfg in configs:
        models.append({
            "provider_id": str(cfg.provider_id),
            "model_id": cfg.model_id,
            "task_types": cfg.task_types or [],
            "prompt_sizes": cfg.prompt_sizes or [],
            "cost": cfg.cost_tier,
            "latency": cfg.latency_tier,
            "quality": cfg.quality_tier,
        })
    return json.dumps(models, separators=(",", ":"))


def route_query(
    query: str,
    routing_configs: list,
    router_provider_type: str,
    router_model_id: str,
    router_api_key: Optional[str] = None,
    router_base_url: Optional[str] = None,
    router_provider_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Call the router LLM to pick the best model for this query.

    Args:
        query: The user's message.
        routing_configs: List of ModelRoutingConfig objects (enabled only).
        router_provider_type: Provider type for the router LLM.
        router_model_id: Model ID for the router LLM.
        router_api_key: Decrypted API key for the router.
        router_base_url: Base URL for the router.
        router_provider_config: Additional config for the router.

    Returns:
        Dict with provider_id, model_id, reason.
    """
    if not routing_configs:
        logger.warning("No routing configs available, cannot route")
        return {}

    cached = _get_cached_decision(query)
    if cached:
        logger.info(f"Routing cache hit: {cached['model_id']}")
        return cached

    models_json = _build_models_summary(routing_configs)
    system_prompt = ROUTER_SYSTEM_PROMPT.format(models_json=models_json)

    try:
        router_llm = create_llm_from_provider(
            provider_type=router_provider_type,
            model_id=router_model_id,
            api_key=router_api_key,
            base_url=router_base_url,
            provider_config=router_provider_config or {},
            temperature=0.0,
        )

        response = router_llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ])

        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            content = content.rsplit("```", 1)[0]
        content = content.strip()

        decision = json.loads(content)

        valid_combos = {(str(c.provider_id), c.model_id) for c in routing_configs}
        if (decision.get("provider_id"), decision.get("model_id")) not in valid_combos:
            logger.warning(f"Router selected invalid model: {decision}, using fallback")
            return {}

        result = {
            "provider_id": decision["provider_id"],
            "model_id": decision["model_id"],
            "reason": decision.get("reason", ""),
        }

        _set_cached_decision(query, result)

        logger.info(
            f"Router selected model: {result['model_id']} "
            f"(reason: {result['reason']})"
        )
        return result

    except Exception as e:
        logger.error(f"Router LLM call failed: {e}")
        return {}