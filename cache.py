"""
Cache Implementation for LangGraph Support Bot
==============================================

This module provides a comprehensive caching system with support for both Redis and JSON file caching.
Features include fuzzy text matching, similarity scoring, and automatic cache management.

Integration Points:
- Redis cache (primary) with JSON file fallback
- Fuzzy text matching for similar queries
- Cache bypass functionality
- Automatic cache invalidation
- Environment-based configuration

Usage:
    from cache import get_from_cache, add_to_cache
    
    # Check cache before processing
    cached_response = get_from_cache(user_query)
    if cached_response:
        return cached_response
    
    # Process query and cache result
    response = process_query(user_query)
    add_to_cache(user_query, response)
"""

import json
import os
import re
import redis
from typing import Any, Dict, Optional
from difflib import SequenceMatcher
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Cache configuration
CACHE_FILE = os.path.join(os.path.dirname(__file__), "data", "cache.json")
SIMILARITY_THRESHOLD = 0.75  # Threshold for fuzzy matching (0.0-1.0)

# Define common stopwords to ignore in topic extraction
STOPWORDS = {
    "the", "a", "an", "and", "or", "if", "to", "of", "at", "by",
    "for", "in", "on", "with", "that", "this", "it", "is", "are",
    "was", "were", "i", "me", "my", "you", "your", "we", "us", "our",
    "can", "cannot", "cant", "not", "do", "does", "did", "no", "be",
    "what", "when", "where", "why", "how", "which", "who", "whom"
}

def _parse_redis_config():
    """Parse Redis configuration from REDIS_URL or individual environment variables."""
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        import urllib.parse
        parsed = urllib.parse.urlparse(redis_url)
        return {
            "host": parsed.hostname,
            "port": parsed.port or 6379,
            "db": int(parsed.path[1:]) if parsed.path and parsed.path[1:] else 0,
            "password": parsed.password,
            "username": parsed.username
        }
    else:
        return {
            "host": os.getenv("REDIS_HOST", "localhost"),
            "port": int(os.getenv("REDIS_PORT", "6379")),
            "db": int(os.getenv("REDIS_DB", "0")),
            "password": os.getenv("REDIS_PASSWORD", None),
            "username": os.getenv("REDIS_USERNAME", None)
        }

REDIS_CONFIG = _parse_redis_config()
USE_REDIS = os.getenv("USE_REDIS_CACHE", "false").lower() == "true"

# Global Redis client
_redis_client = None

def _get_redis_client():
    """Get Redis client or return None if disabled or connection fails."""
    global _redis_client
    if not USE_REDIS:
        return None
    if _redis_client is None:
        try:
            redis_args = {
                "host": REDIS_CONFIG["host"],
                "port": REDIS_CONFIG["port"],
                "db": REDIS_CONFIG["db"],
                "decode_responses": True,
                "socket_connect_timeout": 2,
                "socket_timeout": 2
            }
            if REDIS_CONFIG["password"]:
                redis_args["password"] = REDIS_CONFIG["password"]
            if REDIS_CONFIG["username"]:
                redis_args["username"] = REDIS_CONFIG["username"]
            
            _redis_client = redis.Redis(**redis_args)
            _redis_client.ping()
            print(f"[REDIS CONNECTED] Connected to Redis at {REDIS_CONFIG['host']}:{REDIS_CONFIG['port']}")
        except Exception as e:
            print(f"[REDIS FAILED] Could not connect to Redis: {e}")
            _redis_client = None
    return _redis_client

def reset_redis_client():
    """Reset the Redis client connection (useful after config changes)."""
    global _redis_client
    _redis_client = None
    print("[REDIS RESET] Redis client has been reset")

