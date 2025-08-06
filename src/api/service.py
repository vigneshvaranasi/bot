# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import asyncio
import json
import pathlib
import re
import traceback
from typing import Dict, Any

from crewai.agents.parser import AgentFinish
from crewai.tasks.task_output import TaskOutput
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Import your support bot crew
from src.support_bot.crew import support_crew



STATIC_DIR = pathlib.Path(__file__).parent.parent / "static"
INDEX_HTML_PATH = STATIC_DIR / "index.html"
KEEPALIVE_INTERVAL_SECS = 5
MAX_KEEPALIVE_SECS = 120

app = FastAPI(title="Support Bot API", version="1.0.0")
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class SupportRequest(BaseModel):
    prompt: str
    stream: bool = False

class SupportResponse(BaseModel):
    status: str
    result: str = ""
    error: str = None


async def _process_support_prompt(prompt: str, output_queue: asyncio.Queue = None):
    """Process support bot prompt, optionally pushing progress to queue for streaming."""
    try:
        if output_queue:
            await output_queue.put({'event': 'progress_update', 'status': 'started'})

        support_loop = asyncio.get_running_loop()

        def update_hook(msg: TaskOutput | AgentFinish) -> None:
            if isinstance(msg, AgentFinish):
                print(json.dumps({
                    'thought': msg.thought,
                    'output': msg.output,
                    'text': msg.text
                }))
                return
            if output_queue:
                support_loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(output_queue.put({
                        'event': 'progress_update',
                        'task': getattr(msg, 'name', None),
                        'summary': getattr(msg, 'summary', None),
                        'status': 'task_done'
                    }))
                )

        # Use your support crew with callbacks if streaming
        # If your crew supports callbacks, pass them here
        # crew = support_crew(task_callback=update_hook, step_callback=update_hook)
        # For now, just use support_crew as is
        inputs = {'data_query': prompt}
        result = await support_crew.kickoff_async(inputs=inputs)
        if output_queue:
            await output_queue.put({'status': 'completed', 'output': result.raw})
        return result.raw
    except Exception as e:
        error_msg = f"Error processing prompt: {str(e)}"
        if output_queue:
            await output_queue.put({'status': 'error', 'message': error_msg})
        raise e


# Non-streaming endpoint
@app.post("/support", response_model=SupportResponse)
async def support_endpoint(request: SupportRequest):
    """Support bot endpoint (non-streaming)."""
    try:
        if not request.prompt.strip():
            raise HTTPException(status_code=400, detail="Prompt cannot be empty")
        result = await _process_support_prompt(request.prompt)
        return SupportResponse(status="completed", result=result)
    except Exception as e:
        return SupportResponse(status="error", result="", error=str(e))

# Streaming endpoint
@app.post("/support/stream")
async def support_stream_endpoint(request: SupportRequest):
    """Support bot endpoint with streaming progress updates."""
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    async def generate_updates():
        update_queue = asyncio.Queue()
        support_task = asyncio.create_task(_process_support_prompt(request.prompt, update_queue))
        data_task = asyncio.create_task(update_queue.get())
        heartbeat_task = asyncio.create_task(asyncio.sleep(KEEPALIVE_INTERVAL_SECS))

        try:
            while True:
                done, pending = await asyncio.wait(
                    [data_task, heartbeat_task],
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=MAX_KEEPALIVE_SECS,
                )

                if data_task in done:
                    update = await data_task
                    print(json.dumps(update))

                    output = ''
                    if event := update.pop('event', None):
                        output += f'event: {event}\n'

                    output += f"data: {json.dumps(update)}\n\n"
                    yield output
                    data_task = asyncio.create_task(update_queue.get())

                    if update.get('status') in ['completed', 'error']:
                        break

                elif heartbeat_task in done:
                    yield "event: ping\ndata: {}\n\n"
                    heartbeat_task = asyncio.create_task(asyncio.sleep(KEEPALIVE_INTERVAL_SECS))

                elif not done and pending:
                    raise asyncio.TimeoutError("Stream timed out.")

        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'status': 'error', 'message': 'Stream timed out.'})}\n\n"
            print("Stream timed out: No updates received.")

        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'message': f'An error occurred: {str(e)}'})}\n\n"
            print(f"Error during streaming: {e}")
            print(json.dumps({
                "type": type(e).__name__,
                "message": str(e),
                "traceback": traceback.format_exc()
            }))

        finally:
            if not support_task.done():
                support_task.cancel()
            if not heartbeat_task.done():
                heartbeat_task.cancel()
            if not data_task.done():
                data_task.cancel()

            await asyncio.gather(support_task, heartbeat_task, return_exceptions=True)

    return StreamingResponse(generate_updates(), media_type="text/event-stream")


@app.get("/", response_class=HTMLResponse)
async def home_page():
    """Serve a simple web UI for the support bot."""
    return """
    <!DOCTYPE html>
    <html lang='en'>
    <head>
        <meta charset='UTF-8'>
        <meta name='viewport' content='width=device-width, initial-scale=1.0'>
        <title>Support Bot</title>
        <style>
            body { font-family: Arial, sans-serif; background: #f7f7f7; margin: 0; padding: 0; }
            .container { max-width: 600px; margin: 40px auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 8px #0001; padding: 32px; }
            h1 { text-align: center; color: #333; }
            #prompt { width: 100%; padding: 12px; font-size: 1.1em; border-radius: 4px; border: 1px solid #ccc; margin-bottom: 16px; }
            #send-btn { padding: 10px 24px; font-size: 1.1em; border: none; border-radius: 4px; background: #0078d4; color: #fff; cursor: pointer; }
            #send-btn:disabled { background: #aaa; }
            #response { margin-top: 24px; background: #f0f0f0; border-radius: 4px; padding: 16px; min-height: 40px; white-space: pre-wrap; }
        </style>
    </head>
    <body>
        <div class='container'>
            <h1>Support Bot</h1>
            <input id='prompt' type='text' placeholder='Enter your support question...' autofocus />
            <button id='send-btn'>Send</button>
            <div id='response'></div>
        </div>
        <script>
        const promptInput = document.getElementById('prompt');
        const sendBtn = document.getElementById('send-btn');
        const responseDiv = document.getElementById('response');

        sendBtn.onclick = async function() {
            const prompt = promptInput.value.trim();
            if (!prompt) return;
            sendBtn.disabled = true;
            responseDiv.textContent = 'Thinking...';
            try {
                const res = await fetch('/support', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt })
                });
                const data = await res.json();
                if (data.status === 'completed') {
                    responseDiv.textContent = data.result;
                } else {
                    responseDiv.textContent = data.error || 'Error occurred.';
                }
            } catch (e) {
                responseDiv.textContent = 'Network error.';
            }
            sendBtn.disabled = false;
        };
        promptInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') sendBtn.click();
        });
        </script>
    </body>
    </html>
    """
