import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Model Configuration
EMBEDDING_MODEL_NAME = "models/embedding-001"
LLM_MODEL_NAME = "gemini-2.5-pro"

# DB URL
VECTOR_DATABASE_URL = os.getenv("VECTOR_DATABASE_URL")