def _normalize_text(text: str) -> str:
    """Normalize text by lowercasing, trimming, and removing excessive whitespace."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s]', '', text)
    return text

def _extract_topics(text: str) -> set:
    """Extract significant keywords (excluding common stopwords) from text."""
    if not text:
        return set()
    topics = set()
    for word in re.findall(r'\b\w+\b', text.lower()):
        if word in STOPWORDS or len(word) < 2:
            continue
        topics.add(word)
    return topics

def _calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate similarity between two texts using multiple factors:
    - Basic string similarity
    - Topic/keyword overlap
    - Numeric differences (heavy penalty for mismatches)
    """
    # Basic string similarity using SequenceMatcher
    base_sim = SequenceMatcher(None, text1, text2).ratio()
    
    # Extract topics from both texts
    topics1 = _extract_topics(text1)
    topics2 = _extract_topics(text2)
    
    # Check for numeric differences (apply heavy penalty)
    nums1 = set(re.findall(r'\d+', text1))
    nums2 = set(re.findall(r'\d+', text2))
    if nums1 and nums2 and nums1 != nums2:
        return base_sim * 0.1  # Heavy penalty for numeric mismatches
    
    # Calculate topic-based similarity if both texts have topics
    if topics1 and topics2:
        common_topics = topics1.intersection(topics2)
        total_unique_topics = len(topics1.union(topics2))
        
        if common_topics:
            # Boost similarity based on topic overlap ratio
            topic_overlap_ratio = len(common_topics) / total_unique_topics
            boost = topic_overlap_ratio * 0.2
            boosted_sim = min(1.0, base_sim + boost)
            return boosted_sim
        else:
            # No common topics - apply penalty only if base similarity is low
            if base_sim < 0.6:
                return base_sim * 0.3
    
    return base_sim

def _create_cache_key(query: str) -> str:
    """Create a normalized cache key from the query text."""
    return _normalize_text(query)

