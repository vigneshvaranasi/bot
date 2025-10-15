from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any
# from src.support_bot.crew import support_crew  # Remove this line
from src.support_bot.utils.formatting import sanitize_markdown_output
from src.api.utils.cache import get_from_cache, add_to_cache

router = APIRouter()

# Global variable to hold crew instance
_support_crew = None

def get_support_crew():
    """Lazy initialization of support crew."""
    global _support_crew
    if _support_crew is None:
        print("[CREW] Initializing support crew...")
        from src.support_bot.crew import support_crew
        _support_crew = support_crew
        print("[CREW] Support crew initialized")
    return _support_crew

class SupportRequest(BaseModel):
    prompt: str
    stream: bool = False
    use_cache: bool = True  # Allow users to bypass cache if needed

class SupportResponse(BaseModel):
    status: str
    result: Optional[str] = None
    error: Optional[str] = None
    cached: bool = False  # Indicate if response came from cache

async def _process_support_prompt(prompt: str, context: Optional[str] = ""):
    """Process support bot prompt."""
    try:
        crew = get_support_crew()  # Use lazy initialization
        inputs = {"user_prompt": prompt}
        inputs["context"] = context
        result = await crew.kickoff_async(inputs=inputs)
        return sanitize_markdown_output(result.raw)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing prompt: {str(e)}")

@router.post("/prompt", response_model=SupportResponse)
async def support_endpoint(request: SupportRequest):
    """Support bot endpoint (non-streaming) with caching support."""
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    # Check cache first if caching is enabled
    cached_response = None
    if request.use_cache:
        try:
            cached_response = get_from_cache(request.prompt)
            if cached_response:
                print(f"[CACHE HIT] Returning cached response for: '{request.prompt[:50]}...'")
                return SupportResponse(
                    status="completed", 
                    result=cached_response, 
                    cached=True
                )
        except Exception as e:
            print(f"[CACHE ERROR] Error reading from cache: {e}")
            # Continue with normal processing if cache fails

    # Process the prompt normally
    context = None
    try:
        result = await _process_support_prompt(prompt=request.prompt, context=context)
        
        # Add response to cache if caching is enabled
        if request.use_cache and result:
            try:
                add_to_cache(request.prompt, result)
                print(f"[CACHE STORED] Cached response for: '{request.prompt[:50]}...'")
            except Exception as e:
                print(f"[CACHE ERROR] Error storing to cache: {e}")
                # Don't fail the request if caching fails
        
        return SupportResponse(status="completed", result=result, cached=False)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing prompt: {str(e)}")

@router.get("/cache/status")
async def cache_status():
    """Get cache system status and configuration."""
    from src.api.utils.cache import USE_REDIS, _get_redis_client, CACHE_FILE
    import os
    import json
    
    status = {
        "redis_enabled": USE_REDIS,
        "redis_connected": False,
        "json_cache_file": CACHE_FILE,
        "json_cache_exists": os.path.exists(CACHE_FILE),
        "json_cache_entries": 0
    }
    
    # Check Redis connection
    if USE_REDIS:
        try:
            redis_client = _get_redis_client()
            if redis_client:
                redis_client.ping()
                status["redis_connected"] = True
                # Count Redis cache entries
                cache_keys = redis_client.keys("cache:*")
                status["redis_cache_entries"] = len(cache_keys)
        except Exception as e:
            status["redis_error"] = str(e)
    
    # Check JSON cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                json_cache = json.load(f)
                status["json_cache_entries"] = len(json_cache)
        except Exception as e:
            status["json_cache_error"] = str(e)
    
    return status

@router.delete("/cache/clear")
async def clear_cache(cache_type: str = Query("all", description="Cache type to clear: 'redis', 'json', or 'all'")):
    """Clear cache entries."""
    from src.api.utils.cache import USE_REDIS, _get_redis_client, CACHE_FILE
    import os
    import json
    
    cleared = {"redis": 0, "json": 0, "errors": []}
    
    if cache_type in ["redis", "all"] and USE_REDIS:
        try:
            redis_client = _get_redis_client()
            if redis_client:
                cache_keys = redis_client.keys("cache:*")
                if cache_keys:
                    cleared["redis"] = redis_client.delete(*cache_keys)
        except Exception as e:
            cleared["errors"].append(f"Redis clear error: {e}")
    
    if cache_type in ["json", "all"]:
        try:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    json_cache = json.load(f)
                    cleared["json"] = len(json_cache)
                
                # Clear the cache
                with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                    json.dump({}, f, indent=2)
        except Exception as e:
            cleared["errors"].append(f"JSON clear error: {e}")
    
    return {
        "message": f"Cache cleared successfully",
        "cleared": cleared
    }