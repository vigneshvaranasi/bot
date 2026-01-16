"""
Cache Implementation for LangGraph Support Bot
==============================================

This module provides a Redis-based caching system for the support bot.
Features include fuzzy text matching, similarity scoring, and automatic cache management.

Integration Points:
- Redis cache with semantic similarity matching
- Fuzzy text matching for similar queries
- Cache bypass functionality
- Automatic cache invalidation
- Environment-based configuration

Usage:
    from scripts.cache import get_from_cache, add_to_cache
    
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
from sentence_transformers import SentenceTransformer
import numpy as np

# Load environment variables from .env file
load_dotenv()

# Initialize sentence transformer for semantic similarity (cached globally)
_embedding_model = None

def _get_embedding_model():
    """Get or initialize the sentence transformer model (cached)."""
    global _embedding_model
    if _embedding_model is None:
        try:
            _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            print("[CACHE] Sentence transformer model loaded for semantic similarity")
        except Exception as e:
            print(f"[CACHE ERROR] Failed to load sentence transformer: {e}")
            _embedding_model = False  # Mark as failed to avoid retrying
    return _embedding_model if _embedding_model else None

# Cache configuration
SIMILARITY_THRESHOLD = 0.85  # Threshold for semantic similarity (0.0-1.0) - Balanced for good matches
MIN_TOPIC_OVERLAP = 0.70  # Minimum topic overlap required (0.0-1.0) - Not used with sentence transformers

# Define common stopwords to ignore in topic extraction
STOPWORDS = {
    "the", "a", "an", "and", "or", "if", "to", "of", "at", "by",
    "for", "in", "on", "with", "that", "this", "it", "is", "are",
    "was", "were", "i", "me", "my", "you", "your", "we", "us", "our",
    "can", "cannot", "cant", "not", "do", "does", "did", "no", "be",
    "what", "when", "where", "why", "how", "which", "who", "whom"
}

# Context-dependent query patterns
CONTEXT_PATTERNS = [
    r'\b(it|this|that|these|those|them|they|he|she)\b',  # Pronouns referring to previous context
    r'\b(above|previous|last|earlier|before|related to it|about it)\b',  # References to previous messages
    r'\b(same|similar|like that|such as)\b',  # Comparisons to previous context
    r'\bmore (details|info|information)\b',  # Asking for elaboration
    r'\b(continue|go on|keep going|elaborate)\b',  # Continuation requests
    r'\b(the|that|this)\s+(related|relevant|associated|corresponding)\b',  # "the related incident", "the relevant issue"
    r'\brelated\s+(incident|issue|problem|error|case)\b',  # "related incident from database"
    r'\bfrom\s+(the\s+)?(database|above|context|discussion)\b',  # "from the database", "from above"
    r'\b(tell|show|give|get)\s+me\s+(the|that|this|more|another)\s+(related|relevant|one|example)\b',  # "give me the related...", "show me that example"
    r'\b(what|which|who)\s+(was|is|were|are)\s+(that|this)\b',  # "what was that...", "which is this..." (not "the")
    r'\b(another|other|different)\s+(one|example|case|incident)\b',  # "another example", "other case"
    r'\bfor\s+(this|that|the\s+same|it)\b',  # "for this", "for that issue"
    r'\babout\s+(this|that|it)\b',  # "about this", "about that"
    r'\b(explain|describe|detail)\s+(this|that|it)\b',  # "explain this", "describe that"
]

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

def _is_context_dependent(query: str) -> bool:
    """
    Fast pattern-based context detection using regex.
    Much faster than LLM-based detection while still being effective.
    """
    query_lower = query.lower()
    
    # Check for context-dependent patterns
    for pattern in CONTEXT_PATTERNS:
        if re.search(pattern, query_lower):
            print(f"[CONTEXT DETECTION] Query is context-dependent (matched pattern: {pattern})")
            return True
    
    return False

def _calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate similarity between two texts using semantic embeddings.
    Much faster and more accurate than LLM-based or pure string matching.
    
    Uses sentence transformers for semantic understanding while still 
    checking for numeric differences.
    """
    # Check for numeric differences first (fast rejection)
    nums1 = set(re.findall(r'\d+', text1))
    nums2 = set(re.findall(r'\d+', text2))
    if nums1 and nums2 and nums1 != nums2:
        return 0.0  # Different numbers = different queries
    
    # Try semantic similarity using sentence transformers
    model = _get_embedding_model()
    if model is not None:
        try:
            # Generate embeddings
            embeddings = model.encode([text1, text2], convert_to_numpy=True)
            
            # Normalize embeddings
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            embeddings = embeddings / norms
            
            # Calculate cosine similarity
            similarity = float(np.dot(embeddings[0], embeddings[1]))
            return max(0.0, min(1.0, similarity))  # Clamp to [0, 1]
        except Exception as e:
            print(f"[CACHE WARNING] Semantic similarity failed, falling back to string matching: {e}")
    
    # Fallback to basic string similarity if semantic model unavailable
    base_sim = SequenceMatcher(None, text1, text2).ratio()
    return base_sim

