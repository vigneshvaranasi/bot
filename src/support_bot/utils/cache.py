import json
import os
import re
from typing import Any, Dict, Optional
from difflib import SequenceMatcher

# Location of cache file
CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "cache.json")

# Similarity threshold for fuzzy matching (0.0 to 1.0)
SIMILARITY_THRESHOLD = 0.45


def _normalize_text(text: str) -> str:
    """Normalize text for better matching by handling case, punctuation, and common variations."""
    if not text:
        return ""
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove extra whitespace and normalize spaces
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Remove punctuation except apostrophes in contractions
    text = re.sub(r'[^\w\s\']', '', text)
    
    # Handle common plural forms
    plural_mappings = {
        r'\bissues?\b': 'issue',
        r'\bproblems?\b': 'problem', 
        r'\berrors?\b': 'error',
        r'\busernames?\b': 'username',
        r'\bpasswords?\b': 'password',
        r'\baccounts?\b': 'account',
        r'\bservices?\b': 'service',
        r'\bconnections?\b': 'connection',
        r'\btimeouts?\b': 'timeout',
        r'\brequests?\b': 'request',
        r'\bresponses?\b': 'response',
    }
    
    for pattern, replacement in plural_mappings.items():
        text = re.sub(pattern, replacement, text)
    
    # Handle common synonyms and variations
    synonym_mappings = {
        r'\blog\s*in\b': 'login',
        r'\bsign\s*in\b': 'login',
        r'\bsign\s*up\b': 'signup',
        r'\bregister\b': 'signup',
        r'\bcannot\b': 'cant',
        r'\bcant\b': 'cant',
        r'\bunable\s+to\b': 'cant',
        r'\bfailed\s+to\b': 'cant',
        r'\bwont\b': 'wont',
        r'\bwill\s+not\b': 'wont',
        r'\bdoesnt\b': 'doesnt',
        r'\bdoes\s+not\b': 'doesnt',
        r'\bisnt\b': 'isnt',
        r'\bis\s+not\b': 'isnt',
        r'\bstatus\s+code\b': 'statuscode',
        r'\berror\s+code\b': 'errorcode',
        r'\bhttp\s+(\d+)\b': r'http \1',
        r'\bcode\s+(\d+)\b': r'code \1',
        # Enhanced error/issue synonyms
        r'\bissues?\b': 'error',
        r'\bproblems?\b': 'error',
        r'\bfaults?\b': 'error',
        r'\bfailures?\b': 'error',
        # HTTP error specific patterns
        r'\bget\s+(\d+)\b': r'\1',
        r'\breceive\s+(\d+)\b': r'\1',
        r'\bhaving\s+(\d+)\b': r'\1',
        r'\bseeing\s+(\d+)\b': r'\1',
        r'\bencountering\s+(\d+)\b': r'\1',
        # Action synonyms for resolution
        r'\bsolve\b': 'resolve',
        r'\bfix\b': 'resolve',
        r'\btroubleshoot\b': 'resolve',
        r'\bresolve\s+it\b': 'resolve',
        r'\bhelp\s+me\s+resolve\b': 'resolve',
        r'\bhelp\s+me\s+fix\b': 'resolve',
        r'\bhelp\s+me\s+solve\b': 'resolve',
    }
    
    for pattern, replacement in synonym_mappings.items():
        text = re.sub(pattern, replacement, text)
    
    return text.strip()


