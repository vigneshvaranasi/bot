from fastapi import FastAPI
from src.api.db.base import get_db
from src.api.db import models

app = FastAPI(title="Support Bot", version="1.0.0")

@app.get("/health")
def health_check():
    return {"status": "ok"}
