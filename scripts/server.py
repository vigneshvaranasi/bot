from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import json

app = FastAPI(title="File Upload API")

# Enable CORS for your Vite frontend
origins = ["http://localhost:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic model
class FileUpload(BaseModel):
    filename: str
    content: list

# Ensure /data folder exists
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

@app.post("/save-file")
async def save_file(file: FileUpload):
    if not file.filename or not file.content:
        raise HTTPException(status_code=400, detail="Missing filename or content")
    file_path = os.path.join(DATA_DIR, file.filename)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(file.content, f, ensure_ascii=False, indent=2)
        return {"message": f"File saved as {file_path}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving file: {str(e)}")