def _load_json_cache() -> Dict[str, Any]:
    """Load cache from JSON file."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            print(f"[JSON CACHE WARNING] Could not read cache file: {CACHE_FILE}")
            return {}
    return {}

def _save_json_cache(data: Dict[str, Any]) -> None:
    """Save cache back to JSON file."""
    try:
        cache_dir = os.path.dirname(CACHE_FILE)
        os.makedirs(cache_dir, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"[JSON CACHE ERROR] Could not save cache file: {e}")

def _find_similar_cache_key(target_key: str, cache_keys: list) -> Optional[str]:
    """Find a similar cache key using fuzzy matching."""
    best_match = None
    best_similarity = 0.0
    
    for cached_key in cache_keys:
        similarity = _calculate_similarity(target_key, cached_key)
        if similarity > best_similarity and similarity >= SIMILARITY_THRESHOLD:
            best_similarity = similarity
            best_match = cached_key
    
    return best_match

def _get_from_redis(key: str) -> Optional[Any]:
    """Get value from Redis cache with fuzzy matching fallback."""
    redis_client = _get_redis_client()
    if not redis_client:
        return None
    
    try:
        # Try exact match first
        value = redis_client.get(f"cache:{key}")
        if value:
            return json.loads(value)
        
        # Fuzzy match: check all keys for similar queries
        pattern = "cache:*"
        all_keys = redis_client.keys(pattern)
        cache_keys = [k.replace("cache:", "") for k in all_keys]
        similar_key = _find_similar_cache_key(key, cache_keys)
        
        if similar_key:
            print(f"[REDIS HIT - FUZZY] Similar query '{similar_key}' found for: '{key}'")
            value = redis_client.get(f"cache:{similar_key}")
            if value:
                return json.loads(value)
    except Exception as e:
        print(f"[REDIS ERROR] Error reading from Redis: {e}")
    
    return None

def _set_to_redis(key: str, value: Any, ttl: Optional[int] = None) -> bool:
    """Set value in Redis cache with optional TTL (time-to-live)."""
    redis_client = _get_redis_client()
    if not redis_client:
        return False
    
    try:
        serialized_value = json.dumps(value, ensure_ascii=False)
        if ttl:
            redis_client.setex(f"cache:{key}", ttl, serialized_value)
        else:
            redis_client.set(f"cache:{key}", serialized_value)
        return True
    except Exception as e:
        print(f"[REDIS ERROR] Error writing to Redis: {e}")
        return False

def _add_cache_indicator(response: str, cache_type: str) -> str:
    """Append a cache hit indicator note to the response."""
    cache_note = (
        f"\n\n---\n"
        f"*This response was retrieved from cache for faster delivery.*\n"
        f"*Tip: Add \"no cache\" to your message to bypass cache and get a fresh response.*"
    )
    return response + cache_note

def get_from_cache(query: str, bypass_cache: bool = False) -> Optional[Any]:
    """
    Retrieve a cached response for the query if available.
    
    Uses normalization and fuzzy matching to find similar cached queries.
    Supports cache bypass through keywords or explicit parameter.
    
    Args:
        query (str): The user query to search for in cache
        bypass_cache (bool): If True, skip cache lookup entirely
    
    Returns:
        Optional[Any]: Cached response if found, None otherwise
    """
    # Cache bypass keywords that users can include in their queries
    bypass_keywords = [
        "no cache", "don't cache", "dont cache", "bypass cache", 
        "skip cache", "fresh response", "new response", "refresh"
    ]
    
    # Check if cache should be bypassed
    if bypass_cache or any(keyword in query.lower() for keyword in bypass_keywords):
        print(f"[CACHE BYPASSED] User requested no cache for: '{query[:50]}...'")
        return None
    
    normalized_key = _create_cache_key(query)
    
    # Try Redis first (if enabled)
    if USE_REDIS:
        redis_result = _get_from_redis(normalized_key)
        if redis_result:
            print(f"[REDIS HIT] Found cached response for: '{query[:50]}...'")
            return _add_cache_indicator(redis_result, "Redis")
    
    # Fall back to JSON cache
    json_cache = _load_json_cache()
    
    # Try exact match in JSON cache
    if normalized_key in json_cache:
        print(f"[JSON HIT - EXACT] Found exact match for: '{query[:50]}...'")
        return _add_cache_indicator(json_cache[normalized_key], "JSON")
    
    # Try fuzzy match in JSON cache
    similar_key = _find_similar_cache_key(normalized_key, list(json_cache.keys()))
    if similar_key:
        print(f"[JSON HIT - FUZZY] Similar query found for: '{query[:50]}...'")
        return _add_cache_indicator(json_cache[similar_key], "JSON")
    
    print(f"[CACHE MISS] No match found for: '{query[:50]}...'")
    return None

def add_to_cache(query: str, response: Any, ttl: Optional[int] = None) -> None:
    """
    Add or update a cache entry for the given query and response.
    If a similar query already exists, it will update that entry instead of creating a duplicate.
    
    Args:
        query (str): The user query to cache
        response (Any): The response to cache
        ttl (Optional[int]): Time-to-live in seconds for Redis cache
    """
    if response is None:
        return
    
    normalized_key = _create_cache_key(query)
    
    # Check if a similar query already exists and use that key instead
    existing_key = normalized_key
    
    # Check Redis for similar keys
    if USE_REDIS:
        redis_client = _get_redis_client()
        if redis_client:
            try:
                pattern = "cache:*"
                all_keys = redis_client.keys(pattern)
                cache_keys = [k.decode('utf-8').replace("cache:", "") if isinstance(k, bytes) else k.replace("cache:", "") for k in all_keys]
                similar_key = _find_similar_cache_key(normalized_key, cache_keys)
                
                if similar_key and similar_key != normalized_key:
                    print(f"[CACHE UPDATE] Found similar existing entry '{similar_key}', updating instead of creating new")
                    existing_key = similar_key
            except Exception as e:
                print(f"[CACHE WARNING] Error checking for similar keys: {e}")
    
    # Also check JSON cache for similar keys if Redis didn't find one
    if existing_key == normalized_key:
        json_cache = _load_json_cache()
        similar_key = _find_similar_cache_key(normalized_key, list(json_cache.keys()))
        if similar_key and similar_key != normalized_key:
            print(f"[CACHE UPDATE] Found similar existing entry '{similar_key}' in JSON, updating instead of creating new")
            existing_key = similar_key
    
    # Save to Redis if available (using the existing key if found)
    redis_saved = False
    if USE_REDIS:
        redis_saved = _set_to_redis(existing_key, response, ttl)
        if redis_saved:
            ttl_msg = f" (TTL: {ttl}s)" if ttl else ""
            action = "Updated" if existing_key != normalized_key else "Saved"
            print(f"[REDIS STORED] {action} response for: '{query[:50]}...'{ttl_msg}")
    
    # Always save to JSON as backup (using the existing key if found)
    json_cache = _load_json_cache()
    json_cache[existing_key] = response
    _save_json_cache(json_cache)
    
    if not redis_saved:
        action = "Updated" if existing_key != normalized_key else "Saved"
        print(f"[JSON STORED] {action} response for: '{query[:50]}...'")

def clear_cache(pattern: Optional[str] = None) -> bool:
    """
    Clear cache entries matching the optional pattern.
    
    Args:
        pattern (Optional[str]): Pattern to match keys for deletion. If None, clears all.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Clear Redis cache
        if USE_REDIS:
            redis_client = _get_redis_client()
            if redis_client:
                if pattern:
                    keys = redis_client.keys(f"cache:*{pattern}*")
                else:
                    keys = redis_client.keys("cache:*")
                
                if keys:
                    redis_client.delete(*keys)
                    print(f"[REDIS CLEARED] Deleted {len(keys)} keys")
        
        # Clear JSON cache
        if pattern:
            json_cache = _load_json_cache()
            keys_to_delete = [k for k in json_cache.keys() if pattern in k]
            for key in keys_to_delete:
                del json_cache[key]
            _save_json_cache(json_cache)
            print(f"[JSON CLEARED] Deleted {len(keys_to_delete)} keys")
        else:
            # Clear entire JSON cache
            _save_json_cache({})
            print("[JSON CLEARED] Cleared entire cache")
        
        return True
    except Exception as e:
        print(f"[CACHE ERROR] Error clearing cache: {e}")
        return False

