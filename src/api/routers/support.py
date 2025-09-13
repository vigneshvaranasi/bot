from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from src.support_bot.crew import support_crew
from src.support_bot.utils.formatting import sanitize_markdown_output
from src.support_bot.utils.cache import get_from_cache, add_to_cache

router = APIRouter()

class SupportRequest(BaseModel):
    prompt: str
    stream: bool = False

class SupportResponse(BaseModel):
    status: str
    result: Optional[str] = None
    error: Optional[str] = None

async def _process_support_prompt(prompt: str, context: Optional[str] = ""):
    """Process support bot prompt."""
    try:
        # Ensure context is always a string for consistent cache behavior
        context = context or ""
        
        # Check cache first for faster responses
        cached_response = get_from_cache(prompt, context)
        if cached_response:
            print(f"[Cache Hit] Returning cached response for: {prompt}")
            return cached_response
        
        print(f"[Cache Miss] Processing new prompt: {prompt}")
        
        # Generate new response if not cached
        inputs = {"user_prompt": prompt}
        inputs["context"] = context
        result = await support_crew.kickoff_async(inputs=inputs)
        cleaned_result = sanitize_markdown_output(result.raw)
        
        # Cache the new response
        add_to_cache(prompt, context, cleaned_result)
        print(f"[Cache Stored] Cached response for: {prompt}")
        
        return cleaned_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing prompt: {str(e)}")

@router.post("/prompt", response_model=SupportResponse)
async def support_endpoint(request: SupportRequest):
    """Support bot endpoint (non-streaming)."""
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    # Ensure context is always an empty string for consistent cache behavior
    context = ""
    result = await _process_support_prompt(prompt=request.prompt, context=context)
    return SupportResponse(status="completed", result=result)