def _calculate_similarity(text1: str, text2: str) -> float:
    """Calculate similarity between two normalized texts using sequence matching with HTTP error pattern boost."""
    base_similarity = SequenceMatcher(None, text1, text2).ratio()
    
    # Apply boost for HTTP error patterns
    http_error_patterns = [
        r'\b(http\s+)?\d{3}\s+(error|status|code|issue|problem)?\b',
        r'\b(error|status|code|issue|problem)\s+\d{3}\b',
        r'\b\d{3}\s+(http\s+)?(error|status|code|issue|problem)?\b'
    ]
    
    # Check if both texts contain HTTP error patterns
    has_http_pattern_1 = any(re.search(pattern, text1, re.IGNORECASE) for pattern in http_error_patterns)
    has_http_pattern_2 = any(re.search(pattern, text2, re.IGNORECASE) for pattern in http_error_patterns)
    
    if has_http_pattern_1 and has_http_pattern_2:
        # Extract error codes from both texts
        error_code_1 = re.search(r'\b(\d{3})\b', text1)
        error_code_2 = re.search(r'\b(\d{3})\b', text2)
        
        if error_code_1 and error_code_2 and error_code_1.group(1) == error_code_2.group(1):
            # Same error code found - boost similarity by 30%
            base_similarity = min(1.0, base_similarity + 0.3)
        elif error_code_1 and error_code_2:
            # Different error codes - slight penalty
            base_similarity = max(0.0, base_similarity - 0.1)
    
    # Additional boost for resolution-related terms
    resolution_terms = ['resolve', 'fix', 'solve', 'help', 'troubleshoot']
    has_resolution_1 = any(term in text1 for term in resolution_terms)
    has_resolution_2 = any(term in text2 for term in resolution_terms)
    
    if has_resolution_1 and has_resolution_2:
        # Both mention resolution - slight boost
        base_similarity = min(1.0, base_similarity + 0.1)
    
    return base_similarity


def _create_cache_key(query: str, context: str = "") -> str:
    """Create a normalized cache key from query and context."""
    normalized_query = _normalize_text(query)
    normalized_context = _normalize_text(context)
    return f"{normalized_query}::{normalized_context}"


def _find_similar_cache_key(target_key: str, cache: Dict[str, Any]) -> Optional[str]:
    """Find a similar cache key using fuzzy matching."""
    target_parts = target_key.split("::")
    target_query = target_parts[0] if target_parts else ""
    target_context = target_parts[1] if len(target_parts) > 1 else ""
    
    best_match = None
    best_similarity = 0.0
    
    for cached_key in cache.keys():
        cached_parts = cached_key.split("::")
        cached_query = cached_parts[0] if cached_parts else ""
        cached_context = cached_parts[1] if len(cached_parts) > 1 else ""
        
        # Calculate similarity for both query and context
        query_similarity = _calculate_similarity(target_query, cached_query)
        context_similarity = _calculate_similarity(target_context, cached_context) if target_context or cached_context else 1.0
        
        # Weight query similarity more heavily than context
        overall_similarity = (query_similarity * 0.8) + (context_similarity * 0.2)
        
        if overall_similarity > best_similarity and overall_similarity >= SIMILARITY_THRESHOLD:
            best_similarity = overall_similarity
            best_match = cached_key
    
    return best_match


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
    # Ensure the data directory exists
    cache_dir = os.path.dirname(CACHE_FILE)
    os.makedirs(cache_dir, exist_ok=True)
    
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_from_cache(query: str, context: str = "") -> Optional[Any]:
    """Retrieve a value from cache using intelligent matching."""
    cache = _load_cache()
    
    # First try exact match with normalized key
    normalized_key = _create_cache_key(query, context)
    if normalized_key in cache:
        return cache[normalized_key]
    
    # If no exact match, try fuzzy matching
    similar_key = _find_similar_cache_key(normalized_key, cache)
    if similar_key:
        return cache[similar_key]
    
    return None


def add_to_cache(query: str, context: str = "", value: Any = None) -> None:
    """Add or update a cache entry with normalized key."""
    if value is None:
        return
        
    cache = _load_cache()
    normalized_key = _create_cache_key(query, context)
    cache[normalized_key] = value
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


def get_cache_stats() -> Dict[str, Any]:
    """Get statistics about the cache."""
    cache = _load_cache()
    return {
        "total_entries": len(cache),
        "cache_file_exists": os.path.exists(CACHE_FILE),
        "similarity_threshold": SIMILARITY_THRESHOLD,
        "cache_keys": list(cache.keys())
    }
