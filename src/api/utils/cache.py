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
CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "cache.json")
SIMILARITY_THRESHOLD = 0.75  # More flexible threshold for better matching

# Define common stopwords to ignore in topic extraction (for general keyword filtering)
STOPWORDS = {
    "the", "a", "an", "and", "or", "if", "to", "of", "at", "by", 
    "for", "in", "on", "with", "that", "this", "it", "is", "are", 
    "was", "were", "i", "me", "my", "you", "your", "we", "us", "our", 
    "can", "cannot", "cant", "not", "do", "does", "did", "no", "be"
}

def _parse_redis_config():
    """Parse Redis configuration from REDIS_URL or individual env vars."""
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
USE_REDIS = os.getenv("USE_REDIS_CACHE", "true").lower() == "true"

# Global Redis client
_redis_client = None

def _get_redis_client():
    """Get Redis client or return None if disabled."""
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

def _normalize_text(text: str) -> str:
    """Normalize text by lowercasing, trimming, and removing punctuation."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s]', '', text)
    return text

def _extract_topics(text: str) -> set:
    """Extract significant keywords (excluding common words) from text."""
    if not text:
        return set()
    topics = set()
    for word in re.findall(r'\b\w+\b', text.lower()):
        if word in STOPWORDS or len(word) < 2:
            continue
        topics.add(word)
    return topics

def _calculate_similarity(text1: str, text2: str) -> float:
    """Compute similarity with improved topic matching and keyword importance."""
    # Basic string similarity
    base_sim = SequenceMatcher(None, text1, text2).ratio()
    
    # Extract topics from both texts
    topics1 = _extract_topics(text1)
    topics2 = _extract_topics(text2)
    
    # Check for numeric differences (heavy penalty)
    nums1 = set(re.findall(r'\d+', text1))
    nums2 = set(re.findall(r'\d+', text2))
    if nums1 and nums2 and nums1 != nums2:
        return base_sim * 0.1
    
    # If both have topics, calculate topic overlap
    if topics1 and topics2:
        common_topics = topics1.intersection(topics2)
        total_unique_topics = len(topics1.union(topics2))
        
        if common_topics:
            # Boost similarity based on topic overlap ratio
            topic_overlap_ratio = len(common_topics) / total_unique_topics
            
            # Apply boost based on topic overlap
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
        except json.JSONDecodeError:
            return {}
    return {}

def _save_json_cache(data: Dict[str, Any]) -> None:
    """Save cache back to JSON file."""
    cache_dir = os.path.dirname(CACHE_FILE)
    os.makedirs(cache_dir, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

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
    """Get value from Redis cache (with fuzzy matching if exact key not found)."""
    redis_client = _get_redis_client()
    if not redis_client:
        return None
    try:
        # Try exact match first
        value = redis_client.get(f"cache:{key}")
        if value:
            return json.loads(value)
        # Fuzzy match: check all keys for a sufficiently similar query
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

def _set_to_redis(key: str, value: Any) -> bool:
    """Set value in Redis cache."""
    redis_client = _get_redis_client()
    if not redis_client:
        return False
    try:
        redis_client.set(f"cache:{key}", json.dumps(value, ensure_ascii=False))
        return True
    except Exception as e:
        print(f"[REDIS ERROR] Error writing to Redis: {e}")
        return False

def _add_cache_indicator(response: str, cache_type: str) -> str:
    """Append a cache hit indicator note to the response."""
    cache_note = f"\n\n---\n*This response was retrieved from cache for faster delivery.*\n*Tip: Add \"No cache\" to your message to bypass cache and get a fresh response.*"
    return response + cache_note

def get_from_cache(query: str, bypass_cache: bool = False) -> Optional[Any]:
    """Retrieve a cached response for the query if available, using normalization and fuzzy matching."""
    # Allow user to bypass cache via special keywords in the query
    bypass_keywords = ["no cache", "don't cache", "dont cache", "bypass cache", "skip cache", "fresh response"]
    if bypass_cache or any(keyword in query.lower() for keyword in bypass_keywords):
        print(f"[CACHE BYPASSED] User requested no cache for: '{query}'")
        return None
    normalized_key = _create_cache_key(query)
    # Try Redis first (if enabled)
    if USE_REDIS:
        redis_result = _get_from_redis(normalized_key)
        if redis_result:
            # Check if it was an exact match or fuzzy (for logging purposes)
            if normalized_key in [ _normalize_text(k) for k in _get_redis_client().keys("cache:*") or [] ]:
                print(f"[REDIS HIT - EXACT] Found exact match for: '{query}'")
            return _add_cache_indicator(redis_result, "Redis")
    # Fall back to JSON cache
    json_cache = _load_json_cache()
    # Exact match in JSON cache
    if normalized_key in json_cache:
        print(f"[JSON HIT - EXACT] Found exact match for: '{query}'")
        return _add_cache_indicator(json_cache[normalized_key], "JSON")
    # Fuzzy match in JSON cache
    similar_key = _find_similar_cache_key(normalized_key, list(json_cache.keys()))
    if similar_key:
        print(f"[JSON HIT - FUZZY] Similar query '{similar_key}' found for: '{query}'")
        return _add_cache_indicator(json_cache[similar_key], "JSON")
    print(f"[CACHE MISS] No match found for: '{query}'")
    return None

def add_to_cache(query: str, response: Any) -> None:
    """Add or update a cache entry for the given query and response."""
    if response is None:
        return
    normalized_key = _create_cache_key(query)
    # Save to Redis if available
    redis_saved = False
    if USE_REDIS:
        redis_saved = _set_to_redis(normalized_key, response)
        if redis_saved:
            print(f"[REDIS STORED] Saved response for: '{query}' (key: '{normalized_key}')")
    # Always save to JSON as backup
    json_cache = _load_json_cache()
    json_cache[normalized_key] = response
    _save_json_cache(json_cache)
    if not redis_saved:
        print(f"[JSON STORED] Saved response for: '{query}' (key: '{normalized_key}')")