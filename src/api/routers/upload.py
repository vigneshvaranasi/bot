import os
import uuid
from fastapi import APIRouter, HTTPException, FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

# Embedding model (auto-detect dimension)
embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
VECTOR_SIZE = embedding_model.get_sentence_embedding_dimension()
COLLECTION_NAME = "incident_data_v2"

# Ensure collection exists and has correct dimension
collections = client.get_collections().collections
collection_info = next((c for c in collections if c.name == COLLECTION_NAME), None)
if collection_info is not None:
    # Check dimension
    info = client.get_collection(COLLECTION_NAME)
    current_dim = getattr(getattr(getattr(info, 'config', None), 'params', None), 'vectors', None)
    if hasattr(current_dim, 'size'):
        current_dim = current_dim.size
    if current_dim != VECTOR_SIZE:
        print(f"[Qdrant] Deleting collection '{COLLECTION_NAME}' due to dimension mismatch: {current_dim} != {VECTOR_SIZE}")
        client.delete_collection(collection_name=COLLECTION_NAME)
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
else:
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )

# Schemas

# Accepts id, name, description, but for txt/md, only description may be present
class FileItem(BaseModel):
    id: str = ""
    name: str = ""
    description: str = ""

class FileUpload(BaseModel):
    filename: str
    content: List[dict]

# Router
router = APIRouter(prefix="/files", tags=["File Upload"])

# Helper: embed text
def embed_text(text: str):
    return embedding_model.encode(text).tolist()


@router.get("/count")
async def count_files():
    try:
        count = client.count(collection_name=COLLECTION_NAME, exact=True)
        return {"collection": COLLECTION_NAME, "count": count.count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# API: save file to Qdrant

@router.post("/save")
async def save_file(file: FileUpload):
    if not file.filename or not file.content:
        raise HTTPException(status_code=400, detail="Missing filename or content")

    print("👉 Received payload:", file.dict())  # Debug log

    points = []
    for idx, item in enumerate(file.content):
        # Accept both dicts (from .txt/.md) and Pydantic models (from .json/.csv)
        if isinstance(item, dict):
            name = item.get("name", "")
            description = item.get("description", "")
            item_id = item.get("id", idx)
        else:
            name = getattr(item, "name", "")
            description = getattr(item, "description", "")
            item_id = getattr(item, "id", idx)
        # If both name and description are empty, treat the whole item as description
        if not name and not description:
            description = str(item)
        searchable_text = f"{name} {description}".strip()
        if not searchable_text:
            searchable_text = description or name or str(item)
        vector = embed_text(searchable_text)
        print("👉 Vector length:", len(vector))  # Debug log
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "filename": file.filename,
                    "id": item_id,
                    "name": name,
                    "description": description,
                    "searchable_text": searchable_text,
                },
            )
        )

    try:
        client.upsert(collection_name=COLLECTION_NAME, points=points)
        return {"message": f"✅ Inserted {len(points)} records into Qdrant", "inserted": len(points)}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error saving to Qdrant: {str(e)}")
