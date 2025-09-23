# src/api/routers/upload.py
import os
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from dotenv import load_dotenv

# Qdrant imports
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct

# Embedding model
from sentence_transformers import SentenceTransformer

# Load env
load_dotenv()
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

if not QDRANT_URL:
    raise RuntimeError("QDRANT_URL missing in .env")
client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

# Embedding model
embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
VECTOR_SIZE = 384
COLLECTION_NAME = "incident_data"

# Ensure collection exists
if COLLECTION_NAME not in [c.name for c in client.get_collections().collections]:
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
    )

# Schemas
class FileItem(BaseModel):
    id: int
    name: str = ""
    description: str = ""

class FileUpload(BaseModel):
    filename: str
    content: List[FileItem]

# Router
router = APIRouter(prefix="/files", tags=["File Upload"])

# Helper: embed text
def embed_text(text: str):
    return embedding_model.encode(text).tolist()

# API: save file to Qdrant
@router.post("/save")
async def save_file(file: FileUpload):
    if not file.filename or not file.content:
        raise HTTPException(status_code=400, detail="Missing filename or content")

    points = []
    for item in file.content:
        searchable_text = f"{item.name} {item.description}"
        vector = embed_text(searchable_text)
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "filename": file.filename,
                    "id": item.id,
                    "name": item.name,
                    "description": item.description,
                    "searchable_text": searchable_text,
                },
            )
        )

    try:
        client.upsert(collection_name=COLLECTION_NAME, points=points)
        return {"message": f"✅ Inserted {len(points)} records into Qdrant", "inserted": len(points)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving to Qdrant: {str(e)}")
