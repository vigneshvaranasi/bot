from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from support_bot.crew import support_crew

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
        inputs = {"user_prompt": prompt}
        inputs["context"] = context
        result = await support_crew.kickoff_async(inputs=inputs)
        return result.raw
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing prompt: {str(e)}")

@router.post("/prompt", response_model=SupportResponse)
async def support_endpoint(request: SupportRequest):
    """Support bot endpoint (non-streaming)."""
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    context = None
    result = await _process_support_prompt(prompt=request.prompt, context=context)
    return SupportResponse(status="completed", result=result)