def _create_cache_key(query: str) -> str:
    """Create a normalized cache key from the query text."""
    return _normalize_text(query)



def _find_similar_cache_key(target_key: str, cache_keys: list) -> Optional[str]:
    """Find a similar cache key using STRICT fuzzy matching."""
    best_match = None
    best_similarity = 0.0
    
    for cached_key in cache_keys:
        similarity = _calculate_similarity(target_key, cached_key)
        if similarity > best_similarity and similarity >= SIMILARITY_THRESHOLD:
            best_similarity = similarity
            best_match = cached_key
            print(f"[CACHE SIMILARITY] Matched '{target_key[:50]}...' with '{cached_key[:50]}...' (score: {similarity:.3f})")
    
    if best_match:
        print(f"[CACHE FUZZY MATCH] Best match score: {best_similarity:.3f} (threshold: {SIMILARITY_THRESHOLD})")
    
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
    
    # Check if query is context-dependent
    if _is_context_dependent(query):
        print(f"[CACHE SKIPPED] Query is context-dependent: '{query[:50]}...'")
        return None
    
    normalized_key = _create_cache_key(query)
    
    # Try Redis cache (if enabled)
    if USE_REDIS:
        redis_result = _get_from_redis(normalized_key)
        if redis_result:
            print(f"[REDIS HIT] Found cached response for: '{query[:50]}...'")
            return _add_cache_indicator(redis_result, "Redis")
    
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
    
    # Don't cache context-dependent queries
    if _is_context_dependent(query):
        print(f"[CACHE SKIPPED] Not caching context-dependent query: '{query[:50]}...'")
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
    
    # Save to Redis if available (using the existing key if found)
    if USE_REDIS:
        redis_saved = _set_to_redis(existing_key, response, ttl)
        if redis_saved:
            ttl_msg = f" (TTL: {ttl}s)" if ttl else ""
            action = "Updated" if existing_key != normalized_key else "Saved"
            print(f"[REDIS STORED] {action} response for: '{query[:50]}...'{ttl_msg}")
        else:
            print(f"[CACHE SKIPPED] Failed to save to Redis for: '{query[:50]}...'")
    else:
        print(f"[CACHE SKIPPED] Redis cache is disabled")

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
                else:
                    print("[REDIS] No keys to clear")
            else:
                print("[REDIS] Not connected")
        else:
            print("[CACHE] Redis cache is disabled")
        
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
    """Check if Redis caching is enabled."""
    return USE_REDIS and _get_redis_client() is not None

def get_cache_config() -> Dict[str, Any]:
    """Get current cache configuration."""
    return {
        "use_redis": USE_REDIS,
        "redis_config": REDIS_CONFIG if USE_REDIS else None,
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