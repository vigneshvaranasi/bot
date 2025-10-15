from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from src.api.routers import users, chats, support, auth, roles, settings
from src.api.db.database import engine
from src.api.db_models import Base

# app init
app = FastAPI(title="Support Bot API", version="1.0.0", redirect_slashes=False)

# CORS middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "https://dth5w8dq-5173.inc1.devtunnels.ms",
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_origin_regex=r"https://.*\.devtunnels\.ms$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=86400
)

# routing setup
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(roles.router, prefix="/roles", tags=["Roles"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(chats.router, prefix="/chats", tags=["Chats"])
app.include_router(support.router, prefix="/support", tags=["Support"])
app.include_router(settings.router, prefix="/settings", tags=["Settings"])
app.include_router(upload.router)

# startup event
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# health check
@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}