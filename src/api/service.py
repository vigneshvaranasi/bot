import asyncio
import json
import pathlib
import re
import traceback
from typing import Dict, Any

from crewai.agents.parser import AgentFinish
from crewai.tasks.task_output import TaskOutput
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Support Bot Crew
from src.support_bot.crew import support_crew

app = FastAPI(title="Support Bot API", version="1.0.0")


class SupportRequest(BaseModel):
    prompt: str
    stream: bool = False


class SupportResponse(BaseModel):
    status: str
    result: str = ""
    error: str = None


async def _process_support_prompt(prompt: str, context: str = None):
    """Process support bot prompt."""
    try:
        inputs = {"user_prompt": prompt}
        if context:
            inputs["context"] = context
        result = await support_crew.kickoff_async(inputs=inputs)
        return result.raw
    except Exception as e:
        error_msg = f"Error processing prompt: {str(e)}"
        raise e


# Non-streaming endpoint
@app.post("/prompt", response_model=SupportResponse)
async def support_endpoint(request: SupportRequest):
    """Support bot endpoint (non-streaming)."""
    try:
        if not request.prompt.strip():
            raise HTTPException(status_code=400, detail="Prompt cannot be empty")

        # Currently None, but have to take the context from the Crew
        context = None
        result = await _process_support_prompt(prompt=request.prompt, context=context)
        return SupportResponse(status="completed", result=result)
    except Exception as e:
        return SupportResponse(status="error", result="", error=str(e))


app.mount(
    "/static",
    StaticFiles(directory=str(pathlib.Path(__file__).resolve().parent / "static")),
    name="static",
)