def get_cache_stats() -> Dict[str, Any]:
    """
    Get statistics about the cache usage.
    
    Returns:
        Dict[str, Any]: Cache statistics including counts and configuration
    """
    stats = {
        "redis_enabled": USE_REDIS,
        "redis_connected": _get_redis_client() is not None,
        "json_cache_file": CACHE_FILE,
        "similarity_threshold": SIMILARITY_THRESHOLD
    }
    
    # Redis stats
    if USE_REDIS and _get_redis_client():
        try:
            redis_client = _get_redis_client()
            cache_keys = redis_client.keys("cache:*")
            stats["redis_entries"] = len(cache_keys)
        except Exception:
            stats["redis_entries"] = 0
    else:
        stats["redis_entries"] = 0
    
    # JSON cache stats
    try:
        json_cache = _load_json_cache()
        stats["json_entries"] = len(json_cache)
    except Exception:
        stats["json_entries"] = 0
    
    return stats

# Integration helper functions for LangGraph chat system

def check_cache_for_query(query: str, bypass_cache: bool = False) -> Optional[str]:
    """
    Helper function specifically for LangGraph chat integration.
    
    Args:
        query (str): User query to check in cache
        bypass_cache (bool): Whether to bypass cache lookup
    
    Returns:
        Optional[str]: Cached response if found, None otherwise
    """
    return get_from_cache(query, bypass_cache)

def store_chat_response(query: str, response: str, ttl: Optional[int] = 86400) -> None:
    """
    Helper function to store chat responses with default 24-hour TTL.
    
    Args:
        query (str): User query to cache
        response (str): Chat response to cache
        ttl (Optional[int]): Time-to-live in seconds (default: 24 hours)
    """
    add_to_cache(query, response, ttl)

def is_cache_enabled() -> bool:
    """Check if caching is enabled (either Redis or JSON)."""
    return True  # JSON cache is always available as fallback

def get_cache_config() -> Dict[str, Any]:
    """Get current cache configuration."""
    return {
        "use_redis": USE_REDIS,
        "redis_config": REDIS_CONFIG if USE_REDIS else None,
        "cache_file": CACHE_FILE,
        "similarity_threshold": SIMILARITY_THRESHOLD
    }

if __name__ == "__main__":
    # Test the cache system
    print("Testing Cache System...")
    
    # Test basic caching
    test_query = "How to resolve HTTP 499 errors?"
    test_response = "HTTP 499 errors can be resolved by checking server logs and validating the request format."
    
    print(f"Storing test response for: {test_query}")
    add_to_cache(test_query, test_response)
    
    print(f"Retrieving cached response...")
    cached = get_from_cache(test_query)
    print(f"Cache hit: {cached is not None}")
    
    # Test fuzzy matching
    similar_query = "how to fix http 499 error"
    print(f"\nTesting fuzzy match for: {similar_query}")
    fuzzy_result = get_from_cache(similar_query)
    print(f"Fuzzy match found: {fuzzy_result is not None}")
    
    # Display cache stats
    print(f"\nCache Statistics:")
    stats = get_cache_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")