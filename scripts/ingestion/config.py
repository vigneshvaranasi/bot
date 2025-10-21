import torch
import os
from dotenv import load_dotenv
load_dotenv()

class EmbeddingConfig:
    """Configuration for the embedding model."""
    
    MODEL_NAME = "all-MiniLM-L6-v2"
    
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    
    MODEL_KWARGS = {'device': DEVICE}
    
    ENCODE_KWARGS = {'normalize_embeddings': True}

class QdrantConfig:
    """Configuration for the Qdrant Vector Store."""
    URL = "http://localhost:6333"
    
    COLLECTION_NAME = "past_issues_v2"

class DataConfig:
    """Configuration for the data sources."""
    INCIDENT_JSON_PATH = "data/incidents.json"

class TextSplitterConfig:
    """Configuration for the text chunking."""
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 200

EMBEDDING_SETTINGS = EmbeddingConfig()
QDRANT_SETTINGS = QdrantConfig()
DATA_SETTINGS = DataConfig()
SPLITTER_SETTINGS = TextSplitterConfig()