from fastapi import FastAPI
from src.api.routers import users, chats, support
from src.api.db.database import engine
from src.api.models import Base

# app init
app = FastAPI(title="Support Bot API", version="1.0.0")

# routing setup
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(chats.router, prefix="/chats", tags=["Chats"])
app.include_router(support.router, prefix="/support", tags=["Support"])

# startup event
@app.on_event("startup")
async def startup():
    pass

# health check
@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}